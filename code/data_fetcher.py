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

    def process_papers(csv_path: str, db: DatabaseManager):
        """Process the CSV file and store data in the database with improved paper type handling"""
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

                    # Extract paper ID and usage flag
                    paper_id = row["URL"].strip().split("/")[-1].split("?")[0]
                    use_for_rec = str(row["Use"]).strip() == "1"

                    # Determine paper type
                    # By default, papers are considered "positive" for their own topic
                    paper_type = "positive"

                    # Optional: If you want to specify paper type in CSV, add a column
                    if "Type" in row:
                        paper_type = row["Type"].strip().lower()
                        if paper_type not in ["positive", "negative"]:
                            paper_type = "positive"

                    # Fetch paper details
                    paper_data = get_paper_details([paper_id])[0]
                    if not paper_data:
                        print(f"✗ Could not fetch details for paper {paper_id}")
                        continue

                    # Create and populate Article object
                    article = Article(paper_id, use_for_recommendation=use_for_rec)
                    add_paper_details(article, paper_data)

                    # Fetch and update author details including h-index
                    author_ids = [
                        author["authorId"] for author in paper_data.get("authors", [])
                    ]
                    author_details = get_author_details(author_ids)
                    update_h_index(article, author_details)

                    # Store in database
                    db.insert_paper(article)
                    db.link_topic_paper(topic_id, paper_id, paper_type, use_for_rec)

                    print(f"✓ Successfully processed: {article.info.title}")
                    print(
                        f"  Paper type: {paper_type}, Use for recommendations: {use_for_rec}"
                    )

                except Exception as e:
                    print(f"Error processing row {index + 1}: {e}")
                    continue
