#!/usr/bin/env python3

"""
script to define utility functions
"""

import os
import re
import sys
import time

import matplotlib.pyplot as plt
import pandas as pd
import requests
import yaml
from pyzotero import zotero
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

FIELDS = "paperId,url,authors,journal,title,"
FIELDS += "publicationTypes,publicationDate,citationCount,"
FIELDS += "publicationVenue,externalIds,abstract"

LIBRARY_TYPE = "group"
LIBRARY_ID = os.environ.get("LIBRARY_ID")
ZOTERO_API_KEY = os.environ.get("ZOTERO_API_KEY")
TEST_COLLECTION_KEY = os.environ.get("TEST_COLLECTION_KEY")


def create_session():
    """Create a requests session with retry strategy"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    return session


def handle_api_request(session, endpoint, params=None, json=None, method="GET"):
    """Handle API requests with rate limiting and retries"""
    try:
        if method == "GET":
            response = session.get(endpoint, params=params, timeout=30)
        else:  # POST
            response = session.post(endpoint, params=params, json=json, timeout=30)

        if response.status_code == 429:
            wait_time = int(response.headers.get("Retry-After", 60))
            print(f"Rate limited. Waiting {wait_time} seconds...")
            time.sleep(wait_time)
            return handle_api_request(session, endpoint, params, json, method)

        response.raise_for_status()
        time.sleep(1)  # Basic rate limiting
        return response.json()

    except requests.exceptions.Timeout:
        print(f"Request to {endpoint} timed out. Retrying...")
        time.sleep(2)
        return handle_api_request(session, endpoint, params, json, method)

    except Exception as e:
        print(f"API request failed for {endpoint}: {e}")
        return None


def add_recommended_articles_to_zotero(topic_name, paper_ids):
    """Add the recommended articles to zotero"""
    if LIBRARY_ID is None or ZOTERO_API_KEY is None or TEST_COLLECTION_KEY is None:
        print("Zotero credentials not found.")
    else:
        print("Adding recommended articles to Zotero.")
        zot = zotero.Zotero(LIBRARY_ID, LIBRARY_TYPE, ZOTERO_API_KEY)
        new_items = []
        for _, paper_obj in paper_ids["recommended"].items():
            template = zot.item_template("journalArticle")
            template["title"] = paper_obj.info.title
            template["creators"] = []
            for author in paper_obj.authors:
                template["creators"].append(
                    {"creatorType": "author", "name": author.author_name}
                )
            template["publicationTitle"] = paper_obj.info.journal
            template["date"] = paper_obj.info.publication_date
            template["abstractNote"] = paper_obj.info.abstract
            template["url"] = paper_obj.info.url
            template["tags"] = [{"tag": topic_name}]
            template["collections"] = [TEST_COLLECTION_KEY]
            new_items.append(template)

        for i in range(0, len(new_items), 50):
            zot.check_items(new_items[i : i + 50])
            zot.create_items(new_items[i : i + 50])


def add_negative_articles(topic_obj, dic):
    """Add the negative articles to the topic object"""
    if "negative" not in topic_obj.paper_ids:
        topic_obj.paper_ids["negative"] = {}
    for topic in dic:
        if topic == topic_obj.topic:
            continue
        for paper_id in dic[topic].paper_ids["positive"]:
            if paper_id in topic_obj.paper_ids["negative"]:
                continue
            if paper_id in topic_obj.paper_ids["positive"]:
                continue
            paper_obj = dic[topic].paper_ids["positive"][paper_id]
            if paper_obj.use_for_recommendation is False:
                continue
            topic_obj.paper_ids["negative"][paper_id] = dic[topic].paper_ids[
                "positive"
            ][paper_id]
    print(
        f'Added {len(topic_obj.paper_ids["negative"])} negative articles for {topic_obj.topic}.'
    )


def update_paper_details(topic_obj):
    """Fetch the details of all the papers"""
    all_paper_ids = list(topic_obj.paper_ids["positive"].keys())
    all_paper_ids += list(topic_obj.paper_ids["negative"].keys())
    all_paper_ids = list(set(all_paper_ids))
    all_paper_data = get_paper_details(all_paper_ids)

    for paper_id, paper_data in zip(all_paper_ids, all_paper_data):
        if paper_id == paper_data["paperId"]:
            continue
        print(
            f'Paper ID {paper_id} does not match {paper_data["paperId"]}. Changing the paper ID.'
        )
        if paper_id in topic_obj.paper_ids["positive"]:
            topic_obj.paper_ids["positive"][paper_data["paperId"]] = (
                topic_obj.paper_ids["positive"].pop(paper_id)
            )
        elif paper_id in topic_obj.paper_ids["negative"]:
            topic_obj.paper_ids["negative"][paper_data["paperId"]] = (
                topic_obj.paper_ids["negative"].pop(paper_id)
            )
    return all_paper_data


def add_paper_details(article_obj, article_data):
    """Add the details of the article"""
    article_obj.info.journal = update_journal(
        article_data["journal"],
        article_data["publicationVenue"],
        article_data["externalIds"],
    )
    article_obj.info.title = article_data["title"]
    article_obj.info.url = article_data["url"]
    article_obj.info.abstract = article_data["abstract"]
    article_obj.info.publication_date = article_data["publicationDate"]
    article_obj.info.citation_count = article_data["citationCount"]


def update_h_index(article_obj, authors_data):
    """
    Update h-index of article and its authors with improved calculation
    """
    authors_h_index_list = []
    total_citations = 0

    for row in authors_data:
        if row is None:
            continue

        for author in article_obj.authors:
            if author.author_id == row.get("authorId"):
                # Update author information
                author.h_index = row.get("hIndex")
                author.name = row.get("name")
                author.citation_count = row.get("citationCount")

                if author.h_index is not None:
                    authors_h_index_list.append(author.h_index)
                if author.citation_count is not None:
                    total_citations += author.citation_count

    # Calculate article's h-index based on authors
    if authors_h_index_list:
        # Base h-index is the weighted average of authors
        base_h_index = sum(authors_h_index_list) / len(authors_h_index_list)

        # Adjust for paper's own impact
        if article_obj.info.citation_count:
            citation_factor = min(1.5, (article_obj.info.citation_count / 100) + 1)
            final_h_index = base_h_index * citation_factor
        else:
            final_h_index = base_h_index

        article_obj.info.h_index = round(final_h_index, 2)
    else:
        article_obj.info.h_index = 0

    return article_obj.info.h_index


def add_recommendations_to_positive_articles(article_id, limit=500, fields=FIELDS):
    """Get paper recommendations with improved error handling and fallback"""
    # First try the direct recommendation endpoint
    try:
        recommendations = _get_recommendations_direct(article_id, limit, fields)
        if recommendations:
            return recommendations
    except Exception as e:
        print(f"Direct recommendation failed: {e}")

    # If direct recommendation fails, try batch recommendation
    try:
        return _get_recommendations_batch(article_id, limit, fields)
    except Exception as e:
        print(f"Batch recommendation failed: {e}")
        return []


def _get_recommendations_direct(article_id, limit=500, fields=FIELDS):
    """Try getting recommendations using the direct endpoint"""
    endpoint = f"https://api.semanticscholar.org/recommendations/v1/papers/forpaper/{article_id}"
    params = {"fields": fields, "limit": limit, "from": "all-cs"}

    session = create_session()
    print(f"Trying direct recommendations for paper {article_id}")

    response_data = handle_api_request(session, endpoint, params=params)
    if response_data is None:
        return None
    return response_data.get("recommendedPapers", [])


def _get_recommendations_batch(article_id, limit=500, fields=FIELDS):
    """Try getting recommendations using the batch endpoint"""
    endpoint = "https://api.semanticscholar.org/graph/v1/paper/batch"

    # First get related papers
    params = {
        "fields": f"references,citations,{fields}",
    }

    session = create_session()
    print(f"Trying batch recommendations for paper {article_id}")

    # Get paper details including references and citations
    json_data = {"ids": [article_id]}
    paper_data = handle_api_request(
        session, endpoint, params=params, json=json_data, method="POST"
    )

    if not paper_data or not paper_data[0]:
        return []

    paper = paper_data[0]

    # Collect paper IDs from references and citations
    related_ids = set()

    if paper.get("references"):
        related_ids.update(
            ref["paperId"] for ref in paper["references"] if "paperId" in ref
        )

    if paper.get("citations"):
        related_ids.update(
            cit["paperId"] for cit in paper["citations"] if "paperId" in cit
        )

    # Convert to list and limit
    related_ids = list(related_ids)[:limit]

    if not related_ids:
        return []

    # Get full details for related papers
    params = {"fields": fields}
    json_data = {"ids": related_ids}

    related_papers = handle_api_request(
        session, endpoint, params=params, json=json_data, method="POST"
    )

    if not related_papers:
        return []

    # Filter out None values and sort by citation count
    related_papers = [p for p in related_papers if p is not None]
    related_papers.sort(key=lambda x: x.get("citationCount", 0) or 0, reverse=True)

    return related_papers[:limit]


def get_paper_details(paper_ids, fields=FIELDS):
    """Get paper details with improved error handling"""
    endpoint = "https://api.semanticscholar.org/graph/v1/paper/batch"
    params = {"fields": fields}
    json_data = {"ids": list(paper_ids)}

    session = create_session()
    print(f"Fetching details for {len(paper_ids)} papers...")

    response_data = handle_api_request(
        session, endpoint, params=params, json=json_data, method="POST"
    )
    if response_data is None:
        print("Failed to fetch paper details")
        return []
    return response_data


def get_author_details(all_authors_ids):
    """Get author details with improved error handling"""
    author_details_wo_id = []
    authors_ids = []

    for author_id in all_authors_ids:
        if re.fullmatch(r"[A-Za-z ]+", author_id):
            author_details_wo_id.append(
                {
                    "authorId": author_id,
                    "hIndex": None,
                    "name": author_id,
                    "citationCount": None,
                }
            )
            continue
        authors_ids.append(author_id)

    session = create_session()
    authors_details = []

    for start_index in range(0, len(authors_ids), 1000):
        end_index = min(start_index + 1000, len(authors_ids))
        batch_ids = authors_ids[start_index:end_index]

        endpoint = "https://api.semanticscholar.org/graph/v1/author/batch"
        params = {"fields": "name,hIndex,citationCount"}
        json_data = {"ids": batch_ids}

        print(f"Fetching details for authors {start_index+1} to {end_index}")
        response_data = handle_api_request(
            session, endpoint, params=params, json=json_data, method="POST"
        )

        if response_data:
            authors_details.extend(response_data)

    return authors_details + author_details_wo_id


def update_journal(journal, publication_venue, external_ids):
    """Update the journal of the recommended articles"""
    journal_name = []
    if journal is not None and "name" in journal:
        journal_name.append(journal["name"])

    if publication_venue is not None and "name" in publication_venue:
        for name in journal_name.copy():
            if publication_venue["name"].lower() == name.lower():
                continue
            journal_name.append(publication_venue["name"])

    if not journal_name:
        for external_id in external_ids:
            if external_id in ["CorpusId", "DOI"]:
                continue
            journal_name.append(external_id)

    if not journal_name:
        journal_name = None
    else:
        journal_name = list(set(journal_name))
        journal_name = ", ".join(journal_name)
    return journal_name


def add_recommendations(topic_obj, limit=500, fields=FIELDS):
    """Add recommendations to the positive articles"""
    endpoint = "https://api.semanticscholar.org/recommendations/v1/papers/"
    params = {"fields": fields, "limit": limit}

    positive_paper_ids = [
        paper_id
        for paper_id, paper_obj in topic_obj.paper_ids["positive"].items()
        if paper_obj.use_for_recommendation
    ]

    json_data = {
        "positivePaperIds": positive_paper_ids,
        "negativePaperIds": list(topic_obj.paper_ids["negative"].keys()),
    }

    session = create_session()
    print(f"Fetching recommendations for topic {topic_obj.topic}")
    response_data = handle_api_request(
        session, endpoint, params=params, json=json_data, method="POST"
    )

    if response_data is None:
        print(f"Failed to fetch recommendations for topic {topic_obj.topic}")
        return {"recommendedPapers": []}
    return response_data


def metrics_over_time_js(data) -> plt:
    """Return the metrics over time"""
    dic = {}
    for _, paper_obj in data.items():
        publication_date = paper_obj.info.publication_date
        if publication_date is None or publication_date == "":
            continue
        citation_count = paper_obj.info.citation_count
        if citation_count is None or citation_count == "":
            continue

        year = publication_date.split("-")[0]
        if year not in dic:
            dic[year] = {"num_articles": 0, "num_citations": 0}
        dic[year]["num_articles"] += 1
        dic[year]["num_citations"] += citation_count

    df = pd.DataFrame(dic).T
    df["Year"] = df.index
    df = df.sort_values(by="Year", ascending=True)
    return df


def read_yaml(file_path):
    """Read YAML file"""
    with open(file_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    return data


def write_yaml(data, file_path):
    """Write YAML file"""
    with open(file_path, "w", encoding="utf-8") as file:
        yaml.dump(data, file, default_flow_style=False)
