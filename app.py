import os
import sqlite3
import feedparser
import csv
from flask import Flask, render_template, request, redirect, url_for, jsonify

app = Flask(__name__)

DB_PATH = "database.db"

# Initialize the database
def setup_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Table for storing RSS feeds
    cursor.execute('''CREATE TABLE IF NOT EXISTS rss_feeds (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT UNIQUE,
                        last_fetched TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # Table for storing fetched articles
    cursor.execute('''CREATE TABLE IF NOT EXISTS articles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,
                        link TEXT UNIQUE,
                        source TEXT,
                        date_created TEXT,
                        relevance_score INTEGER DEFAULT 0,
                        selected BOOLEAN DEFAULT 0)''')

    # Table for storing scoring keywords
    cursor.execute('''CREATE TABLE IF NOT EXISTS scoring_keywords (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        category TEXT,
                        keyword TEXT UNIQUE)''')

    # Insert default keywords (ignore duplicates)
    default_keywords = {
        "AI Applications": ["machine learning", "artificial intelligence", "neural networks", "deep learning"],
        "Business Impact": ["ROI", "efficiency", "cost reduction", "profitability", "business transformation"],
        "Use Cases": ["customer service automation", "predictive analytics", "supply chain optimization"],
        "Tech Stack": ["OpenAI", "ChatGPT", "NLP", "computer vision"]
    }

    for category, words in default_keywords.items():
        for word in words:
            cursor.execute("INSERT OR IGNORE INTO scoring_keywords (category, keyword) VALUES (?, ?)", (category, word))

    conn.commit()
    conn.close()

setup_database()

# Fetch all RSS feeds
def get_rss_feeds():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, url, last_fetched FROM rss_feeds ORDER BY last_fetched DESC")
    feeds = cursor.fetchall()
    conn.close()
    return feeds

# Fetch new articles
def fetch_articles(article_limit=10):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT url FROM rss_feeds")
    feeds = cursor.fetchall()

    for feed_url in feeds:
        feed_url = feed_url[0]
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:article_limit]:
                title = entry.title
                link = entry.link
                source = feed.feed.title if 'title' in feed.feed else "Unknown"
                date_created = entry.published if 'published' in entry else "Unknown"

                # Avoid duplicates
                cursor.execute("SELECT COUNT(*) FROM articles WHERE link = ?", (link,))
                if cursor.fetchone()[0] == 0:
                    cursor.execute("INSERT INTO articles (title, link, source, date_created) VALUES (?, ?, ?, ?)",
                                   (title, link, source, date_created))
        except Exception as e:
            print(f"❌ Error fetching/parsing {feed_url}: {str(e)}")

    conn.commit()
    conn.close()

# Score articles based on keywords
def score_articles():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, title FROM articles WHERE relevance_score = 0")
    articles = cursor.fetchall()

    cursor.execute("SELECT keyword FROM scoring_keywords")
    keywords = [row[0] for row in cursor.fetchall()]

    for article_id, title in articles:
        relevance_score = sum(1 for word in keywords if word.lower() in title.lower())
        cursor.execute("UPDATE articles SET relevance_score = ? WHERE id = ?", (relevance_score, article_id))

    conn.commit()
    conn.close()

# Get articles
def get_articles():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, link, source, date_created, relevance_score, selected FROM articles ORDER BY relevance_score DESC")
    articles = cursor.fetchall()
    conn.close()
    return articles

# Get scoring keywords
def get_keywords():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT category, keyword FROM scoring_keywords ORDER BY category")
    keywords = cursor.fetchall()
    conn.close()
    return keywords

# Routes
@app.route("/")
def dashboard():
    feeds = get_rss_feeds()
    articles = get_articles()
    keywords = get_keywords()
    return render_template("index.html", feeds=feeds, articles=articles, keywords=keywords)

@app.route("/upload_rss", methods=["POST"])
def upload_rss():
    file = request.files.get("rss_csv")
    rss_url = request.form.get("rss_url")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if file:
        csv_data = file.read().decode("utf-8").splitlines()
        reader = csv.reader(csv_data)
        for row in reader:
            url = row[0]
            cursor.execute("INSERT OR IGNORE INTO rss_feeds (url) VALUES (?)", (url,))

    if rss_url:
        cursor.execute("INSERT OR IGNORE INTO rss_feeds (url) VALUES (?)", (rss_url,))

    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))

@app.route("/fetch_articles", methods=["POST"])
def fetch_articles_route():
    fetch_articles()
    return redirect(url_for("dashboard"))

@app.route("/score_articles", methods=["POST"])
def score_articles_route():
    score_articles()
    return redirect(url_for("dashboard"))

@app.route("/update_keywords", methods=["POST"])
def update_keywords():
    category = request.form.get("category")
    keyword = request.form.get("keyword")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO scoring_keywords (category, keyword) VALUES (?, ?)", (category, keyword))
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    app.run(debug=True)
