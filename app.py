import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, g
import feedparser
from datetime import datetime
import openai

app = Flask(__name__)
app.secret_key = os.urandom(24)

DATABASE = "database.db"


def get_db():
    """Get a connection to the SQLite database."""
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    """Close the database connection after each request."""
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def setup_database():
    """Ensures all required tables exist before the app starts."""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()

        # Create tables if they do not exist
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                last_fetched TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                link TEXT NOT NULL,
                published TIMESTAMP,
                summary TEXT,
                feed_id INTEGER,
                relevance_score INTEGER,
                enhanced_content TEXT,
                FOREIGN KEY(feed_id) REFERENCES feeds(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                openai_api_key TEXT
            )
            """
        )

        db.commit()
        db.close()


@app.route("/")
def index():
    return redirect(url_for("manage_feeds"))


@app.route("/feeds", methods=["GET", "POST"])
def manage_feeds():
    db = get_db()
    cursor = db.cursor()

    if request.method == "POST":
        feed_url = request.form.get("feed_url")
        if feed_url:
            cursor.execute("INSERT INTO feeds (url) VALUES (?)", (feed_url,))
            db.commit()
            flash("Feed added successfully!", "success")
        else:
            flash("Feed URL cannot be empty.", "danger")

    cursor.execute("SELECT * FROM feeds")
    feeds = cursor.fetchall()
    return render_template("feeds.html", feeds=feeds)


@app.route("/delete_feed/<int:feed_id>")
def delete_feed(feed_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
    db.commit()
    flash("Feed deleted successfully!", "success")
    return redirect(url_for("manage_feeds"))


@app.route("/fetch_articles")
def fetch_articles():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM feeds")
    feeds = cursor.fetchall()

    for feed in feeds:
        feed_data = feedparser.parse(feed["url"])
        for entry in feed_data.entries:
            cursor.execute("SELECT * FROM articles WHERE link = ?", (entry.link,))
            if cursor.fetchone() is None:
                published = (
                    datetime(*entry.published_parsed[:6])
                    if hasattr(entry, "published_parsed")
                    else None
                )
                cursor.execute(
                    """
                    INSERT INTO articles (title, link, published, summary, feed_id)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (entry.title, entry.link, published, entry.get("summary", ""), feed["id"]),
                )

        cursor.execute("UPDATE feeds SET last_fetched = ? WHERE id = ?", (datetime.now(), feed["id"]))

    db.commit()
    flash("Articles fetched successfully!", "success")
    return redirect(url_for("manage_articles"))


@app.route("/articles")
def manage_articles():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM articles")
    articles = cursor.fetchall()
    return render_template("articles.html", articles=articles)


@app.route("/delete_article/<int:article_id>")
def delete_article(article_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM articles WHERE id = ?", (article_id,))
    db.commit()
    flash("Article deleted successfully!", "success")
    return redirect(url_for("manage_articles"))


@app.route("/settings", methods=["GET", "POST"])
def settings():
    db = get_db()
    cursor = db.cursor()

    if request.method == "POST":
        api_key = request.form["api_key"]
        cursor.execute("DELETE FROM settings")
        cursor.execute("INSERT INTO settings (openai_api_key) VALUES (?)", (api_key,))
        db.commit()
        flash("API Key updated!", "success")

    cursor.execute("SELECT openai_api_key FROM settings")
    api_key = cursor.fetchone()
    return render_template("settings.html", api_key=api_key)


if __name__ == "__main__":
    setup_database()  # Ensures database tables are created
    app.run(host="0.0.0.0", port=10000, debug=True)
