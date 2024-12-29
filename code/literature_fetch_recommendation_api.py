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
from utils import (add_paper_details, add_recommendations,
                   add_recommendations_to_positive_articles,
                   get_author_details, get_paper_details, update_h_index)


def print_divider():
    """Print a divider line for better readability"""
    print("\n" + "=" * 80 + "\n")


def extract_paper_id_from_url(url: str) -> str:
    """Extract paper ID from Semantic Scholar URL"""
    try:
        last_part = url.split("/")[-1]
        paper_id = last_part.split("?")[0]
        return paper_id
    except Exception as e:
        print(f"Error extracting paper ID from URL {url}: {e}")
        return None


def process_csv_file(csv_path: str, db: DatabaseManager):
    """Process the CSV file and store data in the database"""
    # Count total rows for progress tracking
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        total_rows = sum(1 for _ in csv.DictReader(f))

    print(f"Found {total_rows} papers to process")
    print_divider()

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, 1):
            try:
                print(f"Processing paper {row_num}/{total_rows}")

                # Process topic
                topic = row["Topic"].strip()
                print(f"Topic: {topic}")
                topic_id = db.insert_topic(topic)
                print(f"✓ Topic saved to database (ID: {topic_id})")

                # Extract paper ID from URL
                paper_id = extract_paper_id_from_url(row["URL"].strip())
                if not paper_id:
                    print(f"✗ Invalid URL: {row['URL']}")
                    print_divider()
                    continue

                print(f"Paper ID: {paper_id}")

                # Convert use_for_recommendation to boolean
                use_for_rec = str(row["Use"]).strip().lower()
                use_for_rec = use_for_rec in ["1", "true", "yes", "y"]
                print(f"Use for recommendations: {use_for_rec}")

                # Fetch paper details
                print("Fetching paper details from Semantic Scholar...")
                paper_data = get_paper_details([paper_id])[0]

                # Create Article object
                article = Article(paper_id, use_for_recommendation=use_for_rec)
                add_paper_details(article, paper_data)
                print(f"✓ Retrieved paper details: {article.info.title}")

                # Process authors
                print(f"Processing {len(paper_data['authors'])} authors...")
                for author_data in paper_data["authors"]:
                    author_id = author_data.get("authorId") or author_data["name"]
                    author = Author(
                        author_id=author_id, author_name=author_data["name"]
                    )
                    article.authors.append(author)
                print("✓ Authors processed")

                # Store in database
                print("Saving paper to database...")
                db.insert_paper(article)
                db.link_topic_paper(topic_id, paper_id, "positive", use_for_rec)
                print("✓ Paper and authors saved to database")

                # Process recommendations if needed
                if use_for_rec:
                    print("\nFetching paper recommendations...")
                    recommendations = add_recommendations_to_positive_articles(
                        paper_id, limit=10
                    )
                    print(f"Found {len(recommendations)} recommendations")

                    for rec_num, rec_paper_data in enumerate(recommendations, 1):
                        if rec_paper_data["publicationDate"] is None:
                            print(
                                f"Skipping recommendation {rec_num} - no publication date"
                            )
                            continue

                        print(
                            f"\nProcessing recommendation {rec_num}/{len(recommendations)}"
                        )
                        rec_paper = Article(rec_paper_data["paperId"])
                        add_paper_details(rec_paper, rec_paper_data)
                        print(f"✓ Recommendation title: {rec_paper.info.title}")

                        # Add recommendation authors
                        print(
                            f"Processing {len(rec_paper_data['authors'])} recommendation authors..."
                        )
                        for author_data in rec_paper_data["authors"]:
                            author_id = (
                                author_data.get("authorId") or author_data["name"]
                            )
                            author = Author(
                                author_id=author_id, author_name=author_data["name"]
                            )
                            rec_paper.authors.append(author)

                        # Store recommendation
                        print("Saving recommendation to database...")
                        db.insert_paper(rec_paper)
                        db.insert_recommendation(paper_id, rec_paper.article_id)
                        print("✓ Recommendation saved")

                print("\n✓ Successfully processed paper!")

            except Exception as e:
                print(f"\n✗ Error processing row {row_num}:")
                print(f"Error details: {e}")

            print_divider()


def main():
    try:
        # Initialize database connection
        print("Initializing database connection...")
        db = DatabaseManager()

        # Initialize data fetcher
        fetcher = DataFetcher(db)

        # Process CSV file
        csv_path = "../data/query.csv"
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV file not found at {csv_path}")

        print(f"\nStarting to process CSV file: {csv_path}")
        fetcher.process_papers(csv_path)
        print("Completed processing papers")

    except Exception as e:
        print(f"Error in main execution: {e}")


if __name__ == "__main__":
    main()
