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
from database import DatabaseManager
from jinja2 import Environment, FileSystemLoader
from utils import (add_paper_details, add_recommendations,
                   add_recommendations_to_positive_articles,
                   get_author_details, get_paper_details, update_h_index)


def extract_paper_id_from_url(url: str) -> str:
    """Extract paper ID from Semantic Scholar URL"""
    try:
        # Split by '/' and get the last part that contains the ID
        last_part = url.split("/")[-1]
        # Remove any URL parameters
        paper_id = last_part.split("?")[0]
        return paper_id
    except Exception as e:
        print(f"Error extracting paper ID from URL {url}: {e}")
        return None


def process_csv_file(csv_path: str, db: DatabaseManager):
    """Process the CSV file and store data in the database"""
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Process topic
                topic = row["Topic"].strip()
                topic_id = db.insert_topic(topic)

                # Extract paper ID from URL
                paper_id = extract_paper_id_from_url(row["URL"].strip())
                if not paper_id:
                    print(f"Skipping row due to invalid URL: {row}")
                    continue

                # Convert use_for_recommendation to boolean
                use_for_rec = str(row["Use"]).strip().lower()
                use_for_rec = use_for_rec in ["1", "true", "yes", "y"]

                # Create Article object and fetch details
                article = Article(paper_id, use_for_recommendation=use_for_rec)
                paper_data = get_paper_details([paper_id])[0]
                add_paper_details(article, paper_data)

                # Add authors
                for author_data in paper_data["authors"]:
                    author_id = author_data.get("authorId") or author_data["name"]
                    author = Author(
                        author_id=author_id, author_name=author_data["name"]
                    )
                    article.authors.append(author)

                # Store in database
                db.insert_paper(article)
                db.link_topic_paper(topic_id, paper_id, "positive", use_for_rec)

                print(f"Processed paper: {paper_id} for topic: {topic}")

                # Process recommendations if needed
                if use_for_rec:
                    print(f"Fetching recommendations for paper: {paper_id}")
                    recommendations = add_recommendations_to_positive_articles(
                        paper_id, limit=10
                    )
                    for rec_paper_data in recommendations:
                        if rec_paper_data["publicationDate"] is None:
                            continue

                        rec_paper = Article(rec_paper_data["paperId"])
                        add_paper_details(rec_paper, rec_paper_data)

                        # Add recommendation authors
                        for author_data in rec_paper_data["authors"]:
                            author_id = (
                                author_data.get("authorId") or author_data["name"]
                            )
                            author = Author(
                                author_id=author_id, author_name=author_data["name"]
                            )
                            rec_paper.authors.append(author)

                        # Store recommendation
                        db.insert_paper(rec_paper)
                        db.insert_recommendation(paper_id, rec_paper.article_id)

            except Exception as e:
                print(f"Error processing row: {row}")
                print(f"Error details: {e}")
                continue


def main():
    try:
        # Initialize database
        db = DatabaseManager()

        # Process CSV file
        csv_path = "../data/query.csv"  # Update path as needed
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV file not found at {csv_path}")

        print(f"Starting to process CSV file: {csv_path}")
        process_csv_file(csv_path, db)
        print("Completed processing CSV file")

    except Exception as e:
        print(f"Error in main execution: {e}")


if __name__ == "__main__":
    main()
