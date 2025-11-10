from dotenv import load_dotenv
import pandas as pd
import nltk
from nltk.corpus import stopwords
import re
import string
from sklearn.feature_extraction.text import CountVectorizer
from sentence_transformers import SentenceTransformer
from bertopic import BERTopic
from fetch_news import connect_db
import os

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models")
BERTOPIC_MODEL_PATH = os.path.join(MODEL_DIR, "BERTopic_model")

# Ensure the 'models' directory exists
os.makedirs(MODEL_DIR, exist_ok=True)

# Manually update this map after you run training and see the
# "Topics Detected" output in your terminal.
# Topic -1 is the outlier topic in BERTopic.
manual_topic_labels = {
        -1: "Miscellaneous",
        0: "Politics",
        1: "Health",
        2: "Science",
        3: "Sports",
        4: "Technology",
        5: "Entertainment",
        6: "Business"
}

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

def create_and_sync_topic_tables():
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            id INT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            keywords TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE(name)
        );
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS article_topics_mapping (
            id INT AUTO_INCREMENT PRIMARY KEY,
            article_id INT NOT NULL,
            topic_id INT NOT NULL,
            relevance_score FLOAT,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (article_id) REFERENCES news(id),
            FOREIGN KEY (topic_id) REFERENCES topics(id),
            UNIQUE KEY (article_id, topic_id)
        );
    """)
    
    print("Syncing manual labels to 'topics' table...")
    for topic_id, name in manual_topic_labels.items():
        try:
            cursor.execute("""
                INSERT INTO topics (id, name, created_at, updated_at)
                VALUES (%s, %s, NOW(), NOW())
                ON DUPLICATE KEY UPDATE name = %s, updated_at = NOW();""", (topic_id, name, name))
        except Exception as e:
            print(f"Error syncing topic {topic_id} ('{name}'): {e}")
            
    conn.commit()
    conn.close()
    print("Topic tables are ready and synced.")

def train_models():
    """
    Fetches ALL articles, trains a new BERTopic model,
    and SAVES it to disk.
    Run this function manually from your terminal.
    """
    print("Starting BERTopic Model Training....")
    
    create_and_sync_topic_tables()
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
        min_topic_size=13
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
    topic_info = topic_model.get_topic_info()
    print(topic_info)

    print("Updating 'topics' table with new keywords...")
    conn = connect_db()
    cursor = conn.cursor()
    for row in topic_info.to_dict('records'):
        topic_id = int(row['Topic'])
        keywords_str = ", ".join(row['Representation'])
        cursor.execute("""
            UPDATE topics SET keywords = %s, updated_at = NOW()
            WHERE id = %s""", (keywords_str, topic_id))
    conn.commit()
    conn.close()
    print("Topic keywords updated.")
    
    print("\nACTION REQUIRED")
    print("Review the topic list above.")
    print("If topic names (0, 1, 2, etc.) don't match your `manual_topic_labels` dict,")
    print("please update the dictionary in this script.")

def assign_topic():
    # LOADS the saved models and assigns topics to new article
    
    create_and_sync_topic_tables()

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

    print("Finding new articles to assign topics to...")
    # Find articles that are NOT in the article_topics mapping table yet
    cursor.execute("""
        SELECT n.id, n.title, n.description, n.content 
        FROM news n
        LEFT JOIN article_topics_mapping at ON n.id = at.article_id
        WHERE at.article_id IS NULL;
    """)
    rows = cursor.fetchall()
    
    if not rows:
        print("No new articles to assign topics to.")
        cursor.close()
        conn.close()
        return
    
    print(f"Assigning topics to {len(rows)} new articles...")

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
        # Get both the predicted topic ID and the probability matrix
        topic_ids, probabilities = topic_model.transform(texts_to_assign)
        
        # Get the relevance score (the probability of the *assigned* topic)
        relevance_scores = list(probabilities)
        
    except Exception as e:
        print(f"Error transforming new articles: {e}")
        cursor.close()
        conn.close()
        return

    # Loop through results and update DB
    updates = 0
    for i in range(len(doc_ids)):
        doc_id = doc_ids[i]
        topic_id = int(topic_ids[i])
        score = float(relevance_scores[i])
        
        try:
            cursor.execute("""
                INSERT INTO article_topics_mapping (article_id, topic_id, relevance_score, assigned_at)
                VALUES (%s, %s, %s, NOW())""", (doc_id, topic_id, score))
            updates += 1
        except Exception as e:
            if "Duplicate entry" not in str(e):
                print(f"Error updating article {doc_id}: {e}")
    
    conn.commit()
    print(f"Topic assignment complete. {updates} articles mapped.")
    cursor.close()
    conn.close()

if __name__ == "__main__":
    print("Running in training mode:")
    #train_models()
    assign_topic()