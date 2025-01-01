#!/usr/bin/env python3

import time
from typing import Dict, List

from article import Article
from author import Author
from database import DatabaseManager
from utils import get_author_details, update_h_index


class HIndexUpdater:
    def __init__(self):
        self.db = DatabaseManager()

    def get_all_papers(self) -> List[Dict]:
        """Get all papers with their authors from the database"""
        conn = self.db.get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT 
                p.*,
                GROUP_CONCAT(pa.author_id) as author_ids,
                GROUP_CONCAT(a.name) as author_names
            FROM papers p
            LEFT JOIN paper_authors pa ON p.id = pa.paper_id
            LEFT JOIN authors a ON pa.author_id = a.id
            GROUP BY p.id
        """
        )

        papers = cursor.fetchall()
        cursor.close()
        conn.close()
        return papers

    def update_paper_h_indices(self):
        """Update h-index for all papers in the database"""
        papers = self.get_all_papers()
        total_papers = len(papers)
        print(f"Found {total_papers} papers to update")

        batch_size = 5  # Process papers in small batches to manage API calls
        for i in range(0, total_papers, batch_size):
            batch = papers[i : i + batch_size]
            print(
                f"\nProcessing batch {i//batch_size + 1}/{(total_papers + batch_size - 1)//batch_size}"
            )

            for paper_data in batch:
                try:
                    print(f"\nProcessing paper: {paper_data['title'][:50]}...")

                    # Create Article object
                    article = Article(paper_data["id"])
                    article.info.title = paper_data["title"]
                    article.info.abstract = paper_data["abstract"]
                    article.info.url = paper_data["url"]
                    article.info.journal = paper_data["journal"]
                    article.info.publication_date = paper_data["publication_date"]
                    article.info.citation_count = paper_data["citation_count"]

                    # Process authors
                    if paper_data["author_ids"]:
                        author_ids = paper_data["author_ids"].split(",")
                        author_names = paper_data["author_names"].split(",")

                        # Create Author objects
                        for author_id, author_name in zip(author_ids, author_names):
                            author = Author(
                                author_id=author_id, author_name=author_name
                            )
                            article.authors.append(author)

                        # Get author details and update h-index
                        print(f"Fetching details for {len(author_ids)} authors...")
                        author_details = get_author_details(author_ids)

                        # Update h-index
                        old_h_index = paper_data["h_index"]
                        new_h_index = update_h_index(article, author_details)

                        print(f"H-index updated: {old_h_index} -> {new_h_index}")

                        # Store updated paper
                        self.db.insert_paper(article)
                    else:
                        print("No authors found for this paper")

                except Exception as e:
                    print(f"Error processing paper {paper_data['id']}: {e}")
                    continue

            # Add a small delay between batches to respect API rate limits
            if i + batch_size < total_papers:
                print("Waiting before next batch...")
                time.sleep(2)


def main():
    try:
        print("Starting h-index update process...")
        updater = HIndexUpdater()
        updater.update_paper_h_indices()
        print("\nCompleted h-index update process")

    except Exception as e:
        print(f"Error in main execution: {e}")
        raise


if __name__ == "__main__":
    main()
