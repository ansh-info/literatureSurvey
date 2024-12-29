-- Create database
CREATE DATABASE IF NOT EXISTS scholar_db;
USE scholar_db;

-- Topics table to store research topics
CREATE TABLE topics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Papers table to store paper details
CREATE TABLE papers (
    id VARCHAR(255) PRIMARY KEY,  -- Semantic Scholar paper ID
    title TEXT NOT NULL,
    abstract TEXT,
    url TEXT,
    publication_date DATE,
    journal VARCHAR(255),
    citation_count INT DEFAULT 0,
    h_index FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Authors table
CREATE TABLE authors (
    id VARCHAR(255) PRIMARY KEY,  -- Semantic Scholar author ID
    name VARCHAR(255) NOT NULL,
    h_index INT,
    citation_count INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Paper-Author relationship
CREATE TABLE paper_authors (
    paper_id VARCHAR(255),
    author_id VARCHAR(255),
    author_order INT,  -- To maintain author order as shown in papers
    PRIMARY KEY (paper_id, author_id),
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES authors(id) ON DELETE CASCADE
);

-- Topic-Paper relationship with classification
CREATE TABLE topic_papers (
    topic_id INT,
    paper_id VARCHAR(255),
    paper_type ENUM('positive', 'negative', 'recommended') NOT NULL,
    use_for_recommendation BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (topic_id, paper_id),
    FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE,
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
);

-- Paper recommendations
CREATE TABLE paper_recommendations (
    source_paper_id VARCHAR(255),
    recommended_paper_id VARCHAR(255),
    recommendation_order INT,  -- To maintain order of recommendations
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_paper_id, recommended_paper_id),
    FOREIGN KEY (source_paper_id) REFERENCES papers(id) ON DELETE CASCADE,
    FOREIGN KEY (recommended_paper_id) REFERENCES papers(id) ON DELETE CASCADE
);

-- Markdown content for papers (for mkdocs)
CREATE TABLE paper_markdown (
    paper_id VARCHAR(255) PRIMARY KEY,
    markdown_content TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
);

-- Topic markdown content (for mkdocs)
CREATE TABLE topic_markdown (
    topic_id INT PRIMARY KEY,
    markdown_content TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
);

-- Create indexes for better query performance
CREATE INDEX idx_papers_date ON papers(publication_date);
CREATE INDEX idx_papers_citations ON papers(citation_count);
CREATE INDEX idx_authors_hindex ON authors(h_index);
CREATE INDEX idx_topic_papers_type ON topic_papers(paper_type);
