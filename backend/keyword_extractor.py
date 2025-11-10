import os
from dotenv import load_dotenv
import pandas as pd
import mysql.connector
from keybert import KeyBERT
from fetch_news import connect_db

load_dotenv()

def create_keywords_table():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS keywords(
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    article_id INT UNIQUE,
                    keywords TEXT,
                    FOREIGN KEY(article_id) REFERENCES news(id)
                );''')
    conn.close()
    return

def extract_and_store_keywords():
    create_keywords_table()
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute('''SELECT n.id, n.title, n.description
                      FROM news n
                      LEFT JOIN keywords k ON n.id = k.article_id
                      WHERE k.article_id IS NULL;''')
    rows = cursor.fetchall()
    raw_news = pd.DataFrame(rows, columns=['id', 'title', 'description'])

    # Keyword extraction per-document using KeyBERT
    kw_model = KeyBERT()
    keywords_dict = {}
    for i, row in raw_news.iterrows():
        title = row['title'] or ""
        description = row['description'] or ""
        doc = (title + " " + description).strip()
        if not doc:
            continue
        keywords = kw_model.extract_keywords(doc, keyphrase_ngram_range=(1, 2), stop_words='english', top_n=3)
        keywords_dict[row['id']] = [kw for kw, _ in keywords]

    # Store keywords back to the database
    for news_id, keywords in keywords_dict.items():
        keywords_str = ', '.join(keywords)
        cursor.execute("INSERT INTO keywords (keywords, article_id) VALUES(%s, %s)", (keywords_str, news_id))
        conn.commit()

    cursor.close()
    conn.close()

if __name__ == "__main__":
    extract_and_store_keywords()