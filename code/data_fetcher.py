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

    def process_papers(self, csv_path: str):
        """Main function to process papers and store in database"""
        papers = self.read_csv(csv_path)
        print(f"Found {len(papers)} papers to process")

        for paper in papers:
            try:
                # Store topic
                topic_id = self.db.insert_topic(paper["topic"])
                print(f"Processed topic: {paper['topic']}")

                # Fetch and store paper details
                paper_data = self.fetch_paper_details(paper["paper_id"])
                if not paper_data:
                    print(f"Could not fetch details for paper {paper['paper_id']}")
                    continue

                # Create Article object
                article = Article(
                    paper["paper_id"],
                    use_for_recommendation=paper["use_for_recommendation"],
                )
                article.info.title = paper_data.get("title")
                article.info.abstract = paper_data.get("abstract")
                article.info.url = paper_data.get("url")
                article.info.journal = paper_data.get("journal")
                article.info.publication_date = paper_data.get("publicationDate")
                article.info.citation_count = paper_data.get("citationCount")

                # Process authors
                for author_data in paper_data.get("authors", []):
                    author = Author(
                        author_id=author_data.get("authorId", author_data["name"]),
                        author_name=author_data["name"],
                    )
                    article.authors.append(author)

                # Store in database
                self.db.insert_paper(article)
                self.db.link_topic_paper(
                    topic_id,
                    paper["paper_id"],
                    "positive",
                    paper["use_for_recommendation"],
                )

                print(f"Successfully processed paper: {article.info.title}")

            except Exception as e:
                print(f"Error processing paper {paper['paper_id']}: {e}")
                continue
