from flask import Flask, render_template, request, redirect, url_for, g
import sqlite3
import feedparser
import csv
import os

app = Flask(__name__)
DATABASE = "database.db"

# ----------------- DATABASE CONNECTION -----------------
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# ----------------- SETUP DATABASE -----------------
def setup_database():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # Create Feeds Table
        cursor.execute('''CREATE TABLE IF NOT EXISTS feeds (
                            id INTEGER PRIMARY KEY, 
                            url TEXT UNIQUE, 
                            last_fetched TEXT)''')
        
        # Create Raw Articles Table
        cursor.execute('''CREATE TABLE IF NOT EXISTS raw_articles (
                            id INTEGER PRIMARY KEY, 
                            title TEXT, 
                            url TEXT UNIQUE, 
                            content TEXT, 
                            score INTEGER DEFAULT NULL)''')
        
        # Create Enhanced Articles Table
        cursor.execute('''CREATE TABLE IF NOT EXISTS enhanced_articles (
                            id INTEGER PRIMARY KEY, 
                            title TEXT, 
                            url TEXT, 
                            content TEXT)''')
        
        # Create Settings Table for API Key
        cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
                            key TEXT PRIMARY KEY, 
                            value TEXT)''')

        db.commit()

setup_database()

# ----------------- HOME PAGE -----------------
@app.route("/")
def home():
    return redirect(url_for("manage_feeds"))

# ----------------- MANAGE RSS FEEDS -----------------
@app.route("/feeds", methods=["GET"])
def manage_feeds():
    cursor = get_db().cursor()
    cursor.execute("SELECT * FROM feeds")
    feeds = cursor.fetchall()
    return render_template("feeds.html", feeds=feeds)

@app.route("/add_feed", methods=["POST"])
def add_feed():
    url = request.form["rss_url"]
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO feeds (url, last_fetched) VALUES (?, NULL)", (url,))
        db.commit()
    except sqlite3.IntegrityError:
        pass  # Feed already exists
    return redirect(url_for("manage_feeds"))

@app.route("/delete_feed", methods=["POST"])
def delete_feed():
    url = request.form["feed_url"]
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM feeds WHERE url=?", (url,))
    db.commit()
    return redirect(url_for("manage_feeds"))

@app.route("/upload_rss", methods=["POST"])
def upload_rss():
    if "file" not in request.files:
        return redirect(url_for("manage_feeds"))

    file = request.files["file"]
    if file.filename == "":
        return redirect(url_for("manage_feeds"))

    if file:
        db = get_db()
        cursor = db.cursor()
        csv_file = file.read().decode("utf-8").splitlines()
        reader = csv.reader(csv_file)

        for row in reader:
            if row:
                try:
                    cursor.execute("INSERT INTO feeds (url, last_fetched) VALUES (?, NULL)", (row[0],))
                except sqlite3.IntegrityError:
                    pass  # Skip duplicates

        db.commit()
    return redirect(url_for("manage_feeds"))

@app.route("/fetch_articles", methods=["POST"])
def fetch_articles():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT url FROM feeds")
    feeds = cursor.fetchall()

    for feed in feeds:
        feed_url = feed[0]
        parsed_feed = feedparser.parse(feed_url)

        for entry in parsed_feed.entries:
            try:
                cursor.execute("INSERT INTO raw_articles (title, url, content) VALUES (?, ?, ?)", 
                               (entry.title, entry.link, entry.summary))
            except sqlite3.IntegrityError:
                pass  # Skip duplicates

    db.commit()
    return redirect(url_for("manage_articles"))

# ----------------- MANAGE ARTICLES -----------------
@app.route("/articles", methods=["GET"])
def manage_articles():
    cursor = get_db().cursor()
    cursor.execute("SELECT * FROM raw_articles")
    articles = cursor.fetchall()
    return render_template("articles.html", articles=articles)

@app.route("/enhanced_articles", methods=["GET"])
def manage_enhanced_articles():
    cursor = get_db().cursor()
    cursor.execute("SELECT * FROM enhanced_articles")
    articles = cursor.fetchall()
    return render_template("enhanced_articles.html", articles=articles)

# ----------------- ARTICLE SCORING -----------------
SCORING_KEYWORDS = ["AI", "Machine Learning", "Automation", "Data Science", "Business Optimization", "ROI"]

def calculate_score(content):
    score = sum(1 for keyword in SCORING_KEYWORDS if keyword.lower() in content.lower())
    return score

@app.route("/score_articles", methods=["POST"])
def score_articles():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, content FROM raw_articles WHERE score IS NULL")
    articles = cursor.fetchall()

    for article in articles:
        article_id, content = article
        score = calculate_score(content)
        cursor.execute("UPDATE raw_articles SET score=? WHERE id=?", (score, article_id))

    db.commit()
    return redirect(url_for("manage_articles"))

# ----------------- SETTINGS: API KEY -----------------
@app.route("/settings", methods=["GET", "POST"])
def settings():
    db = get_db()
    cursor = db.cursor()
    
    if request.method == "POST":
        api_key = request.form["api_key"]
        cursor.execute("INSERT INTO settings (key, value) VALUES ('api_key', ?) ON CONFLICT(key) DO UPDATE SET value=?", 
                       (api_key, api_key))
        db.commit()

    cursor.execute("SELECT value FROM settings WHERE key='api_key'")
    setting = cursor.fetchone()
    return render_template("settings.html", api_key=setting[0] if setting else "")

# ----------------- RUN APPLICATION -----------------
if __name__ == "__main__":
    app.run(debug=True)
