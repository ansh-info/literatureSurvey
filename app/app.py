import os
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
            page_title="Literature Survey Dashboard",
            page_icon="📚",
            layout="wide",
            initial_sidebar_state="expanded",
        )
        # Add custom CSS
        st.markdown(
            """
            <style>
                .block-container {padding-top: 1rem;}
                .element-container {margin-bottom: 1rem;}
                .stProgress {margin-bottom: 1rem;}
            </style>
        """,
            unsafe_allow_html=True,
        )

    def get_topics(self):
        """Get all topics from database"""
        conn = self.db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT t.name, COUNT(tp.paper_id) as paper_count
            FROM topics t
            LEFT JOIN topic_papers tp ON t.id = tp.topic_id
            GROUP BY t.name
            ORDER BY t.name
        """
        )
        topics = [(row["name"], row["paper_count"]) for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return topics

    def get_papers_by_topic(self, topic):
        """Get papers for a specific topic with enhanced details"""
        conn = self.db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT 
                p.*,
                tp.paper_type,
                tp.use_for_recommendation,
                GROUP_CONCAT(DISTINCT a.name) as authors,
                GROUP_CONCAT(DISTINCT a.h_index) as author_h_indices,
                COUNT(pr.recommended_paper_id) as recommendation_count
            FROM papers p
            JOIN topic_papers tp ON p.id = tp.paper_id
            JOIN topics t ON tp.topic_id = t.id
            LEFT JOIN paper_authors pa ON p.id = pa.paper_id
            LEFT JOIN authors a ON pa.author_id = a.id
            LEFT JOIN paper_recommendations pr ON p.id = pr.source_paper_id
            WHERE t.name = %s
            GROUP BY p.id
        """,
            (topic,),
        )
        papers = cursor.fetchall()
        cursor.close()
        conn.close()
        return papers

    def get_author_stats(self, topic):
        """Get author statistics for a topic"""
        conn = self.db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT 
                a.name,
                a.h_index,
                a.citation_count,
                COUNT(DISTINCT pa.paper_id) as paper_count
            FROM authors a
            JOIN paper_authors pa ON a.id = pa.author_id
            JOIN topic_papers tp ON pa.paper_id = tp.paper_id
            JOIN topics t ON tp.topic_id = t.id
            WHERE t.name = %s
            GROUP BY a.id
            ORDER BY a.citation_count DESC
        """,
            (topic,),
        )
        authors = cursor.fetchall()
        cursor.close()
        conn.close()
        return authors

    # Add this method back to the StreamlitDashboard class

    def get_recommendations_for_paper(self, paper_id):
        """Get recommendations for a specific paper with enhanced details"""
        conn = self.db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT 
                p.*,
                GROUP_CONCAT(DISTINCT a.name) as authors,
                GROUP_CONCAT(DISTINCT a.h_index) as author_h_indices,
                pr.recommendation_order
            FROM papers p
            JOIN paper_recommendations pr ON pr.recommended_paper_id = p.id
            LEFT JOIN paper_authors pa ON p.id = pa.paper_id
            LEFT JOIN authors a ON pa.author_id = a.id
            WHERE pr.source_paper_id = %s
            GROUP BY p.id
            ORDER BY pr.recommendation_order ASC
        """,
            (paper_id,),
        )
        recommendations = cursor.fetchall()
        cursor.close()
        conn.close()
        return recommendations

    def display_paper_details(self, paper, recommendations):
        """Display detailed paper information with enhanced formatting"""
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown(f"### {paper['title']}")
            st.markdown(f"**Authors:** {paper['authors']}")
            st.markdown(f"**Publication Date:** {paper['publication_date']}")
            st.markdown(f"**Journal:** {paper['journal']}")
            st.markdown("**Abstract:**")
            st.markdown(f">{paper['abstract']}")
            st.markdown(f"**URL:** [{paper['url']}]({paper['url']})")

        with col2:
            metrics_col1, metrics_col2 = st.columns(2)
            with metrics_col1:
                st.metric("Citations", paper["citation_count"])
            with metrics_col2:
                st.metric(
                    "H-index", round(paper["h_index"], 2) if paper["h_index"] else 0
                )

        if recommendations:
            st.markdown("#### Recommended Papers")
            rec_df = pd.DataFrame(recommendations)
            fig = go.Figure(
                data=[
                    go.Table(
                        header=dict(
                            values=["Title", "Authors", "Citations", "Date"],
                            fill_color="green",
                            align="left",
                        ),
                        cells=dict(
                            values=[
                                rec_df["title"],
                                rec_df["authors"],
                                rec_df["citation_count"],
                                rec_df["publication_date"],
                            ],
                            align="left",
                        ),
                    )
                ]
            )
            st.plotly_chart(fig, use_container_width=True)

    def display_analytics(self, df_papers, authors_data):
        """Display enhanced analytics section"""
        st.header("Analytics Dashboard")

        # Key Metrics
        metric_cols = st.columns(4)
        with metric_cols[0]:
            st.metric("Total Papers", len(df_papers))
        with metric_cols[1]:
            st.metric("Total Citations", df_papers["citation_count"].sum())
        with metric_cols[2]:
            st.metric("Average H-index", round(df_papers["h_index"].mean(), 2))
        with metric_cols[3]:
            st.metric("Unique Authors", len(pd.DataFrame(authors_data)))

        col1, col2 = st.columns(2)

        with col1:
            # Citations over time
            df_papers["year"] = pd.to_datetime(df_papers["publication_date"]).dt.year
            citations_by_year = (
                df_papers.groupby("year")["citation_count"].sum().reset_index()
            )
            fig = px.line(
                citations_by_year,
                x="year",
                y="citation_count",
                title="Citations Over Time",
                labels={"citation_count": "Citations", "year": "Year"},
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

            # Author Impact
            authors_df = pd.DataFrame(authors_data)
            if not authors_df.empty:
                top_authors = authors_df.nlargest(10, "citation_count")
                fig = px.bar(
                    top_authors,
                    x="name",
                    y="citation_count",
                    title="Top Authors by Citations",
                    labels={"name": "Author", "citation_count": "Citations"},
                )
                fig.update_layout(xaxis_tickangle=45)
                st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Papers by type
            papers_by_type = df_papers["paper_type"].value_counts()
            fig = px.pie(
                values=papers_by_type.values,
                names=papers_by_type.index,
                title="Papers by Type",
            )
            st.plotly_chart(fig, use_container_width=True)

            # H-index Distribution
            fig = px.histogram(
                df_papers,
                x="h_index",
                title="H-index Distribution",
                labels={"h_index": "H-index", "count": "Number of Papers"},
            )
            st.plotly_chart(fig, use_container_width=True)

    def run(self):
        # Sidebar
        st.sidebar.title("📚 Navigation")
        topics = self.get_topics()
        selected_topic = st.sidebar.selectbox(
            "Select Topic",
            [t[0] for t in topics],
            format_func=lambda x: f"{x} ({dict(topics)[x]} papers)",
        )

        if selected_topic:
            st.title(f"Literature Survey: {selected_topic}")

            # Get data
            papers = self.get_papers_by_topic(selected_topic)
            authors_data = self.get_author_stats(selected_topic)
            df_papers = pd.DataFrame(papers)

            # Filters
            st.markdown("### 🔍 Filters")
            filter_cols = st.columns(4)
            with filter_cols[0]:
                min_citations = st.number_input("Min Citations", 0, step=1)
            with filter_cols[1]:
                paper_type = st.selectbox("Paper Type", ["All", "positive", "negative"])
            with filter_cols[2]:
                sort_by = st.selectbox(
                    "Sort By", ["citation_count", "publication_date", "h_index"]
                )
            with filter_cols[3]:
                search_term = st.text_input("Search in Title/Abstract")

            # Filter DataFrame
            filtered_df = df_papers[
                (df_papers["citation_count"] >= min_citations)
                & (
                    df_papers["title"].str.contains(search_term, case=False, na=False)
                    | df_papers["abstract"].str.contains(
                        search_term, case=False, na=False
                    )
                )
            ]
            if paper_type != "All":
                filtered_df = filtered_df[filtered_df["paper_type"] == paper_type]

            # Sort DataFrame
            filtered_df = filtered_df.sort_values(by=sort_by, ascending=False)

            # Papers Section
            st.markdown("### 📄 Papers")
            for _, paper in filtered_df.iterrows():
                with st.expander(
                    f"{paper['title']} ({paper['citation_count']} citations)"
                ):
                    recommendations = self.get_recommendations_for_paper(paper["id"])
                    self.display_paper_details(paper, recommendations)

            # Analytics Section
            self.display_analytics(df_papers, authors_data)


if __name__ == "__main__":
    dashboard = StreamlitDashboard()
    dashboard.run()
