from dotenv import load_dotenv
import pandas as pd
from gensim import corpora, models
from gensim.models import TfidfModel
import nltk
from nltk.corpus import stopwords
import re
import string
import spacy
from fetch_news import connect_db
import os

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models")
LDA_MODEL_PATH = os.path.join(MODEL_DIR, "lda_model.gensim")
DICTIONARY_PATH = os.path.join(MODEL_DIR, "dictionary.gensim")
TFIDF_MODEL_PATH = os.path.join(MODEL_DIR, "tfidf_model.gensim")

# Ensure the 'models' directory exists
os.makedirs(MODEL_DIR, exist_ok=True)

def get_nlp_resources():
    try:
        stopwords.words('english')
    except LookupError:
        nltk.download('stopwords')

    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        print("Downloading spaCy model en_core_web_sm...")
        spacy.cli.download("en_core_web_sm")
        nlp = spacy.load("en_core_web_sm")

    stop_words = set(stopwords.words('english'))
    custom_stop_words = {
        'say', 'us', 'news', '’s', 'report', 'government', 'new', 
        'trump', 'people', 'white', 'house', 'country', 'donald', 'united',
        'time', 'week', 'day', 'today', 'monday', 'tuesday', 'wednesday', 
        'thursday', 'friday', 'saturday', 'sunday', 'year', 'night', 'oct', 'season',
        'bbc', 'cbs', 'bloombergcom', 'politico', 'nbc', 'company', 'npr',
        'administration', 'minister', 'state', 'party', 'case' , 'president', 'official', 'states', 
        'washington', 'york', 'point', 'space', 'south', 'street', 'way', 'city', 'los', 'angeles', 'china'
    }
    stop_words.update(custom_stop_words)
    allowed_pos = {'NOUN', 'PROPN'}
    
    return nlp, stop_words, allowed_pos

def preprocess_text(text, nlp, stop_words, allowed_pos):
    text = text.strip().lower()
    text = re.sub(r"http\S+|www\S+|https\S+", '', text, flags=re.MULTILINE)
    text = text.translate(str.maketrans('', '', string.punctuation))
    text = re.sub(r'\d+', '', text)
    
    doc = nlp(text)
    current_doc_tokens = []
    for token in doc:
        lemma = token.lemma_.strip()
        if (lemma not in stop_words and   
            not token.is_punct and         
            not token.is_space and         
            token.pos_ in allowed_pos and  
            lemma != '-PRON-' and 
            len(lemma) > 2):
            
            current_doc_tokens.append(lemma)
    return current_doc_tokens

def train_lda_model():
    """
    Fetches ALL articles, trains a new LDA model, and SAVES it to disk.
    Run this function manually from your terminal.
    """
    print("--- Starting LDA Model Training ---")
    nlp, stop_words, allowed_pos = get_nlp_resources()
    
    conn = connect_db()
    cursor = conn.cursor()

    print("Fetching all articles for training...")
    cursor.execute("SELECT id, title, description, content FROM news")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        print("No articles in database to train on.")
        return

    print(f"Preprocessing {len(rows)} articles...")
    docs_tokens = []
    for row in rows:
        title = row[1] or ""
        description = row[2] or ""
        content = row[3] or ""
        text = (title + " " + description + " " + content)
        docs_tokens.append(preprocess_text(text, nlp, stop_words, allowed_pos))


    print("Building and saving dictionary...")
    dictionary = corpora.Dictionary(docs_tokens)
    dictionary.filter_extremes(no_below=5, no_above=0.6)
    dictionary.save(DICTIONARY_PATH)

    corpus = [dictionary.doc2bow(doc) for doc in docs_tokens]
    
    print("Building and saving TF-IDF model...")
    tfidf = TfidfModel(corpus)
    tfidf.save(TFIDF_MODEL_PATH)
    
    corpus_tfidf = tfidf[corpus]

    if not corpus_tfidf:
        print("Corpus is empty, cannot train.")
        return

    print("Training and saving LDA model...")
    lda_model = models.LdaModel(corpus_tfidf, num_topics=5, id2word=dictionary, passes=25, random_state=42)
    lda_model.save(LDA_MODEL_PATH)

    print("\nTraining Complete!")
    print(f"Models saved to {MODEL_DIR}")
    
    print("\n🔍 Topics Detected:")
    topics = lda_model.print_topics(num_words=5)
    for idx, topic in topics:
        print(f"Topic {idx}: {topic}")
    
    print("\n--- ACTION REQUIRED ---")
    print("Manually update the 'manual_topic_labels' dictionary in the")
    print("'assign_topic' function with these topics.")
    print("------------------------")


def assign_topic():
    # LOADS the saved models and assigns topics to new article
    # Manually update this map after you run training and see the
    # "Topics Detected" output in your terminal.
    manual_topic_labels = {
        0: "World Politics & Governance",
        1: "Health & Lifestyle",
        2: "Science &Technology",
        3: "Sports & Entertainment",
        4: "Business & Economy"
    }
    
    try:
        nlp, stop_words, allowed_pos = get_nlp_resources()
        dictionary = corpora.Dictionary.load(DICTIONARY_PATH)
        tfidf = TfidfModel.load(TFIDF_MODEL_PATH)
        lda_model = models.LdaModel.load(LDA_MODEL_PATH)
    except FileNotFoundError:
        print("Model files not found. Please run this file from your terminal to train them:")
        print("python backend/topic_selection.py")
        return
    except Exception as e:
        print(f"Error loading models: {e}")
        return

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, title, description, content FROM news WHERE topic IS NULL OR topic = ''")
    rows = cursor.fetchall()
    
    if not rows:
        print("No new articles to assign topics to.")
        cursor.close()
        conn.close()
        return
    
    print(f"Assigning topics to {len(rows)} new articles...")

    for row in rows:
        doc_id = row[0]
        title = row[1] or ""
        description = row[2] or ""
        content = row[3] or ""
        text = (title + " " + description + " " + content)
        
        proc_tokens = preprocess_text(text, nlp, stop_words, allowed_pos)
        bow_corpus = dictionary.doc2bow(proc_tokens)
        doc_tfidf = tfidf[bow_corpus]
        topic_distribution = lda_model.get_document_topics(doc_tfidf)
        
        assigned_topic = "General" 
        if topic_distribution:
            best_topic_id = max(topic_distribution, key=lambda item: item[1])[0]
            assigned_topic = manual_topic_labels.get(best_topic_id, "General")
        
        try:
            cursor.execute("UPDATE news SET topic = %s WHERE id = %s", (assigned_topic, doc_id))
            conn.commit()
        except Exception as e:
            print(f"Error updating article {doc_id}: {e}")

    print(f"Topic assignment complete for {len(rows)} articles.")
    cursor.close()
    conn.close()

if __name__ == "__main__":
    print("Running in training mode:")
    train_lda_model()