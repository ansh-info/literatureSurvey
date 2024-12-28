-- Create database if it doesn't exist
CREATE DATABASE IF NOT EXISTS scholar_db;
USE scholar_db;

-- Create tables
CREATE TABLE topics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE papers (
    id VARCHAR(255) PRIMARY KEY,
    title TEXT,
    abstract TEXT,
    journal VARCHAR(255),
    url TEXT,
    publication_date DATE,
    citation_count INT,
    h_index FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE authors (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255),
    h_index INT,
    citation_count INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE paper_authors (
    paper_id VARCHAR(255),
    author_id VARCHAR(255),
    PRIMARY KEY (paper_id, author_id),
    FOREIGN KEY (paper_id) REFERENCES papers(id),
    FOREIGN KEY (author_id) REFERENCES authors(id)
);

CREATE TABLE topic_papers (
    topic_id INT,
    paper_id VARCHAR(255),
    paper_type ENUM('positive', 'negative', 'recommended'),
    use_for_recommendation BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (topic_id, paper_id),
    FOREIGN KEY (topic_id) REFERENCES topics(id),
    FOREIGN KEY (paper_id) REFERENCES papers(id)
);

CREATE TABLE paper_recommendations (
    source_paper_id VARCHAR(255),
    recommended_paper_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_paper_id, recommended_paper_id),
    FOREIGN KEY (source_paper_id) REFERENCES papers(id),
    FOREIGN KEY (recommended_paper_id) REFERENCES papers(id)
);
