import os
import sys
from pathlib import Path

import numpy as np
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
                .paper-card {
                    padding: 1rem;
                    border-radius: 0.5rem;
                    border: 1px solid #e0e0e0;
                    margin-bottom: 1rem;
                }
                .metric-card {
                    background-color: #f8f9fa;
                    padding: 1rem;
                    border-radius: 0.5rem;
                    margin-bottom: 1rem;
                }
                .recommendation-card {
                    background-color: #f0f7ff;
                    padding: 1rem;
                    border-radius: 0.5rem;
                    margin: 0.5rem 0;
                }
            </style>
        """,
            unsafe_allow_html=True,
        )

    def get_topics(self):
        """Get all topics from database with enhanced metrics"""
        conn = self.db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT 
                t.name, 
                COUNT(DISTINCT tp.paper_id) as paper_count,
                COUNT(DISTINCT pr.recommended_paper_id) as recommendation_count,
                AVG(p.h_index) as avg_h_index
            FROM topics t
            LEFT JOIN topic_papers tp ON t.id = tp.topic_id
            LEFT JOIN papers p ON tp.paper_id = p.id
            LEFT JOIN paper_recommendations pr ON p.id = pr.source_paper_id
            GROUP BY t.name
            ORDER BY t.name
        """
        )
        topics = cursor.fetchall()
        cursor.close()
        conn.close()
        return topics

    def get_papers_by_topic(self, topic):
        """Get papers with enhanced details"""
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
                COUNT(DISTINCT pr.recommended_paper_id) as recommendation_count
            FROM papers p
            JOIN topic_papers tp ON p.id = tp.paper_id
            JOIN topics t ON tp.topic_id = t.id
            LEFT JOIN paper_authors pa ON p.id = pa.paper_id
            LEFT JOIN authors a ON pa.author_id = a.id
            LEFT JOIN paper_recommendations pr ON p.id = pr.source_paper_id
            WHERE t.name = %s
            GROUP BY p.id
            ORDER BY p.citation_count DESC
        """,
            (topic,),
        )
        papers = cursor.fetchall()
        cursor.close()
        conn.close()
        return papers

    def get_recommendations_for_paper(self, paper_id):
        """Get enhanced recommendations for a paper"""
        conn = self.db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT 
                p.*,
                GROUP_CONCAT(DISTINCT a.name) as authors,
                GROUP_CONCAT(DISTINCT a.h_index) as author_h_indices,
                pr.recommendation_order,
                COUNT(pr2.recommended_paper_id) as sub_recommendations
            FROM papers p
            JOIN paper_recommendations pr ON pr.recommended_paper_id = p.id
            LEFT JOIN paper_authors pa ON p.id = pa.paper_id
            LEFT JOIN authors a ON pa.author_id = a.id
            LEFT JOIN paper_recommendations pr2 ON p.id = pr2.source_paper_id
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
        """Display enhanced paper information"""
        with st.container():
            st.markdown("""<div class="paper-card">""", unsafe_allow_html=True)

            # Paper title and URL
            if paper["url"]:
                st.markdown(f"### [{paper['title']}]({paper['url']})")
            else:
                st.markdown(f"### {paper['title']}")

            # Paper metadata
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.markdown(f"**Authors:** {paper['authors']}")
                st.markdown(
                    f"**Journal:** {paper['journal'] if paper['journal'] else 'N/A'}"
                )
                st.markdown(f"**Publication Date:** {paper['publication_date']}")

            with col2:
                st.markdown("""<div class="metric-card">""", unsafe_allow_html=True)
                st.metric("Citations", paper["citation_count"])
                st.markdown("</div>", unsafe_allow_html=True)

            with col3:
                st.markdown("""<div class="metric-card">""", unsafe_allow_html=True)
                st.metric(
                    "H-index", f"{paper['h_index']:.2f}" if paper["h_index"] else "N/A"
                )
                st.markdown("</div>", unsafe_allow_html=True)

            # Abstract with toggle
            with st.expander("Abstract"):
                st.markdown(f">{paper['abstract']}")

            # Recommendations section
            if recommendations:
                with st.expander(f"📚 Recommended Papers ({len(recommendations)})"):
                    for rec in recommendations:
                        st.markdown(
                            """<div class="recommendation-card">""",
                            unsafe_allow_html=True,
                        )

                        # Title with link if available
                        if rec["url"]:
                            st.markdown(f"#### [{rec['title']}]({rec['url']})")
                        else:
                            st.markdown(f"#### {rec['title']}")

                        # Recommendation details
                        rec_col1, rec_col2, rec_col3 = st.columns([2, 1, 1])
                        with rec_col1:
                            st.markdown(f"**Authors:** {rec['authors']}")
                            st.markdown(
                                f"**Publication Date:** {rec['publication_date']}"
                            )

                        with rec_col2:
                            st.metric("Citations", rec["citation_count"])

                        with rec_col3:
                            st.metric(
                                "H-index",
                                f"{rec['h_index']:.2f}" if rec["h_index"] else "N/A",
                            )

                        st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

    def display_analytics(self, df_papers, authors_data):
        """Display enhanced analytics dashboard"""
        st.header("📊 Analytics Dashboard")

        # Overview metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown("""<div class="metric-card">""", unsafe_allow_html=True)
            st.metric("Total Papers", len(df_papers))
            st.markdown("</div>", unsafe_allow_html=True)

        with col2:
            st.markdown("""<div class="metric-card">""", unsafe_allow_html=True)
            st.metric("Total Citations", df_papers["citation_count"].sum())
            st.markdown("</div>", unsafe_allow_html=True)

        with col3:
            st.markdown("""<div class="metric-card">""", unsafe_allow_html=True)
            st.metric("Average H-index", f"{df_papers['h_index'].mean():.2f}")
            st.markdown("</div>", unsafe_allow_html=True)

        with col4:
            st.markdown("""<div class="metric-card">""", unsafe_allow_html=True)
            st.metric("Unique Authors", len(pd.DataFrame(authors_data)))
            st.markdown("</div>", unsafe_allow_html=True)

        # Visualization tabs
        tab1, tab2 = st.tabs(["📈 Time Series Analysis", "👥 Author Analysis"])

        with tab1:
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
                    title="Citations Over Time",
                    labels={"citation_count": "Citations", "year": "Year"},
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                # H-index distribution
                fig = px.histogram(
                    df_papers,
                    x="h_index",
                    title="H-index Distribution",
                    labels={"h_index": "H-index", "count": "Number of Papers"},
                    nbins=20,
                )
                st.plotly_chart(fig, use_container_width=True)

        with tab2:
            col1, col2 = st.columns(2)

            with col1:
                # Top authors visualization
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
                # Author h-index distribution
                if not authors_df.empty and "h_index" in authors_df.columns:
                    fig = px.histogram(
                        authors_df,
                        x="h_index",
                        title="Author H-index Distribution",
                        labels={"h_index": "H-index", "count": "Number of Authors"},
                        nbins=20,
                    )
                    st.plotly_chart(fig, use_container_width=True)

    def get_author_stats(self, topic):
        """Get enhanced author statistics for a topic"""
        conn = self.db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
                SELECT 
                    a.name,
                    a.h_index,
                    a.citation_count,
                    COUNT(DISTINCT pa.paper_id) as paper_count,
                    GROUP_CONCAT(DISTINCT p.title) as paper_titles,
                    SUM(p.citation_count) as total_paper_citations
                FROM authors a
                JOIN paper_authors pa ON a.id = pa.author_id
                JOIN papers p ON pa.paper_id = p.id
                JOIN topic_papers tp ON p.id = tp.paper_id
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

    def run(self):
        # Sidebar
        st.sidebar.title("📚 Navigation")
        topics = self.get_topics()

        # Enhanced topic selector
        selected_topic = st.sidebar.selectbox(
            "Select Topic",
            [t["name"] for t in topics],
            format_func=lambda x: f"{x} ({next((t['paper_count'] for t in topics if t['name'] == x), 0)} papers)",
        )

        if selected_topic:
            # Topic overview
            st.title(f"📑 Literature Survey: {selected_topic}")
            topic_data = next((t for t in topics if t["name"] == selected_topic), None)

            if topic_data:
                # Topic metrics
                topic_metrics = st.columns(4)
                with topic_metrics[0]:
                    st.markdown("""<div class="metric-card">""", unsafe_allow_html=True)
                    st.metric("Papers", topic_data["paper_count"])
                    st.markdown("</div>", unsafe_allow_html=True)

                with topic_metrics[1]:
                    st.markdown("""<div class="metric-card">""", unsafe_allow_html=True)
                    st.metric("Recommendations", topic_data["recommendation_count"])
                    st.markdown("</div>", unsafe_allow_html=True)

                with topic_metrics[2]:
                    st.markdown("""<div class="metric-card">""", unsafe_allow_html=True)
                    st.metric("Avg H-index", f"{topic_data['avg_h_index']:.2f}")
                    st.markdown("</div>", unsafe_allow_html=True)

            # Get and process data
            papers = self.get_papers_by_topic(selected_topic)
            authors_data = self.get_author_stats(selected_topic)
            df_papers = pd.DataFrame(papers)

            # Enhanced filters
            st.markdown("### 🔍 Filters")
            filter_cols = st.columns(4)
            with filter_cols[0]:
                min_citations = st.number_input("Min Citations", 0, step=1)
            with filter_cols[1]:
                paper_type = st.selectbox("Paper Type", ["All", "positive", "negative"])
            with filter_cols[2]:
                sort_by = st.selectbox(
                    "Sort By",
                    ["citation_count", "publication_date", "h_index"],
                    format_func=lambda x: {
                        "citation_count": "Citations",
                        "publication_date": "Date",
                        "h_index": "H-index",
                    }[x],
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

            # Display papers
            paper_tabs = st.tabs(["📄 Papers", "📊 Analytics"])

            with paper_tabs[0]:
                for _, paper in filtered_df.iterrows():
                    recommendations = self.get_recommendations_for_paper(paper["id"])
                    self.display_paper_details(paper, recommendations)

            with paper_tabs[1]:
                self.display_analytics(df_papers, authors_data)

                # Additional Analytics Section
                st.markdown("### 📈 Advanced Analytics")

                # Paper Type Distribution
                papers_by_type = df_papers["paper_type"].value_counts()
                if not papers_by_type.empty:
                    col1, col2 = st.columns(2)
                    with col1:
                        fig = px.pie(
                            values=papers_by_type.values,
                            names=papers_by_type.index,
                            title="Papers by Type",
                            hole=0.4,
                        )
                        st.plotly_chart(fig, use_container_width=True)

                    # Recommendation Statistics
                    with col2:
                        rec_stats = {
                            "Papers with Recommendations": len(
                                df_papers[df_papers["recommendation_count"] > 0]
                            ),
                            "Total Recommendations": df_papers[
                                "recommendation_count"
                            ].sum(),
                            "Avg Recommendations per Paper": df_papers[
                                "recommendation_count"
                            ].mean(),
                        }
                        for stat_name, stat_value in rec_stats.items():
                            st.metric(stat_name, f"{stat_value:.1f}")

                # Author Collaboration Network
                if authors_data:
                    st.markdown("### 👥 Author Collaboration Insights")
                    author_df = pd.DataFrame(authors_data)
                    top_authors = author_df.nlargest(5, "citation_count")

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Top 5 Authors by Citations**")
                        for _, author in top_authors.iterrows():
                            st.markdown(
                                f"""
                                * **{author['name']}**
                                  * Citations: {author['citation_count']:,}
                                  * H-index: {author['h_index']}
                                  * Papers: {author['paper_count']}
                            """
                            )

                    with col2:
                        st.markdown("**Publication Timeline**")
                        timeline_data = df_papers.copy()
                        timeline_data["year"] = pd.to_datetime(
                            timeline_data["publication_date"]
                        ).dt.year
                        yearly_papers = (
                            timeline_data.groupby("year")
                            .size()
                            .reset_index(name="papers")
                        )
                        fig = px.bar(
                            yearly_papers,
                            x="year",
                            y="papers",
                            title="Publications by Year",
                        )
                        st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    dashboard = StreamlitDashboard()
    dashboard.run()
