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


    def process_paper(self, paper_data: Dict, topic_id: int, use_for_rec: bool, paper_type: str = "positive"):
        """Process a single paper with complete data persistence"""
        try:
            # Create Article object
            article = Article(paper_data["paperId"], use_for_recommendation=use_for_rec)
            add_paper_details(article, paper_data)

            # Process authors
            for idx, author_data in enumerate(paper_data.get("authors", []), 1):
                author_id = author_data.get("authorId") or author_data["name"]
                author = Author(
                    author_id=author_id,
                    author_name=author_data["name"]
                )
                article.authors.append(author)
                
                # Store author and paper-author relationship
                self.db.insert_author(author)
                self.db.insert_paper_author(article.article_id, author.author_id, idx)

            # Fetch and store author details including h-index
            author_ids = [a.author_id for a in article.authors]
            if author_ids:
                author_details = get_author_details(author_ids)
                update_h_index(article, author_details)
                
                # Update authors with their details
                for author_detail in author_details:
                    if author_detail:
                        author = Author(
                            author_id=author_detail["authorId"],
                            author_name=author_detail["name"],
                            h_index=author_detail.get("hIndex"),
                            citation_count=author_detail.get("citationCount")
                        )
                        self.db.insert_author(author)

            # Store paper in database
            self.db.insert_paper(article)
            self.db.link_topic_paper(topic_id, article.article_id, paper_type, use_for_rec)

            # Generate and store markdown
            markdown_content = self.generate_paper_markdown(article)
            self.db.store_paper_markdown(article.article_id, markdown_content)

            return article

        except Exception as e:
            print(f"Error processing paper {paper_data.get('paperId')}: {e}")
            return None

     def process_recommendations(self, source_paper_id: str, recommendations: List[Dict], limit: int = 10):
        """Process and store paper recommendations"""
        try:
            for idx, rec_data in enumerate(recommendations[:limit], 1):
                if not rec_data.get('publicationDate'):
                    continue

                # Store recommendation relationship
                self.db.insert_paper_recommendations(
                    source_paper_id,
                    rec_data['paperId'],
                    idx
                )

                # Process recommended paper
                self.process_paper(
                    rec_data,
                    None,  # No topic for recommendations
                    False,  # Don't use for recommendations
                    "recommended"
                )

        except Exception as e:
            print(f"Error processing recommendations for {source_paper_id}: {e}")

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
        authors_str = "\n".join([f"- {a.author_name} (h-index: {a.h_index or 'N/A'})" 
                                for a in article.authors])
        
        return template.format(
            title=article.info.title,
            authors=authors_str,
            abstract=article.info.abstract,
            journal=article.info.journal,
            publication_date=article.info.publication_date,
            citation_count=article.info.citation_count,
            h_index=article.info.h_index,
            url=article.info.url
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

