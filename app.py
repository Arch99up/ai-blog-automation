from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import feedparser
import requests

app = Flask(__name__)
DATABASE = "ai_blog.db"

# ✅ FIX: Ensure the database is initialized on startup
def init_db():
    """Creates necessary tables if they don't exist."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Create feeds table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feed_url TEXT UNIQUE NOT NULL,
            last_fetched TIMESTAMP DEFAULT NULL
        )
    """)

    # Create articles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            link TEXT UNIQUE NOT NULL,
            published TEXT
        )
    """)

    # Create enhanced articles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS enhanced_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            link TEXT UNIQUE NOT NULL,
            published TEXT,
            enhanced_content TEXT
        )
    """)

    # Create settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key TEXT
        )
    """)

    conn.commit()
    conn.close()

# ✅ RUN DATABASE INIT ON STARTUP (Fixes missing tables issue)
init_db()

@app.route('/')
def home():
    return redirect(url_for('manage_feeds'))

@app.route('/feeds', methods=['GET', 'POST'])
def manage_feeds():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    if request.method == 'POST':
        feed_url = request.form.get('rss_url')
        if feed_url:
            try:
                cursor.execute("INSERT INTO feeds (feed_url) VALUES (?)", (feed_url,))
                conn.commit()
            except sqlite3.IntegrityError:
                pass  # Ignore duplicate URLs

    cursor.execute("SELECT * FROM feeds")
    feeds = cursor.fetchall()
    conn.close()

    return render_template('feeds.html', feeds=feeds)

@app.route('/delete_feed', methods=['POST'])
def delete_feed():
    feed_url = request.form.get('feed_url')

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM feeds WHERE feed_url = ?", (feed_url,))
    conn.commit()
    conn.close()

    return redirect(url_for('manage_feeds'))

@app.route('/fetch_articles', methods=['POST'])
def fetch_articles():
    article_limit = int(request.form.get('article_limit', 10))  # User-defined limit

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT feed_url FROM feeds")
    feeds = cursor.fetchall()

    for feed in feeds:
        feed_url = feed[0]

        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(feed_url, headers=headers, timeout=10)
            response.raise_for_status()  # Raise error for bad responses

            parsed_feed = feedparser.parse(response.text)

            for entry in parsed_feed.entries[:article_limit]:
                title = entry.get("title", "No Title")
                link = entry.get("link", "No Link")
                published = entry.get("published", "Unknown Date")

                cursor.execute(
                    "INSERT OR IGNORE INTO articles (title, link, published) VALUES (?, ?, ?)",
                    (title, link, published),
                )

        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching {feed_url}: {e}")

        except Exception as e:
            print(f"❌ Error parsing {feed_url}: {e}")

    conn.commit()
    conn.close()

    return redirect(url_for('manage_feeds'))

@app.route('/articles')
def manage_articles():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM articles ORDER BY id DESC")
    articles = cursor.fetchall()
    conn.close()
    return render_template('articles.html', articles=articles)

@app.route('/score_articles', methods=['POST'])
def score_articles():
    """Placeholder route for scoring articles - will need actual logic"""
    return "Scoring functionality not implemented yet", 501  # Not Implemented

@app.route('/enhanced_articles')
def enhanced_articles():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM enhanced_articles ORDER BY id DESC")
    articles = cursor.fetchall()
    conn.close()
    return render_template('enhanced_articles.html', articles=articles)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    if request.method == 'POST':
        api_key = request.form.get('api_key')
        cursor.execute("DELETE FROM settings")  # Ensure only one key is stored
        cursor.execute("INSERT INTO settings (api_key) VALUES (?)", (api_key,))
        conn.commit()

    cursor.execute("SELECT api_key FROM settings LIMIT 1")
    setting = cursor.fetchone()
    conn.close()

    return render_template('settings.html', api_key=setting[0] if setting else "")

if __name__ == '__main__':
    app.run(debug=True)
