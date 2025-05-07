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

async def testEdgar():
    # Test the EDGAR API
    company = Company("AAPL")
    print(company)
    try:
        filings = company.get_filings().latest(10)
        print(filings)
        filing8k = filings.filter(form="8-K")
        print(filing8k)
        filing10k = filings.filter(form="10-K")
        print(filing10k)
        filing10q = filings.filter(form="10-Q")
        print(filing10q)

        print(company.get_financials().income_statement())
    
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
    return ticker_news


@mcp.tool("analyze_stock_sentiment", description="Given a company stock ticker get information from SEC events to analyze the sentiment movement outputtng a number between +1 and -1")
async def analyze_sentiment_gpt():
    """ 1) get data from SEC on company filings
        2) detect event types from given list
        3) adjust sentiment based on event type
    """
    list = await get_8k_filings_tool()
    text =" ".join(list)

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
        Given an input text, return a JSON object with a single key 'sentiment' 
        whose value is a float between -1 (very negative) and +1 (very positive). 
        Output ONLY the JSON. Use the following template for detecting Events:
        {EVENTS} . Also the following penalties to adjust the sentiment {PENALTY}
        """
    
    user_prompt = f"Analyze the sentiment of this SEC filing excerpt:\n\n{text}"
    messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    print(f"running sentiment analysis with messages: {messages}")
    await run_agent(messages)

async def run_agent(messages):
    set_default_openai_key(os.environ["OPENAI_API_KEY"])
    model_settings = ModelSettings( max_tokens=1000, temperature=0.7)
    agent = Agent(
        name="Assistant",
        instructions="Use the available MCP tools to answer the questions.",
        model_settings=model_settings,
    )

    examples = messages 
    for msg in examples:
        print(f"\n>> Query: {msg}")
        resp = await Runner.run(starting_agent=agent, input=msg)
        print("Sentiment Admustment: ", resp.final_output)

# ─── Entrypoint ─────────────────────────────────────────────────────────────────
    

if __name__ == "__main__":
    asyncio.run(testEdgar())
  