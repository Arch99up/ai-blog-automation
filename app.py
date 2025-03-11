from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
import feedparser
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"
DB_PATH = "ai_blog.db"

def setup_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            last_fetched TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            link TEXT UNIQUE,
            source TEXT,
            date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            relevance_score INTEGER DEFAULT NULL,
            selected BOOLEAN DEFAULT FALSE
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scoring_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            keyword TEXT UNIQUE
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_processed_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_article_id INTEGER,
            enhanced_text TEXT,
            FOREIGN KEY (original_article_id) REFERENCES raw_articles(id)
        )
    """)
    
    conn.commit()
    conn.close()

setup_database()

@app.route("/")
def dashboard():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM feeds")
    total_feeds = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM raw_articles WHERE date_created >= datetime('now', '-1 day')")
    new_articles_today = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM raw_articles WHERE relevance_score IS NOT NULL AND date_created >= datetime('now', '-1 day')")
    scored_articles_today = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM ai_processed_articles")
    ai_processed_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM raw_articles")
    database_size = cursor.fetchone()[0]
    
    conn.close()
    
    return render_template("dashboard.html", 
                           total_feeds=total_feeds,
                           new_articles_today=new_articles_today,
                           scored_articles_today=scored_articles_today,
                           ai_processed_count=ai_processed_count,
                           database_size=database_size)

@app.route("/manage_feeds", methods=["GET", "POST"])
def manage_feeds():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if request.method == "POST":
        url = request.form["feed_url"]
        try:
            cursor.execute("INSERT INTO feeds (url) VALUES (?)", (url,))
            conn.commit()
            flash("Feed added successfully", "success")
        except sqlite3.IntegrityError:
            flash("Feed already exists", "danger")
    cursor.execute("SELECT * FROM feeds")
    feeds = cursor.fetchall()
    conn.close()
    return render_template("manage_feeds.html", feeds=feeds)

@app.route("/fetch_articles", methods=["POST"])
def fetch_articles():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT url FROM feeds")
    feeds = cursor.fetchall()
    
    for feed_url in feeds:
        feed = feedparser.parse(feed_url[0])
        for entry in feed.entries:
            title = entry.title
            link = entry.link
            source = feed_url[0]
            try:
                cursor.execute("INSERT INTO raw_articles (title, link, source) VALUES (?, ?, ?)", (title, link, source))
            except sqlite3.IntegrityError:
                continue
    conn.commit()
    conn.close()
    flash("Articles fetched successfully!", "success")
    return redirect(url_for("manage_feeds"))

@app.route("/manage_raw_articles")
def manage_raw_articles():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM raw_articles ORDER BY date_created DESC")
    articles = cursor.fetchall()
    conn.close()
    return render_template("manage_raw_articles.html", articles=articles)

@app.route("/score_articles", methods=["POST"])
def score_articles():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM raw_articles WHERE relevance_score IS NULL")
    unscored_articles = cursor.fetchall()
    cursor.execute("SELECT keyword FROM scoring_keywords")
    keywords = [row[0] for row in cursor.fetchall()]
    
    for article in unscored_articles:
        score = sum([1 for word in keywords if word.lower() in article[1].lower()])
        cursor.execute("UPDATE raw_articles SET relevance_score = ? WHERE id = ?", (score, article[0]))
    
    conn.commit()
    conn.close()
    flash("Articles scored successfully!", "success")
    return redirect(url_for("manage_raw_articles"))

@app.route("/manage_enhanced_articles")
def manage_enhanced_articles():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ai_processed_articles")
    enhanced_articles = cursor.fetchall()
    conn.close()
    return render_template("manage_enhanced_articles.html", articles=enhanced_articles)

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        openai_key = request.form["openai_api_key"]
        os.environ["OPENAI_API_KEY"] = openai_key
        flash("API Key updated successfully!", "success")
    return render_template("settings.html", openai_api_key=os.environ.get("OPENAI_API_KEY", ""))

if __name__ == "__main__":
    app.run(debug=True)
