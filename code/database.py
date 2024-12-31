#!/usr/bin/env python3

from typing import Dict, List, Optional

import mysql.connector
from mysql.connector import Error


class DatabaseManager:
    def __init__(self):
        self.config = {
            "host": "localhost",
            "user": "scholar_user",
            "password": "scholar_pass",
            "database": "scholar_db",
            "port": 3306,
        }

    def get_connection(self):
        try:
            conn = mysql.connector.connect(**self.config)
            return conn
        except Error as e:
            print(f"Error connecting to MySQL: {e}")
            raise

    def insert_topic(self, topic_name: str) -> int:
        """
        Insert a topic and return its ID.
        If topic already exists, returns existing ID.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # First try to find if topic exists
            cursor.execute("SELECT id FROM topics WHERE name = %s", (topic_name,))
            result = cursor.fetchone()

            if result:
                return result[0]

            # If not exists, insert new topic
            cursor.execute("INSERT INTO topics (name) VALUES (%s)", (topic_name,))
            conn.commit()

            # Get the ID of the newly inserted topic
            cursor.execute("SELECT id FROM topics WHERE name = %s", (topic_name,))
            topic_id = cursor.fetchone()[0]

            return topic_id

        finally:
            cursor.close()
            conn.close()

    def insert_paper(self, article_obj) -> None:
        """Insert or update paper details"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Insert paper
            query = """
                INSERT INTO papers (id, title, abstract, journal, url, 
                                  publication_date, citation_count, h_index)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    title = VALUES(title),
                    abstract = VALUES(abstract),
                    journal = VALUES(journal),
                    url = VALUES(url),
                    publication_date = VALUES(publication_date),
                    citation_count = VALUES(citation_count),
                    h_index = VALUES(h_index)
            """
            values = (
                article_obj.article_id,
                article_obj.info.title,
                article_obj.info.abstract,
                article_obj.info.journal,
                article_obj.info.url,
                article_obj.info.publication_date,
                article_obj.info.citation_count,
                article_obj.info.h_index,
            )
            cursor.execute(query, values)

            # Process authors
            for idx, author in enumerate(article_obj.authors, 1):
                # Insert author
                self.insert_author(author)
                # Link author to paper with order
                self.link_paper_author(article_obj.article_id, author.author_id, idx)

            conn.commit()

        except Exception as e:
            conn.rollback()
            print(f"Error inserting paper: {e}")
            raise
        finally:
            cursor.close()
            conn.close()

    def insert_author(self, author_obj) -> None:
        """Insert or update author details"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            query = """
                INSERT INTO authors (id, name, h_index, citation_count)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    name = COALESCE(VALUES(name), name),
                    h_index = COALESCE(VALUES(h_index), h_index),
                    citation_count = COALESCE(VALUES(citation_count), citation_count)
            """
            values = (
                author_obj.author_id,
                author_obj.author_name,
                author_obj.h_index,
                author_obj.citation_count,
            )
            cursor.execute(query, values)
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def insert_paper_author(self, paper_id: str, author_id: str, author_order: int):
        """Create paper-author relationship with order"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            query = """
                INSERT INTO paper_authors (paper_id, author_id, author_order)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE author_order = VALUES(author_order)
            """
            cursor.execute(query, (paper_id, author_id, author_order))
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def insert_paper_recommendations(
        self, source_paper_id: str, recommended_paper_id: str, recommendation_order: int
    ):
        """Store paper recommendations with order"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            query = """
                INSERT INTO paper_recommendations 
                    (source_paper_id, recommended_paper_id, recommendation_order)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    recommendation_order = VALUES(recommendation_order)
            """
            cursor.execute(
                query, (source_paper_id, recommended_paper_id, recommendation_order)
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def store_paper_markdown(self, paper_id: str, markdown_content: str):
        """Store paper's markdown content"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            query = """
                INSERT INTO paper_markdown (paper_id, markdown_content)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE 
                    markdown_content = VALUES(markdown_content),
                    last_updated = CURRENT_TIMESTAMP
            """
            cursor.execute(query, (paper_id, markdown_content))
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def store_topic_markdown(self, topic_id: int, markdown_content: str):
        """Store topic's markdown content"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            query = """
                INSERT INTO topic_markdown (topic_id, markdown_content)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE 
                    markdown_content = VALUES(markdown_content),
                    last_updated = CURRENT_TIMESTAMP
            """
            cursor.execute(query, (topic_id, markdown_content))
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def link_paper_author(
        self, paper_id: str, author_id: str, author_order: int = 1
    ) -> None:
        """Create paper-author relationship"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            query = """
                INSERT INTO paper_authors (paper_id, author_id, author_order)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE author_order = VALUES(author_order)
            """
            cursor.execute(query, (paper_id, author_id, author_order))
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def link_topic_paper(
        self,
        topic_id: int,
        paper_id: str,
        paper_type: str = "positive",
        use_for_recommendation: bool = True,
    ) -> None:
        """Link paper to topic with type and recommendation flag"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            query = """
                INSERT INTO topic_papers 
                    (topic_id, paper_id, paper_type, use_for_recommendation)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    paper_type = VALUES(paper_type),
                    use_for_recommendation = VALUES(use_for_recommendation)
            """
            cursor.execute(
                query, (topic_id, paper_id, paper_type, use_for_recommendation)
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()
