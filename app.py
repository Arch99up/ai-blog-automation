from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import feedparser
import requests

app = Flask(__name__)
DATABASE = "ai_blog.db"

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

    conn.commit()
    conn.close()

# Run database initialization before the first request
@app.before_first_request
def setup():
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

if __name__ == '__main__':
    init_db()  # Ensure database is created on startup
    app.run(debug=True)
