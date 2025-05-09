#!/usr/bin/env python3
import os, asyncio
import argparse
from typing import List, Union, Dict
from fastmcp import FastMCP, Context
from agents import Agent, Runner, gen_trace_id, trace, set_default_openai_key
from agents.mcp import MCPServerSse, MCPServerSseParams
from agents.model_settings import ModelSettings
import spacy
import pandas
from edgar import Company, set_identity
from bs4 import BeautifulSoup
import pandas as pd
import re
from loguru import logger
from datetime import datetime
from csv import DictReader

    # Create the FastMCP server _with_ host/port settings
# Parse command-line arguments for port (and optionally host)
parser = argparse.ArgumentParser(
    description="Start the lookup SSE server with configurable port and host"
)
parser.add_argument(
    "--port", "-p",
    type=int,
    default=8000,
    help="Port to bind the SSE server to (default: 8000)"
)
parser.add_argument(
    "--host", "-H",
    type=str,
    default="127.0.0.1",
    help="Host/interface to bind to (default: 127.0.0.1)"
)
args = parser.parse_args()

name = "StockSentiment"
# put this in SECTRETS
SEC_EDGAR_USER_AGENT="John Williams (jrwtango@gmail.com)"
set_identity(SEC_EDGAR_USER_AGENT)

mcp = FastMCP(name=name, port=8000, host="localhost")


@mcp.tool("TestEdgar", description="Test out the EDGAR API")
async def testEdgar()-> Dict[str,str]:
    # Test the EDGAR API
    company = Company("AAPL")
    print(company)
    try:
        """
        filings = company.get_filings().latest(10)
        print(filings)
        filing8k = filings.filter(form="8-K")
        print(filing8k)
        filing10k = filings.filter(form="10-K")
        print(filing10k)
        filing10q = filings.filter(form="10-Q")
        print(filing10q)
        insider_sales = filings.filter(form="4")
        print(f"insider salies {insider_sales}")

        income_statement = company.get_financials().income_statement()

        balance_sheet = company.get_financials().balance_sheet()

        print(f"Sentiment Adjustment: {balance_sheet}")
        """
        sentiment = 0.5
        return {'Sentiment: ': str(sentiment)}

    except AttributeError:  
        pass
     
    


@mcp.tool("get_8k_filings", description="Get 8k filings for a list of companies")
async def get_8k_filings_tool()-> Dict[str,str]:

    morning_movers = [ ]

    # List of stocks
    spx_morning_movers = ["AAPL","MSFT"]

    morning_movers.extend(spx_morning_movers)

    morning_movers = list(set(morning_movers))

    ticker_news = []
    

    for ticker in morning_movers:
        company = Company(ticker)
        try:
            latest_filing = company.get_filings().latest(3)
            annual_reports = latest_filing.filter(form="10-K")
            text = latest_filing.text()
            #financials = company.financials
            #income_statement = financials.income_statement()
            #balance_sheet = financials.balance_sheet()
            # cashflow = financials.cashflow_statement()
            # annual_reports = company.get_filings(form="10-K").latest(3)

            # latest_10qs = quarterly_reports.latest(3)
        except AttributeError:
            continue

        if latest_filing is None:
            continue

        filing_text = str(latest_filing.obj())

        # Remove non-text characters like borders, repetitive dashes or extraneous dividers, and multiple
        # spaces/newlines using regex
        clean_text = re.sub(r"[^\w\s,.()\'\"\-]", "", filing_text)
        clean_text = re.sub(r"-{2,}", "", clean_text)
        clean_text = re.sub(r"\s+", " ", clean_text).strip()
        ticker_news.append(clean_text)

    # expand list
    print(ticker_news)
    return {"ticker" : ticker_news}

@mcp.tool("analyze_stock_sentiment", description="Analyze sentiment from SEC data")
async def analyze_stock_sentiment(text: Union[str, Dict]) -> Dict[str, str]:
    if isinstance(text, dict):
        content = "\n".join(f"{k}: {v}" for k, v in text.items())
    elif isinstance(text, str):
        content = text
    else:
        return {"error": "Invalid input type"}

    EVENTS = {
        "Executive Changes": ["resigned", "appointed", "left the company", "terminated"],
        "Financial Updates": ["earnings", "guidance", "profit warning", "quarterly report"],
        "Mergers and Acquisitions": ["acquisition", "merger", "purchase", "sale"],
        "Litigation": ["lawsuit", "filed suit", "settled"],
        "Bankruptcy": ["bankruptcy", "chapter 11", "restructure"],
        "Product Announcements": ["product launch", "new product", "discontinued"],
        "Regulatory Changes": ["regulation", "compliance", "fined", "penalty"],
    }

    PENALTY = {
        "Executive Changes": -0.3,
        "Bankruptcy": -0.7,
        "Financial Update - profit warning": -0.4,
        "Financial Update - missed": -0.4,
        "Mergers and Acquisitions": +0.5,
        "Litigation": -0.4,
        "Product Announcements": +0.3,
        "Regulatory Changes": -0.3,
    }

    agent = Agent(
        name="SentimentAgent",
        instructions=f"""
        You are a sentiment analysis engine.
        Given the input text, return a JSON object with a single key 'sentiment'
        whose value is a float between -1 (very negative) and +1 (very positive).
        Explain which events you used to adjust sentiment.
        Use these Events: {EVENTS}
        Use these Penalties: {PENALTY}
        """
    )

    user_input = [{"role": "user", "content": content}]
    try:
        result = await Runner.run(agent, user_input)
        if isinstance(result.final_output, dict):
            return {"sentiment": str(result.final_output.get("sentiment", "N/A"))}
        else:
            return {"sentiment": str(result.final_output)}
    except Exception as e:
        return {"error": f"Execution failed: {str(e)}"}




# ─── Entrypoint ─────────────────────────────────────────────────────────────────


# Define relevant keywords per category
# Define relevant keywords per category
RELEVANT_KEYWORDS = {
    "Executive Changes": ["executive", "officer", "ceo", "cfo", "resign", "appointment", "management", "director"],
    "Financial Updates": ["revenue", "earnings", "profit", "loss", "guidance", "financial results", "income"],
    "Mergers and Acquisitions": ["merger", "acquisition", "buyout", "purchase", "deal", "consolidation"],
    "Litigation": ["litigation", "lawsuit", "legal proceedings", "settlement", "complaint"],
    "Bankruptcy": ["bankruptcy", "chapter 11", "insolvency", "restructuring"],
    "Product Announcements": ["launch", "product", "release", "innovation", "update"],
    "Regulatory Changes": ["regulation", "compliance", "sec", "doj", "ftc", "sanction", "enforcement"]
}

def identify_topics(text: str) -> list:
    """Return list of matched categories for a given section of text."""
    matches = []
    lower_text = text.lower()
    for category, keywords in RELEVANT_KEYWORDS.items():
        if any(kw in lower_text for kw in keywords):
            matches.append(category)
    return matches

@mcp.tool("getSECData", description="Given a company stock ticker get relevant data from SEC filings")
async def getSECData(ticker) -> Dict[str, str]:
    company = Company(ticker)

    form_items = {
        "8-K": ["1.01", "1.03", "2.01", "2.02", "5.02", "8.01"],
        "10-K": ["Item 1", "Item 1A", "Item 3", "Item 7"],
        "10-Q": ["Item 1", "Item 1A", "Item 3", "Item 7"],
    }

    extracted_data = []

    for form_type, items in form_items.items():
        try:
            filings_query = company.get_filings(form=form_type)
            if filings_query is None:
                continue

            filings = filings_query.latest(2)

            for filing in filings:
                try:
                    text = filing.text()
                    sections = []

                    if items:
                        for item in items:
                            pattern = re.compile(rf"(Item\s+{re.escape(item)}.*?)(?=Item\s+\d+|\Z)", re.DOTALL | re.IGNORECASE)
                            match = pattern.search(text)
                            if match:
                                item_text = match.group(1).strip()
                                matched_topics = identify_topics(item_text)
                                if matched_topics:
                                    sections.append({
                                        "Item": item,
                                        "Content": item_text,
                                        "Matched Topics": matched_topics
                                    })
                    else:
                        matched_topics = identify_topics(text)
                        if matched_topics:
                            sections.append({
                                "Item": "Full Text",
                                "Content": text.strip(),
                                "Matched Topics": matched_topics
                            })

                    if sections:
                        extracted_data.append({
                            "Form Type": form_type,
                            "Accession Number": filing.accession_number,
                            "Filing Date": filing.filing_date,
                            "Relevant Sections": sections
                        })

                except Exception as inner_err:
                    print(f"Error parsing filing: {inner_err}")

        except Exception as outer_err:
            print(f"Error with form {form_type}: {outer_err}")

    df = pd.DataFrame(extracted_data)
    df.to_csv("sec_filings_extracted_data.csv", index=False)

    return {"extracted_data": extracted_data[:5]}

if __name__ == "__main__":
    url = f"http://{args.host}:{args.port}/{name}/sse"
    print(f"Starting SSE at {url} …")
    mcp.run(transport="sse", host=args.host, port=args.port)
  