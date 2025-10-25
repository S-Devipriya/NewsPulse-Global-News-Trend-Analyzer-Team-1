from transformers import pipeline
import mysql.connector as mysql
import os

# Load Hugging Face sentiment analysis pipeline once
sentiment_analyzer = pipeline("sentiment-analysis")

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
    label = result[0]['label']
    score = result[0]['score']

    if label == 'POSITIVE':
        return {
            'positive': int(round(score * 100)),
            'neutral': int(round((1-score) * 100)),
            'negative': 0,
            'overall': 'Positive'
        }
    else:
        return {
            'positive': 0,
            'neutral': int(round((1-score) * 100)),
            'negative': int(round(score * 100)),
            'overall': 'Negative'
        }

def save_sentiment(article_id, sentiment_dict):
    """
    Store sentiment results for a news article in the database.
    """
    connection = mysql.connect(
        host = os.getenv("MYSQL_HOST"),
        user = os.getenv("MYSQL_USER"),
        password = os.getenv("MYSQL_PASSWORD"),
        database = os.getenv("MYSQL_DB")
    )
    cursor = connection.cursor()
    query = '''CREATE TABLE IF NOT EXISTS sentiments (
               id INT AUTO_INCREMENT PRIMARY KEY,
               article_id INT,
               positive FLOAT,
               neutral FLOAT,
               negative FLOAT,
               FOREIGN KEY (article_id) REFERENCES news(id)
           );'''
    cursor.execute(query)
    connection.commit()
    query = '''INSERT INTO sentiments (article_id, positive, neutral, negative)
               VALUES (%s, %s, %s, %s)'''
    cursor.execute(query, (
        article_id,
        float(sentiment_dict['positive']),
        float(sentiment_dict['neutral']),
        float(sentiment_dict['negative'])
    ))
    connection.commit()
    connection.close()
