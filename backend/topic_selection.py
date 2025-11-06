from dotenv import load_dotenv
import pandas as pd
import nltk
from nltk.corpus import stopwords
import re
import string
from sklearn.feature_extraction.text import CountVectorizer
from sentence_transformers import SentenceTransformer
from bertopic import BERTopic
import joblib
from fetch_news import connect_db
import os

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models")
BERTOPIC_MODEL_PATH = os.path.join(MODEL_DIR, "BERTopic_model")

# Ensure the 'models' directory exists
os.makedirs(MODEL_DIR, exist_ok=True)

def get_stopwords():
    """
    Gets the list of English stopwords and adds custom ones.
    """
    try:
        stopwords.words('english')
    except LookupError:
        nltk.download('stopwords')
    
    stop_words = set(stopwords.words('english'))
    custom_stop_words = {
        'say', 'us', 'news', '’s', 'report', 'government', 'new', 
        'trump', 'people', 'white', 'house', 'country', 'donald', 'united',
        'time', 'week', 'day', 'today', 'monday', 'tuesday', 'wednesday', 
        'thursday', 'friday', 'saturday', 'sunday', 'year', 'night', 'oct', 'season',
        'bbc', 'cbs', 'bloombergcom', 'politico', 'nbc', 'company', 'npr',
        'administration', 'minister', 'state', 'party', 'case' , 'president', 'official', 'states', 
        'washington', 'york', 'point', 'space', 'south', 'street', 'way', 'city', 'los', 'angeles', 'china',
        'gmt', 'pm', 'am', 'et'
    }
    stop_words.update(custom_stop_words)
    return list(stop_words)

def preprocess_text_for_bert(text):
    if not text:
        return ""
    text = text.strip().lower()
    text = re.sub(r"http\S+|www\S+|https\S+", '', text, flags=re.MULTILINE) 
    text = text.translate(str.maketrans('', '', string.punctuation)) 
    text = re.sub(r'\d+', '', text) 
    text = " ".join(text.split()) 
    return text

def train_models():
    """
    Fetches ALL articles, trains a new BERTopic model,
    and SAVES it to disk.
    Run this function manually from your terminal.
    """
    print("Starting BERTopic Model Training....")
    
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

    print(f"Preprocessing {len(rows)} articles (minimal cleaning)...")
    docs_text = [] 
    for row in rows:
        title = row[1] or ""
        description = row[2] or ""
        content = row[3] or ""
        text = (title + " " + description + " " + content)
        docs_text.append(preprocess_text_for_bert(text))

    print("Loading embedding model...")
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

    stop_words = get_stopwords()
    vectorizer_model = CountVectorizer(stop_words=stop_words)

    topic_model = BERTopic(
        embedding_model=embedding_model,
        vectorizer_model=vectorizer_model,
        language="english",
        verbose=True,
        min_topic_size=10
    )

    print("Training BERTopic model (this may take a while)...")
    try:
        topics, probabilities = topic_model.fit_transform(docs_text)
    except Exception as e:
        print(f"Error during BERTopic training: {e}")
        return

    print("Saving model...")
    topic_model.save(BERTOPIC_MODEL_PATH)

    print("\nTraining Complete!")
    
    print("\n🔍 Topics Detected:")
    print(topic_model.get_topic_info())
    
    print("\n--- ACTION REQUIRED ---")
    print("Manually update the 'manual_topic_labels' dictionary in the")
    print("'assign_topic' function with these topics.")
    print("------------------------")


def assign_topic():
    # LOADS the saved models and assigns topics to new article
    # Manually update this map after you run training and see the
    # "Topics Detected" output in your terminal.
    # Topic -1 is the outlier topic in BERTopic.
    manual_topic_labels = {
        -1: "General", 
        0: "Sports",
        1: "Health",
        2: "Technology",
        3: "Science",
        4: "Business",
        # Add more mappings as found by the model
    }
    
    try:
        # Load the saved BERTopic model
        topic_model = BERTopic.load(BERTOPIC_MODEL_PATH)
    except FileNotFoundError:
        print("Model files not found. Please run this file from your terminal to train them:")
        print("python topic_selection.py")
        return
    except Exception as e:
        print(f"Error loading model: {e}")
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

    # --- Batch Processing ---
    texts_to_assign = []
    doc_ids = []
    for row in rows:
        doc_id = row[0]
        title = row[1] or ""
        description = row[2] or ""
        content = row[3] or ""
        text = (title + " " + description + " " + content)
        
        texts_to_assign.append(preprocess_text_for_bert(text))
        doc_ids.append(doc_id)

    if not texts_to_assign:
        print("No processable text found in new articles.")
        cursor.close()
        conn.close()
        return

    try:
        # Use .transform() to assign topics to new docs
        # This returns a list of topic IDs, one for each doc
        topic_ids, _ = topic_model.transform(texts_to_assign)
    
    except Exception as e:
        print(f"Error transforming new articles: {e}")
        cursor.close()
        conn.close()
        return

    # Loop through results and update DB
    updates = 0
    for i in range(len(doc_ids)):
        doc_id = doc_ids[i]
        best_topic_id = topic_ids[i] # Get the topic ID for this doc
        assigned_topic = manual_topic_labels.get(int(best_topic_id), "General")
        
        try:
            cursor.execute("UPDATE news SET topic = %s WHERE id = %s", (assigned_topic, doc_id))
            updates += 1
        except Exception as e:
            print(f"Error updating article {doc_id}: {e}")
    
    conn.commit()
    print(f"Topic assignment complete. {updates} articles updated.")
    cursor.close()
    conn.close()

if __name__ == "__main__":
    print("Running in training mode:")
    #train_models()
    assign_topic()