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


def process_csv_file(csv_path: str, db: DatabaseManager):
    """Process the CSV file and store data in the database"""
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Process topic
            topic = row["Topic"].strip()
            topic_id = db.insert_topic(topic)

            # Get paper ID
            paper_id = row["PaperId"].strip()
            if "/" in paper_id:  # Handle full URLs
                paper_id = paper_id.split("/")[-1].split("?")[0]

            # Convert use_for_recommendation to boolean
            use_for_rec = str(row["UseForRecommendation"]).strip().lower()
            use_for_rec = use_for_rec in ["1", "true", "yes", "y"]

            # Create Article object and fetch details
            article = Article(paper_id, use_for_recommendation=use_for_rec)
            paper_data = get_paper_details([paper_id])[0]
            add_paper_details(article, paper_data)

            # Add authors
            for author_data in paper_data["authors"]:
                author_id = author_data.get("authorId") or author_data["name"]
                author = Author(author_id=author_id, author_name=author_data["name"])
                article.authors.append(author)

            # Store in database
            db.insert_paper(article)
            db.link_topic_paper(topic_id, paper_id, "positive", use_for_rec)

            # Process recommendations if needed
            if use_for_rec:
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
                        author_id = author_data.get("authorId") or author_data["name"]
                        author = Author(
                            author_id=author_id, author_name=author_data["name"]
                        )
                        rec_paper.authors.append(author)

                    # Store recommendation
                    db.insert_paper(rec_paper)
                    db.insert_recommendation(paper_id, rec_paper.article_id)


def main():
    # Initialize database
    db = DatabaseManager()

    # Process CSV file
    csv_path = "../data/query.csv"  # Update path as needed
    process_csv_file(csv_path, db)


if __name__ == "__main__":
    main()
