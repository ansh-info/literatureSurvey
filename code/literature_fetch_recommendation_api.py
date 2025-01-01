#!/usr/bin/env python3

"""
This script demonstrates how to use the Semantic Scholar API to search for papers 
and retrieve their details.
"""


import csv
import os
import time

import pandas as pd
from article import Article
from author import Author
from data_fetcher import DataFetcher
from database import DatabaseManager
from jinja2 import Environment, FileSystemLoader
from topic import Topic
from utils import (add_negative_articles, add_paper_details,
                   add_recommendations,
                   add_recommendations_to_positive_articles,
                   add_recommended_articles_to_zotero, get_paper_details,
                   metrics_over_time_js, read_yaml, update_h_index,
                   update_paper_details, write_yaml)


def process_csv_file(csv_path: str, db: DatabaseManager):
    """Process CSV file with complete data pipeline"""
    fetcher = DataFetcher(db)

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        df = pd.read_csv(f)
        total_papers = len(df)
        print(f"Found {total_papers} papers to process")

        for index, row in df.iterrows():
            try:
                print(f"\nProcessing paper {index + 1}/{total_papers}")

                # Process topic
                topic = row["Topic"].strip()
                topic_id = db.insert_topic(topic)
                print(f"✓ Topic saved: {topic}")

                # Get paper usage and type
                use_for_rec = str(row["Use"]).strip() == "1"
                paper_type = row.get("Type", "positive").strip().lower()
                if paper_type not in ["positive", "negative"]:
                    paper_type = "positive"

                # Extract paper ID
                paper_id = row["URL"].strip().split("/")[-1].split("?")[0]
                print(f"Processing paper ID: {paper_id}")

                # Fetch paper details
                paper_data = get_paper_details([paper_id])[0]
                if not paper_data:
                    print(f"✗ Could not fetch details for paper {paper_id}")
                    continue

                # Process paper with all related data
                article = fetcher.process_paper(
                    paper_data, topic_id, use_for_rec, paper_type
                )

                if article:
                    print(f"✓ Successfully processed: {article.info.title}")
                    print(f"  Authors: {len(article.authors)}")
                    print(f"  H-index: {article.info.h_index}")
                else:
                    print(f"✗ Failed to process paper {paper_id}")

            except Exception as e:
                print(f"Error processing row {index + 1}: {e}")
                continue


def main():
    try:
        # Initialize database connection
        print("Initializing database connection...")
        db = DatabaseManager()

        # Construct the path to the CSV file
        base_dir = os.path.dirname(
            os.path.abspath(__file__)
        )  # Directory of the current script
        csv_path = os.path.join(
            base_dir, "../data/query.csv"
        )  # Adjust relative path accordingly

        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV file not found at {csv_path}")

        print(f"\nStarting to process CSV file: {csv_path}")
        process_csv_file(csv_path, db)
        print("\nCompleted processing papers")

    except Exception as e:
        print(f"Error in main execution: {e}")
        raise


if __name__ == "__main__":
    main()
