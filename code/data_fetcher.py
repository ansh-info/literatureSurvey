import os
import time
from typing import Dict, List

import requests
from article import Article
from author import Author
from database import DatabaseManager
from utils import (add_paper_details, add_recommendations_to_positive_articles,
                   create_session, get_author_details, get_paper_details,
                   update_h_index)


class DataFetcher:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.session = create_session()

    # For just Main Papers(csv)
    def process_paper(
        self,
        paper_data: Dict,
        topic_id: int,
        use_for_rec: bool,
        paper_type: str = "positive",
    ):
        """Process a single paper with all related data"""
        try:
            paper_id = paper_data["paperId"]
            print(f"Processing paper {paper_id}")

            # Step 1: Create article object and add basic details
            article = Article(paper_id, use_for_recommendation=use_for_rec)
            add_paper_details(article, paper_data)

            # Step 2: Store the paper first
            print("Storing paper basic details...")
            try:
                self.db.insert_paper(article)
            except Exception as e:
                print(f"Error storing paper: {e}")
                return None

            # Step 3: Process authors in smaller batches
            print("Processing authors...")
            authors = []
            author_batch_size = 4

            author_data_list = paper_data.get("authors", [])
            for i in range(0, len(author_data_list), author_batch_size):
                batch = author_data_list[i : i + author_batch_size]
                print(f"Processing author batch {i//author_batch_size + 1}")

                for idx, author_data in enumerate(batch, i + 1):
                    try:
                        author_id = author_data.get("authorId") or author_data.get(
                            "name"
                        )
                        if not author_id:
                            continue

                        author = Author(
                            author_id=author_id, author_name=author_data.get("name")
                        )
                        authors.append(author)

                        print(f"Storing author {idx}: {author.author_name}")
                        self.db.insert_author(author)
                        self.db.link_paper_author(paper_id, author_id, idx)

                    except Exception as e:
                        print(f"Error processing author {idx}: {e}")
                        continue

                time.sleep(1)  # Small delay between batches

            article.authors = authors

            # Step 4: Update h-index in batches
            if article.authors:
                print("Fetching author details...")
                author_ids = [a.author_id for a in article.authors]

                for i in range(0, len(author_ids), author_batch_size):
                    batch_ids = author_ids[i : i + author_batch_size]
                    print(f"Fetching details for authors {i+1} to {i+len(batch_ids)}")
                    author_details = get_author_details(batch_ids)
                    time.sleep(1)  # Rate limiting

                    # Update each author in the batch
                    for author_detail in author_details:
                        if author_detail:
                            self.update_single_author(author_detail)

                # Final h-index update for the paper
                update_h_index(article, author_details)
                self.db.insert_paper(article)

            # Step 5: Link to topic
            print("Linking paper to topic...")
            self.db.link_topic_paper(topic_id, paper_id, paper_type, use_for_rec)

            # Step 6: Process and store recommendations
            if use_for_rec and paper_type == "positive":
                print("Fetching paper recommendations...")
                recommended_papers = add_recommendations_to_positive_articles(paper_id)

                if recommended_papers:
                    print(f"Found {len(recommended_papers)} recommendations")
                    for idx, rec_paper in enumerate(recommended_papers, 1):
                        try:
                            # Skip if paper ID is missing
                            if not rec_paper.get("paperId"):
                                continue

                            # Create article object for recommendation
                            rec_article = Article(rec_paper["paperId"])
                            add_paper_details(rec_article, rec_paper)

                            # First store the recommended paper
                            try:
                                print(f"Storing recommended paper {idx}...")
                                # Store paper without h-index calculation
                                self.db.insert_paper(rec_article)

                                # Process and store authors (without h-index)
                                for author_idx, author_data in enumerate(
                                    rec_paper.get("authors", []), 1
                                ):
                                    author_id = author_data.get(
                                        "authorId"
                                    ) or author_data.get("name")
                                    if not author_id:
                                        continue

                                    author = Author(
                                        author_id=author_id,
                                        author_name=author_data.get("name"),
                                    )
                                    self.db.insert_author(author)
                                    self.db.link_paper_author(
                                        rec_article.article_id, author_id, author_idx
                                    )

                                # Store the recommendation relationship
                                print(
                                    f"Storing recommendation {idx}: {rec_article.info.title}"
                                )
                                self.db.insert_paper_recommendations(
                                    paper_id, rec_article.article_id, idx
                                )

                            except Exception as e:
                                print(
                                    f"Warning: Could not store recommended paper: {e}"
                                )
                                continue

                        except Exception as e:
                            print(f"Error processing recommendation {idx}: {e}")
                            continue
                else:
                    print("No recommendations found")

            return article

        except Exception as e:
            print(f"Error details: {str(e)}")
            return None

    # For all the papers(csv and recommended_papers)
    def process_paper(
        self,
        paper_data: Dict,
        topic_id: int,
        use_for_rec: bool,
        paper_type: str = "positive",
    ):
        """Process a single paper with all related data"""
        try:
            paper_id = paper_data["paperId"]
            print(f"Processing paper {paper_id}")

            # Step 1: Create article object and add basic details
            article = Article(paper_id, use_for_recommendation=use_for_rec)
            add_paper_details(article, paper_data)

            # Step 2: Store the paper first
            print("Storing paper basic details...")
            try:
                self.db.insert_paper(article)
            except Exception as e:
                print(f"Error storing paper: {e}")
                return None

            # Step 3: Process authors in smaller batches
            print("Processing authors...")
            authors = []
            author_batch_size = 4

            author_data_list = paper_data.get("authors", [])
            for i in range(0, len(author_data_list), author_batch_size):
                batch = author_data_list[i : i + author_batch_size]
                print(f"Processing author batch {i//author_batch_size + 1}")

                for idx, author_data in enumerate(batch, i + 1):
                    try:
                        author_id = author_data.get("authorId") or author_data.get(
                            "name"
                        )
                        if not author_id:
                            continue

                        author = Author(
                            author_id=author_id, author_name=author_data.get("name")
                        )
                        authors.append(author)

                        print(f"Storing author {idx}: {author.author_name}")
                        self.db.insert_author(author)
                        self.db.link_paper_author(paper_id, author_id, idx)

                    except Exception as e:
                        print(f"Error processing author {idx}: {e}")
                        continue

                time.sleep(1)  # Small delay between batches

            article.authors = authors

            # Step 4: Update h-index in batches
            if article.authors:
                print("Fetching author details...")
                author_ids = [a.author_id for a in article.authors]

                for i in range(0, len(author_ids), author_batch_size):
                    batch_ids = author_ids[i : i + author_batch_size]
                    print(f"Fetching details for authors {i+1} to {i+len(batch_ids)}")
                    author_details = get_author_details(batch_ids)
                    time.sleep(1)  # Rate limiting

                    # Update each author in the batch
                    for author_detail in author_details:
                        if author_detail:
                            self.update_single_author(author_detail)

                # Final h-index update for the paper
                update_h_index(article, author_details)
                self.db.insert_paper(article)

            # Step 5: Link to topic
            print("Linking paper to topic...")
            self.db.link_topic_paper(topic_id, paper_id, paper_type, use_for_rec)

            # Step 6: Process and store recommendations
            if use_for_rec and paper_type == "positive":
                print("Fetching paper recommendations...")
                recommended_papers = add_recommendations_to_positive_articles(paper_id)

                if recommended_papers:
                    print(f"Found {len(recommended_papers)} recommendations")
                    for idx, rec_paper in enumerate(recommended_papers, 1):
                        try:
                            # Skip if paper ID is missing
                            if not rec_paper.get("paperId"):
                                continue

                            # Create article object for recommendation
                            rec_article = Article(rec_paper["paperId"])
                            add_paper_details(rec_article, rec_paper)

                            # First store the recommended paper
                            try:
                                print(f"Storing recommended paper {idx}...")
                                self.db.insert_paper(rec_article)
                            except Exception as e:
                                print(
                                    f"Warning: Could not store recommended paper: {e}"
                                )
                                continue

                            # Then process authors for recommended paper
                            print(f"Processing authors for recommendation {idx}...")
                            authors = []
                            author_data_list = rec_paper.get("authors", [])

                            for author_idx, author_data in enumerate(
                                author_data_list, 1
                            ):
                                try:
                                    author_id = author_data.get(
                                        "authorId"
                                    ) or author_data.get("name")
                                    if not author_id:
                                        continue

                                    author = Author(
                                        author_id=author_id,
                                        author_name=author_data.get("name"),
                                    )
                                    authors.append(author)

                                    # Store author and link to paper
                                    self.db.insert_author(author)
                                    self.db.link_paper_author(
                                        rec_article.article_id, author_id, author_idx
                                    )

                                except Exception as e:
                                    print(
                                        f"Error processing author {author_idx} for recommendation {idx}: {e}"
                                    )
                                    continue

                            rec_article.authors = authors

                            # Update h-index for recommended paper
                            if rec_article.authors:
                                author_ids = [a.author_id for a in rec_article.authors]
                                author_details = get_author_details(author_ids)

                                # Update each author's details
                                for author_detail in author_details:
                                    if author_detail:
                                        self.update_single_author(author_detail)

                                # Calculate and update h-index
                                update_h_index(rec_article, author_details)
                                self.db.insert_paper(rec_article)

                            # Store the recommendation relationship
                            print(
                                f"Storing recommendation {idx}: {rec_article.info.title} (h-index: {rec_article.info.h_index})"
                            )
                            self.db.insert_paper_recommendations(
                                paper_id, rec_article.article_id, idx
                            )

                        except Exception as e:
                            print(f"Error processing recommendation {idx}: {e}")
                            continue
                else:
                    print("No recommendations found")

            return article

        except Exception as e:
            print(f"Error details: {str(e)}")
            return None

    def update_single_author(self, author_detail):
        """Update a single author's details"""
        try:
            author = Author(
                author_id=author_detail["authorId"],
                author_name=author_detail.get("name"),
                h_index=author_detail.get("hIndex"),
                citation_count=author_detail.get("citationCount"),
            )
            self.db.insert_author(author)
        except Exception as e:
            print(f"Error updating author {author_detail.get('authorId')}: {e}")
