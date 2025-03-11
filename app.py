import os
import sqlite3
import feedparser
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

app = Flask(__name__)
app.secret_key = os.urandom(24)
DATABASE = "database.db"

# Ensure database and tables exist
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def setup_database():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            last_fetched TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feed_url TEXT NOT NULL,
            title TEXT NOT NULL,
            link TEXT NOT NULL,
            summary TEXT,
            published TIMESTAMP,
            relevance_score INTEGER DEFAULT 0
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scoring_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            keyword TEXT UNIQUE NOT NULL
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            openai_api_key TEXT
        )
        """)
        conn.commit()

setup_database()

# Routes
@app.route('/')
def home():
    return redirect(url_for('manage_feeds'))

@app.route('/feeds', methods=['GET', 'POST'])
def manage_feeds():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        feed_url = request.form['rss_url']
        try:
            cursor.execute("INSERT INTO feeds (url) VALUES (?)", (feed_url,))
            conn.commit()
            flash("Feed added successfully!", "success")
        except sqlite3.IntegrityError:
            flash("Feed already exists!", "warning")

    cursor.execute("SELECT * FROM feeds")
    feeds = cursor.fetchall()
    conn.close()
    return render_template('feeds.html', feeds=feeds)

@app.route('/delete_feed', methods=['POST'])
def delete_feed():
    feed_url = request.form['feed_url']
    conn = get_db_connection()
    conn.execute("DELETE FROM feeds WHERE url = ?", (feed_url,))
    conn.commit()
    conn.close()
    flash("Feed deleted successfully!", "success")
    return redirect(url_for('manage_feeds'))

@app.route('/fetch_articles', methods=['POST'])
def fetch_articles():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT url FROM feeds")
    feeds = cursor.fetchall()

    for feed in feeds:
        feed_url = feed['url']
        parsed_feed = feedparser.parse(feed_url)

        for entry in parsed_feed.entries:
            try:
                cursor.execute("""
                INSERT INTO articles (feed_url, title, link, summary, published)
                VALUES (?, ?, ?, ?, ?)
                """, (feed_url, entry.title, entry.link, entry.summary, entry.published))
            except sqlite3.IntegrityError:
                continue

    conn.commit()
    conn.close()
    flash("Articles fetched successfully!", "success")
    return redirect(url_for('manage_feeds'))

@app.route('/articles')
def manage_articles():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM articles ORDER BY published DESC")
    articles = cursor.fetchall()
    conn.close()
    return render_template('articles.html', articles=articles)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        api_key = request.form['openai_api_key']
        cursor.execute("DELETE FROM settings")
        cursor.execute("INSERT INTO settings (openai_api_key) VALUES (?)", (api_key,))
        conn.commit()
        flash("API Key updated!", "success")

    cursor.execute("SELECT openai_api_key FROM settings")
    setting = cursor.fetchone()
    conn.close()
    return render_template('settings.html', api_key=setting['openai_api_key'] if setting else "")

if __name__ == '__main__':
    app.run(debug=True)

