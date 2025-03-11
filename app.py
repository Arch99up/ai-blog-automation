from flask import Flask, render_template, request, jsonify
import feedparser
import markdown
import requests
import openai
import nltk
from collections import Counter

import nltk
nltk.download('punkt')
nltk.download('stopwords')
nltk.download('averaged_perceptron_tagger')
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

app = Flask(__name__)

# OpenAI API Key (Replace with your actual key)
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY_HERE"

# Sample RSS Feeds
RSS_FEEDS = [
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "https://www.theverge.com/rss/index.xml",
    "https://techcrunch.com/feed/",
]

# Function to fetch and parse RSS feeds
def fetch_articles():
    articles = []
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:5]:  # Fetch only top 5 articles per feed
            articles.append({
                "title": entry.title,
                "link": entry.link,
                "summary": markdown.markdown(entry.summary) if "summary" in entry else "No summary available",
                "source": feed_url
            })
    return articles

# Function to score articles based on keyword frequency & uniqueness
def score_articles(articles):
    stop_words = set(stopwords.words("english"))
    scores = []
    
    for article in articles:
        words = word_tokenize(article["title"].lower() + " " + article["summary"].lower())
        words = [w for w in words if w.isalnum() and w not in stop_words]
        
        word_counts = Counter(words)
        score = sum(word_counts.values()) / (len(word_counts) + 1)  # Simple relevance score
        
        scores.append({
            "title": article["title"],
            "link": article["link"],
            "summary": article["summary"],
            "source": article["source"],
            "score": round(score, 2)
        })
    
    return sorted(scores, key=lambda x: x["score"], reverse=True)

# Route: Fetch & Score Articles
@app.route("/fetch")
def fetch_and_score():
    articles = fetch_articles()
    scored_articles = score_articles(articles)
    return jsonify(scored_articles)

# Route: Internal Dashboard (Simple UI)
@app.route("/")
def dashboard():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
