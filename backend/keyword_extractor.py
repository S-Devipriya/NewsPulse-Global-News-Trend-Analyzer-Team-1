import os
from dotenv import load_dotenv
import pandas as pd
from keybert import KeyBERT
from fetch_news import connect_db

load_dotenv()

def extract_and_store_keywords():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, title, description FROM news WHERE keywords IS NULL OR keywords = ''")
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
        cursor.execute("UPDATE news SET keywords = %s WHERE id = %s", (keywords_str, news_id))
        conn.commit()

    cursor.close()
    conn.close()
