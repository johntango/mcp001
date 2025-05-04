import os
import spacy
import pandas

from edgar import *
from loguru import logger
from flask import Request, Flask
from datetime import datetime
from pandas_gbq import to_gbq, read_gbq
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from demo_secrets import (
    project_id, # Your Google Cloud Project ID
    bigquery_dataset, # Your BigQuery Dataset ID
)

os.environ["GCLOUD_PROJECT"] = project_id

set_identity("Carsten Savage carstensavageconsulting@gmail.com")

app = Flask(__name__)


def analyze_sentiment(text):
    nlp = spacy.load("en_core_web_sm")

    vader = SentimentIntensityAnalyzer()

    # Lists of 8-K events for detection
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

    # Detect events
    def extract_8k_events(text, events_dict):
        doc = nlp(text)
        detected_events = set()

        for ent in doc.ents:
            for event_type, keywords in events_dict.items():
                if any(keyword in text.lower() for keyword in keywords):
                    detected_events.add(
                        event_type
                    )  # Use add() to avoid duplicates

        logger.debug(detected_events)

        return list(detected_events)

    def get_sentiment_vader(text):
        sentiment = vader.polarity_scores(text)
        return sentiment

    def adjust_sentiment_for_8k_events(text, events, base_sentiment):
        # Initialize weight adjustments
        sentiment_adjustment = 0

        # Apply weights for each event type detected
        for event in events:
            if event == "Executive Changes":
                sentiment_adjustment -= 0.3
            elif event == "Bankruptcy":
                sentiment_adjustment -= 0.7
            elif event == "Financial Updates":
                # Mixed - can be positive or negative based on context
                if (
                    "profit warning" in text.lower()
                    or "missed" in text.lower()
                ):
                    sentiment_adjustment -= 0.4
                else:
                    sentiment_adjustment += 0.2
            elif event == "Mergers and Acquisitions":
                sentiment_adjustment += 0.5
            elif event == "Litigation":
                sentiment_adjustment -= 0.4
            elif event == "Product Announcements":
                sentiment_adjustment += 0.3
            elif event == "Regulatory Changes":
                sentiment_adjustment -= 0.3

        # Adjust base sentiment score
        final_sentiment = base_sentiment["compound"] + sentiment_adjustment

        # Ensure sentiment stays within bounds [-1, 1]
        final_sentiment = max(min(final_sentiment, 1), -1)

        return final_sentiment

    # Step 4: Detect Events and Apply Adjustments
    detected_events = extract_8k_events(text, EVENTS)
    vader_sentiment = get_sentiment_vader(text)
    adjusted_sentiment = adjust_sentiment_for_8k_events(
        text, detected_events, vader_sentiment
    )

    return adjusted_sentiment


def get_8k_filings():
    morning_movers = []

    # List of stocks
    spx_morning_movers = ["PANW", "TSLA"]

    morning_movers.extend(spx_morning_movers)

    morning_movers = list(set(morning_movers))

    logger.debug(morning_movers)

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

        adjusted_8k_sentiment = analyze_sentiment(clean_text)

        # Extract the filing date from the 8-K.
        date_pattern = (
            r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December"
            r")\s+\d{1,2},\s+\d{4}\b"
        )

        dates = re.findall(date_pattern, filing_text)

        filing_date = datetime.strptime(dates[0], "%B %d, %Y").date()

        ticker_news.append(
            {
                "ticker": ticker,
                "filing_date": filing_date,
                "news": clean_text,
                "adjusted_8k_sentiment": adjusted_8k_sentiment,
            }
        )

    ticker_news_frame = pandas.DataFrame(ticker_news)

    return ticker_news_frame


@app.route("/oni")
def oni():
    ticker_news_frame = get_8k_filings()

    # Query existing data from the BigQuery table
    retrieve_all_from_latest_stock_news_query = f"""
    SELECT * FROM `{bigquery_dataset}.latest_stock_news`
    """

    existing_latest_stock_news = read_gbq(
        retrieve_all_from_latest_stock_news_query, project_id=project_id
    )

    comparison_news_frame = ticker_news_frame.merge(
        existing_latest_stock_news,
        how="left",
        on=["ticker", "filing_date"],
        suffixes=["_current", "_existing"],
    )

    current_news_frame = comparison_news_frame.query(
        "news_current.notnull()"
    ).query("news_existing.isnull()")

    current_news_frame = current_news_frame[
        [
            "ticker",
            "filing_date",
            "news_current",
            "adjusted_8k_sentiment_current",
        ]
    ]

    current_news_frame = current_news_frame.rename(
        columns={
            "news_current": "news",
            "adjusted_8k_sentiment_current": "adjusted_8k_sentiment",
        }
    )

    to_gbq(
        current_news_frame,
        f"{bigquery_dataset}.latest_stock_news",
        project_id=project_id,
        if_exists="append",
    )

    logger.debug(current_news_frame)

    return "Done!"


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))