from flask import Flask, render_template, request, jsonify, redirect, url_for
import feedparser
import markdown
import sqlite3
import datetime
import openai
import csv
from collections import Counter

app = Flask(__name__)

# ✅ Define database path globally
DB_PATH = "articles.db"

# ✅ OpenAI API Key (Replace with your actual key)
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY_HERE"

# ✅ Ensure database setup
def setup_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create required tables
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

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_article_id INTEGER,
            ai_content TEXT,
            date_created TEXT,
            FOREIGN KEY (original_article_id) REFERENCES articles(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rss_feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scoring_parameters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword_weight REAL DEFAULT 1.0,
            word_frequency_weight REAL DEFAULT 1.0,
            stopword_penalty REAL DEFAULT 0.5
        )
    ''')

    # Insert default scoring parameters if not set
    cursor.execute("SELECT COUNT(*) FROM scoring_parameters")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO scoring_parameters (keyword_weight, word_frequency_weight, stopword_penalty) VALUES (1.0, 1.0, 0.5)")

    conn.commit()
    conn.close()

setup_database()  # Ensure database setup at startup

# ✅ Fetch RSS Feeds from database
def get_rss_feeds():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT url FROM rss_feeds")
    feeds = [row[0] for row in cursor.fetchall()]
    conn.close()
    return feeds

# ✅ Fetch and store articles
def fetch_articles():
    feeds = get_rss_feeds()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for feed_url in feeds:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:5]:  # Fetch top 5 per feed
            cursor.execute("SELECT COUNT(*) FROM articles WHERE link=?", (entry.link,))
            if cursor.fetchone()[0] == 0:  # Avoid duplicates
                cursor.execute("INSERT INTO articles (title, link, source, date_created) VALUES (?, ?, ?, ?)",
                               (entry.title, entry.link, feed_url, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
    
    conn.close()

# ✅ Score articles
def score_articles():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Fetch scoring parameters
    cursor.execute("SELECT keyword_weight, word_frequency_weight, stopword_penalty FROM scoring_parameters")
    params = cursor.fetchone()
    keyword_weight, word_freq_weight, stopword_penalty = params

    cursor.execute("SELECT id, title, link FROM articles WHERE relevance_score = 0")
    articles = cursor.fetchall()

    for article in articles:
        words = article[1].lower().split()
        word_counts = Counter(words)

        score = (sum(word_counts.values()) * word_freq_weight) / (len(word_counts) + 1)
        cursor.execute("UPDATE articles SET relevance_score = ? WHERE id = ?", (round(score, 2), article[0]))
    
    conn.commit()
    conn.close()

# ✅ Upload CSV file to batch add RSS feeds
@app.route("/upload_csv", methods=["POST"])
def upload_csv():
    if "file" not in request.files:
        return "No file uploaded", 400

    file = request.files["file"]
    if file.filename == "":
        return "No file selected", 400

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        csv_data = csv.reader(file.read().decode("utf-8").splitlines())
        for row in csv_data:
            cursor.execute("INSERT OR IGNORE INTO rss_feeds (url) VALUES (?)", (row[0],))
        
        conn.commit()
    except Exception as e:
        return str(e), 500
    finally:
        conn.close()

    return redirect(url_for("dashboard"))

# ✅ Send selected articles to OpenAI
@app.route("/send_to_openai", methods=["POST"])
def send_to_openai():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, title FROM articles WHERE selected = 1")
    selected_articles = cursor.fetchall()

    for article in selected_articles:
        prompt = f"Summarize this article: {article[1]}"
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        
        ai_generated_content = response["choices"][0]["message"]["content"]
        cursor.execute("INSERT INTO ai_articles (original_article_id, ai_content, date_created) VALUES (?, ?, ?)",
                       (article[0], ai_generated_content, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))

# ✅ Route: Dashboard
@app.route("/")
def dashboard():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, title, link, source, date_created, relevance_score, selected FROM articles ORDER BY relevance_score DESC")
    articles = cursor.fetchall()

    cursor.execute("SELECT keyword_weight, word_frequency_weight, stopword_penalty FROM scoring_parameters")
    scoring_params = cursor.fetchone()

    conn.close()
    return render_template("index.html", articles=articles, scoring_params=scoring_params)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)

