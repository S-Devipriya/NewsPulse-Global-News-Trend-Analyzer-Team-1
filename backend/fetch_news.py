#!/usr/bin/env python
# coding: utf-8

# In[6]:


import os
from dotenv import load_dotenv
import requests
import mysql.connector
from datetime import datetime

load_dotenv()

def create_database():
    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD")
    )
    cursor = conn.cursor()
    cursor.execute('''CREATE DATABASE IF NOT EXISTS newsdb;''')
    conn.commit()
    cursor.execute('USE newsdb;')
    conn.commit()

    cursor.execute('''CREATE TABLE IF NOT EXISTS news (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title TEXT,
        source VARCHAR(255),
        publishedAt DATETIME,
        url LONGTEXT,
        description TEXT,
        imageurl TEXT,
        keywords VARCHAR(255),
        topic VARCHAR(255));''')
    print("Database and table ensured.")
    conn.commit()
    conn.close()
    return

def connect_db():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB")
    )

def fetch_live_news(topic=None, num_articles=10):
    NEWS_API_KEY = os.getenv("NEWS_API_KEY")
    url = f"https://newsapi.org/v2/top-headlines?language=en&pageSize={int(num_articles)}&apiKey={NEWS_API_KEY}"
    #url = f"https://newsapi.org/v2/everything?q={topic}&pageSize={num_articles}&apiKey={NEWS_API_KEY}"
    response = requests.get(url)
    data = response.json()
    articles = data.get("articles", [])
    return articles[:num_articles]

def convert_publishedAt(publishedAt_str):
    try:
        return datetime.strptime(publishedAt_str, "%Y-%m-%dT%H:%M:%SZ")
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

    cursor.execute(
        "INSERT INTO news (title, source, publishedAt, url, description, imageurl) VALUES (%s, %s, %s, %s, %s, %s)",
        (
            article.get("title"),
            article.get("source", {}).get("name"),
            published,
            article.get("url"),
            article.get("description"),
            article.get("urlToImage"),
        )
    )
    conn.commit()
    cursor.close()
    conn.close()

def store_articles(articles):
    for article in articles:
        if article.get("title"):
            insert_news(article)

def fetch_and_store():
    articles = fetch_live_news()
    store_articles(articles)


# In[ ]:




