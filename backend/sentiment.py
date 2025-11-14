from transformers import pipeline
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

# Load Hugging Face sentiment analysis pipeline once
sentiment_analyzer = pipeline("sentiment-analysis")

def connect_db():
    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB")
    )
    cursor = conn.cursor()
    query = '''CREATE TABLE IF NOT EXISTS sentiments (
               id INT AUTO_INCREMENT PRIMARY KEY,
               article_id INT,
               positive FLOAT,
               neutral FLOAT,
               negative FLOAT,
               overall TEXT,
               FOREIGN KEY (article_id) REFERENCES news(id)
           );'''
    cursor.execute(query)
    conn.commit()
    return conn

def analyze_sentiment(text):
    """
    Analyze sentiment of the given text.
    Returns:
        dict: {
            'positive': int (percentage),
            'neutral': int (percentage),
            'negative': int (percentage),
            'overall': 'Positive' or 'Neutral' or 'Negative'
        }
    """
    
    result = sentiment_analyzer(text)
    label = result[0]['label'].upper()
    score = result[0]['score']
    
    # Default to zero for all scores
    positive, neutral, negative = 0, 0, 0

    # Assign scores based on returned label
    if label == 'POSITIVE':
        positive = score
        # If you want to distribute remainder, use below 
        neutral = (1-score)
        negative = 0
        overall = 'Positive'
    elif label == 'NEGATIVE':
        negative = score
        neutral = (1-score)
        positive = 0
        overall = 'Negative'
    elif label == 'NEUTRAL':
        neutral = score
        # For remainder distribution
        positive = 0
        negative = 0
        overall = 'Neutral'
    else:
        # In case of unknown label, fallback to neutral
        neutral = score
        positive = 0
        negative = 0
        overall = 'Neutral'

    return {
        'positive': int(round(positive * 100)),
        'neutral': int(round(neutral * 100)),
        'negative': int(round(negative * 100)),
        'overall': overall
    }

def save_sentiment(article_id, sentiment_dict):
    """
    Store sentiment results for a news article in the database.
    """
    conn = connect_db()
    cursor = conn.cursor()
    query = '''INSERT INTO sentiments (article_id, positive, neutral, negative, overall)
               VALUES (%s, %s, %s, %s, %s)'''
    cursor.execute(query, (
        article_id,
        float(sentiment_dict['positive']),
        float(sentiment_dict['neutral']),
        float(sentiment_dict['negative']),
        str(sentiment_dict['overall'])
    ))
    conn.commit()
    conn.close()

def analyze_and_save_sentiments():
    conn = connect_db()
    cursor = conn.cursor(dictionary=True) 
    cursor.execute('''SELECT n.id
                      FROM news n
                      LEFT JOIN sentiments s ON n.id = s.article_id
                      WHERE s.article_id IS NULL;''')
    article_rows = cursor.fetchall()
    if not article_rows:
        print("No new articles to analyze.")
        conn.close()
        return

    print(f"Found {len(article_rows)} new articles to analyze...")
    for row in article_rows:
        article_id_int = row['id'] 
        cursor.execute('''SELECT title, description FROM news where id = %s''', (article_id_int,))
        article = cursor.fetchone()
        if not article:
            continue
        title = article.get('title') or ""
        description = article.get('description') or ""
        text = title + " " + description
        if not text.strip():
            continue   
        sentiment = analyze_sentiment(text)
        save_sentiment(article_id_int, sentiment)    
    conn.close()
    print("Sentiment analysis complete.")

if __name__ == "__main__":
    analyze_and_save_sentiments()
