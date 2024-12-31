import csv
from typing import Dict, List

import requests
from article import Article
from author import Author
from database import DatabaseManager
from utils import create_session, handle_api_request


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


    def process_paper(self, paper_data: Dict, topic_id: int, use_for_rec: bool, paper_type: str):
        """Process a single paper with complete author information"""
        try:
            # Create Article object
            article = Article(paper_data["paperId"], use_for_recommendation=use_for_rec)
            
            # Add basic paper details
            add_paper_details(article, paper_data)
            
            # Process authors
            author_ids = []
            for author_data in paper_data.get("authors", []):
                author_id = author_data.get("authorId")
                if author_id:
                    author_ids.append(author_id)
                    author = Author(
                        author_id=author_id,
                        author_name=author_data["name"]
                    )
                    article.authors.append(author)
            
            # Fetch complete author details including h-index
            if author_ids:
                author_details = self.fetch_author_details(author_ids)
                update_h_index(article, author_details)
            
            # Store in database
            self.db.insert_paper(article)
            self.db.link_topic_paper(topic_id, article.article_id, paper_type, use_for_rec)
            
            return article
            
        except Exception as e:
            print(f"Error processing paper {paper_data.get('paperId')}: {e}")
            return None

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

