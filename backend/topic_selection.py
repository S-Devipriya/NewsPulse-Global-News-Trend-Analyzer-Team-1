from dotenv import load_dotenv
import pandas as pd
from gensim import corpora, models
import nltk
from nltk.corpus import stopwords
import re
import string
import spacy
from fetch_news import connect_db

load_dotenv()
try:
    stopwords.words('english')
except LookupError:
    nltk.download('stopwords')

stop_words = set(stopwords.words('english'))
nlp = spacy.load("en_core_web_sm")

def get_topic_keywords(topic_str, n=3):
    # Extracts n top keywords from LDA topic descriptor string
    # Example input: '0.025*"ai" + 0.020*"robot" + ...'
    words = [w.split('*"')[1].replace('"', '') for w in topic_str.split(' + ')[:n]]
    return ", ".join(words)

def analyze_topics():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, title, description, content FROM news WHERE topic IS NULL OR topic = ''")
    rows = cursor.fetchall()
    if not rows:
        print("No new articles to analyze.")
        cursor.close()
        conn.close()
        return

    raw_news = pd.DataFrame(rows, columns=['id', 'title', 'description', 'content'])

    docs_tokens = []
    doc_ids = []
    for i, row in raw_news.iterrows():
        doc_ids.append(row['id'])
        title = row['title'] or ""
        description = row['description'] or ""
        content = row['content'] or ""
        text = (title + " " + description + " " + content).strip().lower()
        text = re.sub(r"http\S+|www\S+|https\S+", '', text, flags=re.MULTILINE)
        text = text.translate(str.maketrans('', '', string.punctuation))
        text = re.sub(r'\d+', '', text)

        doc = nlp(text)
        current_doc_tokens = []
        for token in doc:
            if not token.text in stop_words and not token.is_punct and not token.is_space:
                lemma = token.lemma_.strip()
                if lemma and lemma != '-PRON-':
                    current_doc_tokens.append(lemma)
        docs_tokens.append(current_doc_tokens)

    if not docs_tokens:
        print("No tokens found after preprocessing.")
        return

    dictionary = corpora.Dictionary(docs_tokens)
    dictionary.filter_extremes(no_below=2, no_above=0.8)
    corpus = [dictionary.doc2bow(doc) for doc in docs_tokens]

    # Train LDA model
    if len(dictionary) > 0 and len(corpus) > 0:
        lda_model = models.LdaModel(corpus, num_topics=5, id2word=dictionary, passes=15, random_state=42)

        print("\n🔍 Topics Detected:")
        topics = lda_model.print_topics(num_words=5)
        for idx, topic in topics:
            print(f"Topic {idx}: {topic}")

        print("\nAssigning topics to articles...")
        for i, doc_corpus in enumerate(corpus):
            doc_id = doc_ids[i]
            topic_distribution = lda_model.get_document_topics(doc_corpus)
            if topic_distribution:
                best_topic_id = max(topic_distribution, key=lambda item: item[1])[0]
                topic_keywords = get_topic_keywords(topics[best_topic_id][1], n=3)
                assigned_topic = topic_keywords if topic_keywords else "General"
                try:
                    cursor.execute("UPDATE news SET topic = %s WHERE id = %s", (assigned_topic, doc_id))
                    conn.commit()
                    print(f"  -> Updated article {doc_id} with topic: '{assigned_topic}'")
                except Exception as e:
                    print(f"Error updating article {doc_id}: {e}")
            else:
                print(f"  -> Could not determine topic for article {doc_id}")

    else:
        print("Not enough data to build a topic model.")

    cursor.close()
    conn.close()
