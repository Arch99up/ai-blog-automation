from flask import Flask, render_template, request, redirect, url_for
import feedparser
import sqlite3
import datetime
import csv

app = Flask(__name__)

# ✅ Database Path
DB_PATH = "articles.db"

# ✅ Ensure Database Setup
def setup_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Ensure RSS Feeds table includes last_fetched column
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rss_feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            last_fetched TEXT DEFAULT NULL
        )
    ''')

    # Ensure Articles table exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            link TEXT,
            source TEXT,
            date_created TEXT,
            relevance_score REAL DEFAULT 0,
            selected INTEGER DEFAULT 0
        )
    ''')

    conn.commit()
    conn.close()

setup_database()  # Ensure database setup at startup

# ✅ Fetch RSS Feeds from database
def get_rss_feeds():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, url, last_fetched FROM rss_feeds ORDER BY last_fetched DESC NULLS LAST")
    feeds = cursor.fetchall()
    conn.close()
    return feeds

# ✅ Fetch & Store New Articles (Specify Number Per Source)
def fetch_articles(article_limit=5):
    feeds = get_rss_feeds()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for feed_id, feed_url, last_fetched in feeds:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:article_limit]:  # Fetch specified number of articles per feed
            cursor.execute("SELECT COUNT(*) FROM articles WHERE link=?", (entry.link,))
            if cursor.fetchone()[0] == 0:  # Avoid duplicates
                cursor.execute("INSERT INTO articles (title, link, source, date_created) VALUES (?, ?, ?, ?)",
                               (entry.title, entry.link, feed_url, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()

        # ✅ Update last fetched timestamp
        cursor.execute("UPDATE rss_feeds SET last_fetched = ? WHERE id = ?", (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), feed_id))

    conn.commit()
    conn.close()

# ✅ Upload CSV or Single URL for RSS Feeds
@app.route("/upload_rss", methods=["POST"])
def upload_rss():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Handle single URL input
    if "rss_url" in request.form and request.form["rss_url"].strip():
        cursor.execute("INSERT OR IGNORE INTO rss_feeds (url) VALUES (?)", (request.form["rss_url"].strip(),))

    # Handle CSV Upload
    if "file" in request.files:
        file = request.files["file"]
        if file.filename != "":
            csv_data = csv.reader(file.read().decode("utf-8").splitlines())
            for row in csv_data:
                cursor.execute("INSERT OR IGNORE INTO rss_feeds (url) VALUES (?)", (row[0],))

    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))

# ✅ Route to Fetch New Articles (User-defined Limit)
@app.route("/fetch_articles", methods=["POST"])
def fetch_articles_route():
    article_limit = int(request.form.get("article_limit", 5))  # Default to 5 per source
    fetch_articles(article_limit)
    return redirect(url_for("dashboard"))

# ✅ Route: Dashboard
@app.route("/")
def dashboard():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Fetch articles & RSS feeds with last fetch timestamps
    cursor.execute("SELECT id, title, link, source, date_created, relevance_score, selected FROM articles ORDER BY relevance_score DESC")
    articles = cursor.fetchall()

    feeds = get_rss_feeds()

    conn.close()
    return render_template("index.html", articles=articles, feeds=feeds)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
