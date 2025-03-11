import os
import sqlite3
import csv
import feedparser
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

app = Flask(__name__)
app.secret_key = "supersecretkey"

DB_PATH = "database.db"

# Ensure the database is set up
def setup_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            last_fetched TIMESTAMP DEFAULT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feed_url TEXT,
            title TEXT,
            link TEXT,
            published TEXT,
            summary TEXT,
            score INTEGER DEFAULT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key TEXT
        )
    """)
    
    conn.commit()
    conn.close()

setup_database()


# 1️⃣ **Manage Feeds Section** - Upload CSV and Add Single URL
@app.route('/feeds', methods=['GET'])
def manage_feeds():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM feeds")
    feeds = cursor.fetchall()
    conn.close()
    return render_template("feeds.html", feeds=feeds)


@app.route('/upload_rss', methods=['POST'])
def upload_rss():
    """ Handles CSV uploads for bulk RSS feed addition """
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('manage_feeds'))

    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('manage_feeds'))

    if file:
        file_path = os.path.join('uploads', file.filename)
        file.save(file_path)

        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if len(row) > 0:
                    add_feed(row[0])  # Process each RSS URL

        os.remove(file_path)  # Clean up uploaded file
        flash('RSS Feeds uploaded successfully')

    return redirect(url_for('manage_feeds'))


@app.route('/add_feed', methods=['POST'])
def add_feed_route():
    """ Allows adding a single RSS feed manually """
    url = request.form.get('rss_url')
    if url:
        add_feed(url)
        flash("Feed added successfully")
    else:
        flash("Invalid URL")
    return redirect(url_for('manage_feeds'))


def add_feed(url):
    """ Helper function to add an RSS feed to the database """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO feeds (url) VALUES (?)", (url,))
        conn.commit()
    except sqlite3.IntegrityError:
        flash("Feed already exists")
    conn.close()


# 2️⃣ **Fetch Articles from Feeds**
@app.route('/fetch_articles', methods=['POST'])
def fetch_articles():
    """ Fetches articles from all stored RSS feeds """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT url FROM feeds")
    feeds = cursor.fetchall()

    for feed in feeds:
        feed_url = feed[0]
        parsed_feed = feedparser.parse(feed_url)

        if parsed_feed.entries:
            for entry in parsed_feed.entries:
                title = entry.get("title", "No Title")
                link = entry.get("link", "")
                published = entry.get("published", "Unknown Date")
                summary = entry.get("summary", "No Summary")

                cursor.execute("""
                    INSERT INTO articles (feed_url, title, link, published, summary)
                    VALUES (?, ?, ?, ?, ?)
                """, (feed_url, title, link, published, summary))

    conn.commit()
    conn.close()
    flash("Articles fetched successfully")
    return redirect(url_for('manage_articles'))


# 3️⃣ **Manage Articles Section**
@app.route('/articles', methods=['GET'])
def manage_articles():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM articles ORDER BY id DESC")
    articles = cursor.fetchall()
    conn.close()
    return render_template("articles.html", articles=articles)


# 4️⃣ **Settings Page (API Key)**
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if request.method == 'POST':
        api_key = request.form.get("api_key")
        cursor.execute("DELETE FROM settings")  # Only store one API key
        cursor.execute("INSERT INTO settings (api_key) VALUES (?)", (api_key,))
        conn.commit()
        flash("API Key Updated")

    cursor.execute("SELECT api_key FROM settings LIMIT 1")
    setting = cursor.fetchone()
    conn.close()

    return render_template("settings.html", api_key=setting[0] if setting else "")


# Run the application
if __name__ == '__main__':
    app.run(debug=True)
