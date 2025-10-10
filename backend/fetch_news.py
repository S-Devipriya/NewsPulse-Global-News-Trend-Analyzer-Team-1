#!/usr/bin/env python
# coding: utf-8

# In[6]:


import os
from dotenv import load_dotenv
import requests
import mysql.connector
from datetime import datetime
from text_processing import preprocess_text  # Import preprocessing function

load_dotenv()

def connect_db():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB")
    )

def convert_publishedAt(publishedAt_str):
    try:
        dt = datetime.strptime(publishedAt_str, "%Y-%m-%dT%H:%M:%SZ")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None

def insert_news(article):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(1) FROM news WHERE url = %s", (article.get("url"),))
    exists = cursor.fetchone()[0]
    if exists:
        cursor.close()
        conn.close()
        return
    published = convert_publishedAt(article.get("publishedAt"))

    # Preprocess title and description before storing
    cleaned_title = preprocess_text(article.get("title", ""))
    cleaned_description = preprocess_text(article.get("description", ""))

    cursor.execute(
        "INSERT INTO news (title, source, publishedAt, url, description, imageurl) VALUES (%s, %s, %s, %s, %s, %s)",
        (
            cleaned_title,
            article.get("source", {}).get("name"),
            published,
            article.get("url"),
            cleaned_description,
            article.get("urlToImage"),
        )
    )
    conn.commit()
    cursor.close()
    conn.close()

def fetch_live_news(topic, num_articles=10):
    NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
    url = f"https://newsapi.org/v2/everything?q={topic}&pageSize={num_articles}&apiKey={NEWSAPI_KEY}"
    response = requests.get(url)
    data = response.json()
    articles = data.get("articles", [])
    return articles[:num_articles]

def store_articles(articles):
    for article in articles:
        if article.get("title"):
            insert_news(article)


# In[ ]:




