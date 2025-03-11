from flask import Flask, render_template, request, jsonify, redirect, url_for
import feedparser
import markdown
import sqlite3
import datetime
import openai
import nltk
from collections import Counter

nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

def setup_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create table for storing articles
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            link TEXT,
            source TEXT,
            date_created TEXT,
            relevance_score REAL,
            selected INTEGER DEFAULT 0
        )
    ''')

    # Create table for storing RSS feeds
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rss_feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE
        )
    ''')

    conn.commit()
    conn.close()

# Run this when the app starts
setup_database()


app = Flask(__name__)
DB_PATH = "articles.db"  # Database file

# OpenAI API Key (Replace with your actual key)
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY_HERE"

# Function to fetch RSS feeds from database
def get_rss_feeds():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT url FROM rss_feeds")
    feeds = [row[0] for row in cursor.fetchall()]
    conn.close()
    return feeds

# Function to fetch and store articles
def fetch_articles():
    feeds = get_rss_feeds()
    articles = []

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for feed_url in feeds:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:5]:  # Fetch top 5 per feed
            cursor.execute("SELECT COUNT(*) FROM articles WHERE link=?", (entry.link,))
            if cursor.fetchone()[0] == 0:  # Avoid duplicates
                cursor.execute("INSERT INTO articles (title, link, source, date_created, relevance_score) VALUES (?, ?, ?, ?, ?)",
                               (entry.title, entry.link, feed_url, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 0))
                conn.commit()
    
    conn.close()

# Function to retrieve articles from database
def get_articles():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, link, source, date_created, relevance_score, selected FROM articles ORDER BY relevance_score DESC")
    articles = cursor.fetchall()
    conn.close()
    return articles

# Function to update article selection for OpenAI processing
@app.route("/update_selection", methods=["POST"])
def update_selection():
    article_id = request.form.get("article_id")
    selected = request.form.get("selected")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE articles SET selected=? WHERE id=?", (selected, article_id))
    conn.commit()
    conn.close()
    return jsonify({"message": "Selection updated successfully"})

# Route: Fetch & Store Articles
@app.route("/fetch_articles", methods=["POST"])
def fetch_and_store_articles():
    fetch_articles()
    return redirect(url_for("dashboard"))

# Route: Add RSS Feed
@app.route("/add_rss_feed", methods=["POST"])
def add_rss_feed():
    feed_url = request.form.get("feed_url")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO rss_feeds (url) VALUES (?)", (feed_url,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Ignore duplicate feeds
    conn.close()
    return redirect(url_for("dashboard"))

# Route: Dashboard (Display Articles)
@app.route("/")
def dashboard():
    articles = get_articles()
    return render_template("index.html", articles=articles)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
