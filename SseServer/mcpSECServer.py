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
async def testEdgar():
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

        return {'Sentiment adjustment: ': 0.5}

    except AttributeError:  
        pass
     
    


@mcp.tool("get_8k_filings", description="Get 8k filings for a list of companies")
async def get_8k_filings_tool():

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
    return {"textticker_news" : ticker_news}


@mcp.tool("analyze_stock_sentiment", description="Given a company stock ticker get information from SEC events to analyze the sentiment movement outputtng a number between +1 and -1")
async def analyze_sentiment_gpt():
    """ 1) get data from SEC on company filings
        2) detect event types from given list
        3) adjust sentiment based on event type
    """
    # read extracted filings from file
    df = pd.read_csv("sec_filings_extracted_data.csv")
    if df.empty:
        df = await get_8k_filings_tool()
    text =df.tolist()
    EVENTS = {
        "Executive Changes": [
            "resigned",
            "appointed",
            "left the company",
            "terminated",
        ],
        "Financial Updates": [
            "earnings",
            "guidance",
            "profit warning",
            "quarterly report",
        ],
        "Mergers and Acquisitions": [
            "acquisition",
            "merger",
            "purchase",
            "sale",
        ],
        "Litigation": ["lawsuit", "filed suit", "settled"],
        "Bankruptcy": ["bankruptcy", "chapter 11", "restructure"],
        "Product Announcements": [
            "product launch",
            "new product",
            "discontinued",
        ],
        "Regulatory Changes": ["regulation", "compliance", "fined", "penalty"],
    }
    PENALTY = {"Executive Changes": -0.3,
                "Bankruptcy": -0.7,
                "Financial Update - profit warning" : -0.4,
                "Financial Update - missed" : -0.4,
                "Mergers and Acquisitions": +0.5,
                "Litigation": -0.4,
                "Product Announcements": +0.3,
                "Regulatory Changes": -0.3
    }
        


    system_prompt = f"""
        You are a sentiment analysis engine. 
        Given the input text, return a JSON object with a single key 'sentiment' 
        whose value is a float between -1 (very negative) and +1 (very positive). 
        Output ONLY the JSON. Use the following template for detecting Events:
        {EVENTS} . Also the following penalties to adjust the sentiment {PENALTY}
        """
    
    user_prompt = f"Analyze the sentiment of this SEC filing data:\n\n{text}"
    messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    print(f"running sentiment analysis with messages: {messages}")
    sentiment = await run_agent(messages)

async def run_agent(messages):
    set_default_openai_key(os.environ["OPENAI_API_KEY"])
    model_settings = ModelSettings( max_tokens=1000, temperature=0.7)
    agent = Agent(
        name="Assistant",
        instructions="Use the data extracted from SEC filings to estimate the sentiment as a number between -1 and +1",
        model_settings=model_settings,
    )

    examples = messages 
    for msg in examples:
        print(f"\n>> Query: {msg}")
        resp = await Runner.run(starting_agent=agent, input=msg)
        print("Sentiment Admustment: ", resp.final_output)
    
    return {"sentiment": resp.final_output}

# ─── Entrypoint ─────────────────────────────────────────────────────────────────
@mcp.tool("getSECData", description="Given a company stock ticker get relevant event data from SEC filings")
async def getSECData():
    # Define the target company
    company = Company("MSFT")  # Microsoft Corporation

    # Define forms and the items of interest
    form_items = {
        "8-K": ["1.01", "1.03", "2.01", "2.02", "5.02", "8.01"],
        "10-K": ["Item 1", "Item 1A", "Item 3", "Item 7"],
        "10-Q": ["Item 1", "Item 1A", "Item 3", "Item 7"],
        "S-4": [],
        "SC 13D": [],
        "SC TO": []
    }
    form_items =  {"10-K": ["Item 1", "Item 1A", "Item 3", "Item 7"]}

    # Store the extracted data
    extracted_data = []

    # Iterate through each form type
    for form_type, items in form_items.items():
        try:
            # Retrieve filings and check for None
            filings_query = company.get_filings(form=form_type)
            if filings_query is None:
                print(f"No filings found for form {form_type}")
                continue

            filings = filings_query.latest(5)  # Get last 5 filings

            for filing in filings:
                try:
                    text = filing.text()

                    # Extract item sections or full text
                    sections = {}
                    if items != []:
                        for item in items:
                            pattern = re.compile(rf"(Item\s+{re.escape(item)}.*?)(?=Item\s+\d+|\Z)", re.DOTALL | re.IGNORECASE)
                            match = pattern.search(text)
                            if match:
                                sections[item] = match.group(1).strip()
                    else:
                        sections["Full Text"] = text.strip()

                    extracted_data.append({
                        "Form Type": form_type,
                        "Accession Number": filing.accession_number,
                        "Filing Date": filing.filing_date,  # Correct attribute
                        "Sections": sections
                    })

                except Exception as inner_err:
                    print(f"Error parsing a {form_type} filing: {inner_err}")

        except Exception as outer_err:
            print(f"An error occurred while processing form {form_type}: {outer_err}")

    # Convert to DataFrame
    df = pd.DataFrame(extracted_data)

    # Preview or export
    print(df.head())
    df.to_csv("sec_filings_extracted_data.csv", index=False)
    return {"extracted_data": "Hello World"}


if __name__ == "__main__":
    url = f"http://{args.host}:{args.port}/{name}/sse"
    print(f"Starting SSE at {url} …")
    mcp.run(transport="sse", host=args.host, port=args.port)
  