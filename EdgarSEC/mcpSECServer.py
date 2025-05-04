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

from edgar import *
from loguru import logger
from datetime import datetime
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    # Create the FastMCP server _with_ host/port settings

name = "SEClookup"
# put this in SECTRETS
SEC_EDGAR_USER_AGENT="John Williams (jrwtango@gmail.com)"
set_identity(SEC_EDGAR_USER_AGENT)

mcp = FastMCP(name=name, port=8000, host="localhost")

@mcp.tool("hello",description="Given a person's name return Hello <name>" )
def hello(params: dict):
    name = params.get("name")
    if not name:
        raise ValueError("Parameter 'name' is required")
    return {"hello": f"Hello {name}"}   

@mcp.tool("get_8k_filings", description="Get 8k filings for a list of companies")
def get_8k_filings_tool():

    morning_movers = [ ]

    # List of stocks
    spx_morning_movers = ["PANW", "TSLA","MSFT"]

    morning_movers.extend(spx_morning_movers)

    morning_movers = list(set(morning_movers))

    ticker_news = []

    for ticker in morning_movers:
        try:
            latest_filing = Company(ticker).get_filings(form="8-K").latest(1)
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

    return ticker_news


@mcp.tool("analyze_stock_sentiment", description="Given a company stock ticker get information from SEC events to analyze the sentiment movement outputtng a number between +1 and -1")
async def analyze_sentiment_gpt():
    """ 1) get data from SEC on company filings
        2) detect event types from given list
        3) adjust sentiment based on event type
    """
    list = get_8k_filings_tool()
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
    
    await run_agent(messages)

async def run_agent(messages ):
    set_default_openai_key(os.environ["OPENAI_API_KEY"])
    model_settings = ModelSettings( max_tokens=1000, temperature=0.7)
    agent = Agent(
        name="Assistant",
        instructions="Use the available MCP tools to answer the questions.",
        model_settings=model_settings,
    )

    examples = [ messages ]
    for msg in examples:
        print(f"\n>> Query: {msg}")
        resp = await Runner.run(starting_agent=agent, input=msg)
        print("Sentiment Admustment: ", resp.final_output)

# ─── Entrypoint ─────────────────────────────────────────────────────────────────
    

if __name__ == "__main__":
    mcp.run()