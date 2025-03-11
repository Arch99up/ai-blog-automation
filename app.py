from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
import feedparser
import os

app = Flask(__name__)
DB_PATH = "database.db"

# Setup Database
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
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            link TEXT UNIQUE,
            source TEXT,
            date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            relevance_score INTEGER DEFAULT 0,
            selected INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            openai_api_key TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scoring_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            keyword TEXT UNIQUE
        )
    """)
    
    conn.commit()
    conn.close()

setup_database()

# Routes
@app.route('/')
def dashboard():
    return render_template("index.html")

@app.route('/feeds', methods=['GET', 'POST'])
def manage_feeds():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        feed_url = request.form.get('feed_url')
        cursor.execute("INSERT OR IGNORE INTO feeds (url) VALUES (?)", (feed_url,))
        conn.commit()
    
    cursor.execute("SELECT * FROM feeds")
    feeds = cursor.fetchall()
    conn.close()
    return render_template("feeds.html", feeds=feeds)

@app.route('/fetch_articles', methods=['POST'])
def fetch_articles():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT url FROM feeds")
    feeds = cursor.fetchall()
    
    for feed in feeds:
        d = feedparser.parse(feed[0])
        for entry in d.entries:
            cursor.execute("INSERT OR IGNORE INTO articles (title, link, source) VALUES (?, ?, ?)",
                           (entry.title, entry.link, feed[0]))
    
    conn.commit()
    conn.close()
    return redirect(url_for('manage_articles'))

@app.route('/articles')
def manage_articles():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM articles ORDER BY date_created DESC")
    articles = cursor.fetchall()
    conn.close()
    return render_template("articles.html", articles=articles)

@app.route('/score_articles', methods=['POST'])
def score_articles():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM articles WHERE relevance_score = 0")
    articles = cursor.fetchall()
    
    cursor.execute("SELECT keyword FROM scoring_keywords")
    keywords = [row[0] for row in cursor.fetchall()]
    
    for article in articles:
        score = sum([article[1].count(kw) for kw in keywords])
        cursor.execute("UPDATE articles SET relevance_score = ? WHERE id = ?", (score, article[0]))
    
    conn.commit()
    conn.close()
    return redirect(url_for('manage_articles'))

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        api_key = request.form.get('openai_api_key')
        cursor.execute("DELETE FROM settings")
        cursor.execute("INSERT INTO settings (openai_api_key) VALUES (?)", (api_key,))
        conn.commit()
    
    cursor.execute("SELECT openai_api_key FROM settings")
    setting = cursor.fetchone()
    conn.close()
    return render_template("settings.html", api_key=setting[0] if setting else "")

@app.route('/manage_keywords', methods=['GET', 'POST'])
def manage_keywords():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        category = request.form.get('category')
        keyword = request.form.get('keyword')
        cursor.execute("INSERT OR IGNORE INTO scoring_keywords (category, keyword) VALUES (?, ?)", (category, keyword))
        conn.commit()
    
    cursor.execute("SELECT * FROM scoring_keywords ORDER BY category")
    keywords = cursor.fetchall()
    conn.close()
    return render_template("keywords.html", keywords=keywords)

if __name__ == '__main__':
    app.run(debug=True)
