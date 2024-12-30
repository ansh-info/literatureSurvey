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
        """Insert a topic and return its ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO topics (name) VALUES (%s) ON DUPLICATE KEY UPDATE name=name",
                (topic_name,),
            )
            cursor.execute("SELECT id FROM topics WHERE name = %s", (topic_name,))
            topic_id = cursor.fetchone()[0]
            conn.commit()
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

            # Insert authors
            for author in article_obj.authors:
                self.insert_author(cursor, author)
                self.link_paper_author(cursor, article_obj.article_id, author.author_id)

            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def insert_author(self, cursor, author_obj) -> None:
        """Insert or update author details"""
        query = """
            INSERT INTO authors (id, name, h_index, citation_count)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                h_index = VALUES(h_index),
                citation_count = VALUES(citation_count)
        """
        values = (
            author_obj.author_id,
            author_obj.author_name,
            author_obj.h_index,
            author_obj.citation_count,
        )
        cursor.execute(query, values)

    def link_paper_author(self, cursor, paper_id: str, author_id: str) -> None:
        """Create paper-author relationship"""
        query = """
            INSERT IGNORE INTO paper_authors (paper_id, author_id)
            VALUES (%s, %s)
        """
        cursor.execute(query, (paper_id, author_id))

    def link_topic_paper(
        self,
        topic_id: int,
        paper_id: str,
        paper_type: str,
        use_for_recommendation: bool = True,
    ) -> None:
        """Link paper to topic"""
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
