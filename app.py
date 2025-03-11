from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
import feedparser
import requests
import os
from datetime import datetime

app = Flask(__name__)
DB_PATH = "database.db"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

# ✅ Scoring Keywords (Default List)
SCORING_KEYWORDS = {
    "business": ["efficiency", "cost savings", "revenue", "optimization", "transformation", "automation", "performance", "process improvement", "streamlining"],
    "financial": ["ROI", "profit", "margin", "revenue growth", "cost reduction", "investment", "financial impact", "savings", "budgeting"],
    "productivity": ["workflow", "productivity", "KPIs", "operational improvement", "benchmarking", "best practices"],
    "technology": ["machine learning", "deep learning", "automation", "digitalization", "AI", "robotics", "predictive analytics", "NLP"],
    "quantitative": ["percentage", "growth", "increase", "decrease", "uplift", "reduction", "measurable results", "metrics"],
    "negative": ["entertainment", "politics", "celebrity", "sports", "gossip"]  # Lowers relevance score
}

# ✅ Initialize Database
def setup_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Table for RSS feeds
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rss_feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            last_fetched TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table for articles
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            link TEXT UNIQUE,
            summary TEXT,
            published TEXT,
            feed_id INTEGER,
            relevance_score REAL DEFAULT NULL,
            FOREIGN KEY(feed_id) REFERENCES rss_feeds(id)
        )
    """)

    # Table for scoring keywords
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scoring_keywords (
            category TEXT,
            keyword TEXT UNIQUE
        )
    """)

    # Insert default keywords if table is empty
    cursor.execute("SELECT COUNT(*) FROM scoring_keywords")
    if cursor.fetchone()[0] == 0:
        for category, words in SCORING_KEYWORDS.items():
            for word in words:
                cursor.execute("INSERT INTO scoring_keywords (category, keyword) VALUES (?, ?)", (category, word))

    conn.commit()
    conn.close()

setup_database()


# ✅ Endpoint: Fetch & Manage Keywords
@app.route("/get_keywords", methods=["GET"])
def get_keywords():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT category, keyword FROM scoring_keywords")
    keywords = [{"category": row[0], "keyword": row[1]} for row in cursor.fetchall()]
    conn.close()
    return jsonify(keywords)


@app.route("/add_keyword", methods=["POST"])
def add_keyword():
    data = request.json
    category = data.get("category")
    keyword = data.get("keyword")
    if not category or not keyword:
        return jsonify({"error": "Category and keyword are required"}), 400

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO scoring_keywords (category, keyword) VALUES (?, ?)", (category, keyword))
    conn.commit()
    conn.close()
    return jsonify({"message": f"Keyword '{keyword}' added to category '{category}'"})


@app.route("/delete_keyword", methods=["POST"])
def delete_keyword():
    data = request.json
    keyword = data.get("keyword")
    if not keyword:
        return jsonify({"error": "Keyword is required"}), 400

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM scoring_keywords WHERE keyword = ?", (keyword,))
    conn.commit()
    conn.close()
    return jsonify({"message": f"Keyword '{keyword}' removed"})


# ✅ Scoring Function
def score_article(title, summary):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT category, keyword FROM scoring_keywords")
    keywords = cursor.fetchall()
    conn.close()

    keyword_dict = {}
    for category, keyword in keywords:
        if category not in keyword_dict:
            keyword_dict[category] = []
        keyword_dict[category].append(keyword)

    title = title.lower()
    summary = summary.lower()
    
    score = 0
    for category, words in keyword_dict.items():
        for word in words:
            if word in title or word in summary:
                if category == "negative":
                    score -= 5
                else:
                    score += 10

    return max(score, 0)  # Ensure score is not negative


# ✅ Endpoint: Score Unscored Articles
@app.route("/score_articles", methods=["POST"])
def score_articles():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, summary FROM articles WHERE relevance_score IS NULL")
    articles = cursor.fetchall()

    for article_id, title, summary in articles:
        score = score_article(title, summary)
        cursor.execute("UPDATE articles SET relevance_score = ? WHERE id = ?", (score, article_id))

    conn.commit()
    conn.close()
    return jsonify({"message": f"Scored {len(articles)} articles."})


if __name__ == "__main__":
    app.run(debug=True)
