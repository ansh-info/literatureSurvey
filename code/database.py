#!/usr/bin/env python3

import time
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
            "connect_timeout": 60,
            "pool_size": 5,
            "pool_reset_session": True,
        }

    def get_connection(self):
        try:
            conn = mysql.connector.connect(**self.config)
            cursor = conn.cursor()
            # Set session variables to help with timeouts
            cursor.execute("SET SESSION wait_timeout=600")
            cursor.execute("SET SESSION interactive_timeout=600")
            cursor.close()
            return conn
        except Error as e:
            print(f"Error connecting to MySQL: {e}")
            raise

    def execute_with_retry(self, operation, max_retries=3):
        """Execute database operation with retry logic"""
        last_error = None
        for attempt in range(max_retries):
            conn = None
            cursor = None
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                result = operation(cursor)
                conn.commit()
                return result
            except mysql.connector.Error as e:
                last_error = e
                if cursor:
                    cursor.close()
                if conn:
                    conn.rollback()
                if e.errno == 1205:  # Lock timeout error
                    if attempt < max_retries - 1:
                        wait_time = min(2**attempt, 30)  # Cap wait time at 30 seconds
                        print(
                            f"Lock timeout, retrying in {wait_time} seconds... (attempt {attempt + 1})"
                        )
                        time.sleep(wait_time)
                        continue
                raise
            except Exception as e:
                last_error = e
                if cursor:
                    cursor.close()
                if conn:
                    conn.rollback()
                if attempt < max_retries - 1:
                    wait_time = min(2**attempt, 30)
                    print(
                        f"Database error: {e}, retrying in {wait_time} seconds... (attempt {attempt + 1})"
                    )
                    time.sleep(wait_time)
                    continue
                raise
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
        if last_error:
            raise last_error

    def insert_topic(self, topic_name: str) -> int:
        """Insert a topic and return its ID with retry logic"""

        def operation(cursor):
            # First try to find if topic exists
            cursor.execute("SELECT id FROM topics WHERE name = %s", (topic_name,))
            result = cursor.fetchone()

            if result:
                return result[0]

            # If not exists, insert new topic
            cursor.execute("INSERT INTO topics (name) VALUES (%s)", (topic_name,))
            cursor.execute("SELECT id FROM topics WHERE name = %s", (topic_name,))
            return cursor.fetchone()[0]

        return self.execute_with_retry(operation)

    def insert_paper(self, article_obj) -> None:
        """Insert or update paper details with retry logic"""

        def operation(cursor):
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

        return self.execute_with_retry(operation)

    def insert_author(self, author_obj) -> None:
        """Insert or update author with retry logic"""

        def operation(cursor):
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

        return self.execute_with_retry(operation)

    def link_paper_author(
        self, paper_id: str, author_id: str, author_order: int = 1
    ) -> None:
        """Create paper-author relationship with retry logic"""

        def operation(cursor):
            query = """
                INSERT INTO paper_authors (paper_id, author_id, author_order)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE author_order = VALUES(author_order)
            """
            cursor.execute(query, (paper_id, author_id, author_order))

        return self.execute_with_retry(operation)

    def link_topic_paper(
        self,
        topic_id: int,
        paper_id: str,
        paper_type: str = "positive",
        use_for_recommendation: bool = True,
    ) -> None:
        """Link paper to topic with retry logic"""

        def operation(cursor):
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

        return self.execute_with_retry(operation)

    def insert_paper_recommendations(
        self, source_paper_id: str, recommended_paper_id: str, recommendation_order: int
    ) -> None:
        """Store paper recommendations with retry logic"""

        def operation(cursor):
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

        return self.execute_with_retry(operation)
