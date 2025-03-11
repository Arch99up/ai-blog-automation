from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import datetime
import csv
import requests
import xml.etree.ElementTree as ET  # Using safer XML parsing

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
            link TEXT UNIQUE,
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

# ✅ Fetch & Store New Articles (Safer Parsing)
def fetch_articles(article_limit=5):
    feeds = get_rss_feeds()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for feed_id, feed_url, last_fetched in feeds:
        try:
            response = requests.get(feed_url, timeout=10)
            response.raise_for_status()

            # Parse RSS using XML (avoiding feedparser issues)
            root = ET.fromstring(response.content)
            articles = root.findall(".//item")

            count = 0
            for item in articles:
                title = item.find("title").text if item.find("title") is not None else "Untitled"
                link = item.find("link").text if item.find("link") is not None else ""
                pub_date = item.find("pubDate").text if item.find("pubDate") is not None else datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                cursor.execute("SELECT COUNT(*) FROM articles WHERE link=?", (link,))
                if cursor.fetchone()[0] == 0:  # Avoid duplicates
                    cursor.execute("INSERT INTO articles (title, link, source, date_created) VALUES (?, ?, ?, ?)",
                                   (title, link, feed_url, pub_date))
                    conn.commit()
                    count += 1

                if count >= article_limit:
                    break  # Stop at the limit

            # ✅ Update last fetched timestamp
            cursor.execute("UPDATE rss_feeds SET last_fetched = ? WHERE id = ?", 
                           (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), feed_id))

        except Exception as e:
            print(f"❌ Error fetching/parsing {feed_url}: {e}")

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

