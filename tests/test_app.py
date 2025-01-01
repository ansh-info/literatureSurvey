import os
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
code_dir = os.path.join(project_root, "code")
if code_dir not in sys.path:
    sys.path.append(code_dir)

from database import DatabaseManager


class StreamlitDashboard:
    def __init__(self):
        self.db = DatabaseManager()
        st.set_page_config(
            page_title="Literature Survey Dashboard", page_icon="📚", layout="wide"
        )

    def get_topics(self):
        """Get all topics from database"""
        conn = self.db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT name FROM topics ORDER BY name")
        topics = [row["name"] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return topics

    def get_papers_by_topic(self, topic):
        """Get papers for a specific topic"""
        conn = self.db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT p.*, tp.paper_type, tp.use_for_recommendation,
                   GROUP_CONCAT(a.name) as authors
            FROM papers p
            JOIN topic_papers tp ON p.id = tp.paper_id
            JOIN topics t ON tp.topic_id = t.id
            LEFT JOIN paper_authors pa ON p.id = pa.paper_id
            LEFT JOIN authors a ON pa.author_id = a.id
            WHERE t.name = %s
            GROUP BY p.id
        """,
            (topic,),
        )
        papers = cursor.fetchall()
        cursor.close()
        conn.close()
        return papers

    def get_recommendations_for_paper(self, paper_id):
        """Get recommendations for a specific paper"""
        conn = self.db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT p.*, GROUP_CONCAT(a.name) as authors
            FROM papers p
            JOIN paper_recommendations pr ON pr.recommended_paper_id = p.id
            LEFT JOIN paper_authors pa ON p.id = pa.paper_id
            LEFT JOIN authors a ON pa.author_id = a.id
            WHERE pr.source_paper_id = %s
            GROUP BY p.id
        """,
            (paper_id,),
        )
        recommendations = cursor.fetchall()
        cursor.close()
        conn.close()
        return recommendations

    def run(self):
        st.title("Literature Survey Dashboard")

        # Sidebar
        st.sidebar.title("Navigation")
        topics = self.get_topics()
        selected_topic = st.sidebar.selectbox("Select Topic", topics)

        # Main content
        if selected_topic:
            st.header(f"Papers in {selected_topic}")

            # Get papers for selected topic
            papers = self.get_papers_by_topic(selected_topic)

            # Convert to DataFrame for easier handling
            df_papers = pd.DataFrame(papers)

            # Add filters
            cols = st.columns(3)
            with cols[0]:
                min_citations = st.number_input("Min Citations", 0, step=1)
            with cols[1]:
                paper_type = st.selectbox("Paper Type", ["All", "positive", "negative"])
            with cols[2]:
                search_term = st.text_input("Search in Title")

            # Filter DataFrame
            filtered_df = df_papers[
                (df_papers["citation_count"] >= min_citations)
                & (df_papers["title"].str.contains(search_term, case=False, na=False))
            ]
            if paper_type != "All":
                filtered_df = filtered_df[filtered_df["paper_type"] == paper_type]

            # Display papers
            st.subheader("Papers")
            for _, paper in filtered_df.iterrows():
                with st.expander(
                    f"{paper['title']} ({paper['citation_count']} citations)"
                ):
                    st.write(f"**Authors:** {paper['authors']}")
                    st.write(f"**Publication Date:** {paper['publication_date']}")
                    st.write(f"**Journal:** {paper['journal']}")
                    st.write(f"**Abstract:** {paper['abstract']}")
                    st.write(f"**URL:** [{paper['url']}]({paper['url']})")

                    # Show recommendations if available
                    recommendations = self.get_recommendations_for_paper(paper["id"])
                    if recommendations:
                        st.write("**Recommendations:**")
                        rec_df = pd.DataFrame(recommendations)
                        st.dataframe(
                            rec_df[
                                [
                                    "title",
                                    "authors",
                                    "citation_count",
                                    "publication_date",
                                ]
                            ],
                            hide_index=True,
                        )

            # Analytics
            st.subheader("Analytics")
            col1, col2 = st.columns(2)

            with col1:
                # Citations over time
                df_papers["year"] = pd.to_datetime(
                    df_papers["publication_date"]
                ).dt.year
                citations_by_year = (
                    df_papers.groupby("year")["citation_count"].sum().reset_index()
                )
                fig = px.line(
                    citations_by_year,
                    x="year",
                    y="citation_count",
                    title="Citations by Year",
                )
                st.plotly_chart(fig)

            with col2:
                # Papers by type
                papers_by_type = df_papers["paper_type"].value_counts()
                fig = px.pie(
                    values=papers_by_type.values,
                    names=papers_by_type.index,
                    title="Papers by Type",
                )
                st.plotly_chart(fig)


if __name__ == "__main__":
    dashboard = StreamlitDashboard()
    dashboard.run()
