import os
from dotenv import load_dotenv
import pandas as pd
import nltk
from nltk.corpus import stopwords
from gensim import corpora, models
from keybert import KeyBERT
from sklearn.feature_extraction.text import CountVectorizer
from fetch_news import connect_db
from text_preprocessing import preprocess_text

load_dotenv()

def extract_and_store_keywords():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, title, description FROM news WHERE keywords IS NULL OR keywords = ''")
    rows = cursor.fetchall()
    raw_news = pd.DataFrame(rows, columns=['id', 'title', 'description'])

    # Build a list of tokenized documents
    docs_tokens = []
    for i, row in raw_news.iterrows():
        title = row['title'] or ""
        description = row['description'] or ""
        text = (title + " " + description).strip()
        pre = preprocess_text(text) or ""
        tokens = pre.split()
        docs_tokens.append(tokens)

    # Create dictionary and corpus from all documents
    dictionary = corpora.Dictionary(docs_tokens)
    corpus = [dictionary.doc2bow(doc_tokens) for doc_tokens in docs_tokens]

    # Train LDA on the whole corpus (or per-doc if you prefer)
    if len(dictionary) > 0 and len(corpus) > 0:
        lda_model = models.LdaModel(corpus, num_topics=min(3, max(1, len(dictionary))), id2word=dictionary, passes=10)

        print("\n🔍 Topics Detected:")
        for idx, topic in lda_model.print_topics(num_words=5):
            print(f"Topic {idx + 1}: {topic}")
    else:
        print("No tokens available for LDA.")

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
