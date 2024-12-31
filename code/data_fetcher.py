import csv
import os
import time
from typing import Dict, List

import requests
from article import Article
from author import Author
from database import DatabaseManager
from utils import (add_paper_details, add_recommendations_to_positive_articles,
                   create_session, get_author_details, get_paper_details,
                   handle_api_request, update_h_index)


class DataFetcher:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.session = create_session()

    def extract_paper_id(self, url: str) -> str:
        """Extract paper ID from Semantic Scholar URL"""
        try:
            return url.split("/")[-1].split("?")[0]
        except Exception as e:
            print(f"Error extracting paper ID from URL {url}: {e}")
            return None

    def read_csv(self, file_path: str) -> List[Dict]:
        """Read and parse the CSV file"""
        papers = []
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                paper_id = self.extract_paper_id(row["URL"].strip())
                if paper_id:
                    papers.append(
                        {
                            "topic": row["Topic"].strip(),
                            "use_for_recommendation": row["Use"].strip() == "1",
                            "paper_id": paper_id,
                        }
                    )
        return papers

    def fetch_paper_details(self, paper_id: str) -> Dict:
        """Fetch paper details from Semantic Scholar API"""
        endpoint = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}"
        params = {
            "fields": "paperId,url,authors,journal,title,abstract,publicationDate,citationCount"
        }
        print(f"Fetching details for paper {paper_id}")
        return handle_api_request(self.session, endpoint, params=params)


    def fetch_author_details(self, author_ids: List[str]) -> List[Dict]:
        """Fetch author details from Semantic Scholar API"""
        endpoint = "https://api.semanticscholar.org/graph/v1/author/batch"
        params = {"fields": "authorId,name,hIndex,citationCount"}
        
        # Process in batches of 100 to avoid API limits
        author_details = []
        for i in range(0, len(author_ids), 100):
            batch_ids = author_ids[i:i+100]
            data = {"ids": batch_ids}
            
            response = handle_api_request(
                self.session, 
                endpoint, 
                params=params, 
                json=data,
                method="POST"
            )
            
            if response:
                author_details.extend(response)
                
            time.sleep(1)  # Rate limiting
            
        return author_details

    def process_authors(self, paper_id: str, authors_data: List[Dict], fetch_details: bool = True):
        """Process and store author information"""
        authors = []
        for idx, author_data in enumerate(authors_data, 1):
            author_id = author_data.get('authorId') or author_data.get('name')
            if not author_id:
                continue

            # Create author object
            author = Author(
                author_id=author_id,
                author_name=author_data.get('name')
            )
            
            # Store in database
            self.db.insert_author(author)
            self.db.link_paper_author(paper_id, author_id, idx)
            authors.append(author)

        if fetch_details and authors:
            # Fetch additional author details
            author_ids = [a.author_id for a in authors]
            author_details = get_author_details(author_ids)
            
            # Update authors with details
            for author_detail in author_details:
                if author_detail and author_detail.get('authorId'):
                    author = Author(
                        author_id=author_detail['authorId'],
                        author_name=author_detail.get('name'),
                        h_index=author_detail.get('hIndex'),
                        citation_count=author_detail.get('citationCount')
                    )
                    self.db.insert_author(author)

        return authors

    def process_paper(self, paper_data: Dict, topic_id: int, use_for_rec: bool, paper_type: str = "positive"):
        """Process a single paper with all related data"""
        try:
            paper_id = paper_data['paperId']
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
            author_batch_size = 4  # Process authors in smaller batches
            
            author_data_list = paper_data.get('authors', [])
            for i in range(0, len(author_data_list), author_batch_size):
                batch = author_data_list[i:i + author_batch_size]
                print(f"Processing author batch {i//author_batch_size + 1}")
                
                for idx, author_data in enumerate(batch, i + 1):
                    try:
                        author_id = author_data.get('authorId') or author_data.get('name')
                        if not author_id:
                            continue

                        author = Author(
                            author_id=author_id,
                            author_name=author_data.get('name')
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
                    batch_ids = author_ids[i:i + author_batch_size]
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
            
            return article
            
        except Exception as e:
            print(f"Error details: {str(e)}")
            return None

     def update_single_author(self, author_detail):
        """Update a single author's details"""
        try:
            author = Author(
                author_id=author_detail['authorId'],
                author_name=author_detail.get('name'),
                h_index=author_detail.get('hIndex'),
                citation_count=author_detail.get('citationCount')
            )
            self.db.insert_author(author)
        except Exception as e:
            print(f"Error updating author {author_detail.get('authorId')}: {e}")

    def process_recommendations(self, paper_id: str, limit: int = 10):
        """Fetch and store paper recommendations"""
        try:
            print(f"Fetching recommendations for paper {paper_id}")
            recommendations = add_recommendations_to_positive_articles(paper_id, limit)
            
            for idx, rec_data in enumerate(recommendations, 1):
                if not rec_data.get('publicationDate'):
                    continue
                
                try:
                    # First process the recommended paper
                    rec_paper = self.process_paper(
                        rec_data,
                        None,  # No topic for recommendations
                        False,  # Don't use for recommendations
                        "recommended"
                    )
                    
                    if rec_paper:
                        # Then store the recommendation relationship
                        self.db.insert_paper_recommendations(paper_id, rec_data['paperId'], idx)
                        print(f"Stored recommendation {idx}: {rec_paper.info.title}")
                        
                except Exception as e:
                    print(f"Error processing recommendation {idx}: {str(e)}")
                    continue
                    
        except Exception as e:
            print(f"Error in recommendations for {paper_id}: {str(e)}")

    def generate_paper_markdown(self, article: Article) -> str:
        """Generate markdown content for a paper"""
        template = """# {title}

## Authors
{authors}

## Abstract
{abstract}

## Publication Details
- Journal: {journal}
- Date: {publication_date}
- Citations: {citation_count}
- H-index: {h_index}

## URL
{url}
"""
        authors_str = "\n".join([
            f"- {a.author_name} (h-index: {a.h_index or 'N/A'}, citations: {a.citation_count or 'N/A'})" 
            for a in article.authors
        ])
        
        return template.format(
            title=article.info.title or "No title",
            authors=authors_str or "No authors listed",
            abstract=article.info.abstract or "No abstract available",
            journal=article.info.journal or "No journal listed",
            publication_date=article.info.publication_date or "No date available",
            citation_count=article.info.citation_count or 0,
            h_index=article.info.h_index or 0,
            url=article.info.url or "No URL available"
        )

     def process_papers_from_csv(self, csv_path: str):
        """Process all papers from CSV with improved author handling"""
        papers = self.read_csv(csv_path)
        total = len(papers)
        
        for idx, paper in enumerate(papers, 1):
            print(f"\nProcessing paper {idx}/{total}")
            
            # Get paper details
            paper_data = self.fetch_paper_details(paper["paper_id"])
            if not paper_data:
                continue
                
            # Process the paper with author data
            article = self.process_paper(
                paper_data,
                paper["topic_id"],
                paper["use_for_recommendation"],
                paper.get("paper_type", "positive")
            )
            
            if article:
                print(f"✓ Successfully processed: {article.info.title}")
                print(f"  Authors: {len(article.authors)}")
                print(f"  H-index: {article.info.h_index}")

