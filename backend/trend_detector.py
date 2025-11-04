import pandas as pd
import mysql.connector
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import Counter
import nltk
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
import re
import json

load_dotenv()

# Download stopwords if not already downloaded
try:
    nltk.download('stopwords', quiet=True)
    stop_words = set(stopwords.words('english'))
except:
    stop_words = set()

class TrendDetector:
    def __init__(self):
        self.connection = self.connect_db()
    
    def connect_db(self):
        return mysql.connector.connect(
            host=os.getenv("MYSQL_HOST"),
            port=int(os.getenv("MYSQL_PORT", 3306)),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DB")
        )
    
    def preprocess_text(self, text):
        if not text:
            return ""
        text = re.sub(r'\W+', ' ', text.lower())
        tokens = [word for word in text.split() if word not in stop_words and len(word) > 2]
        return ' '.join(tokens)
    
    def get_recent_news(self, days=7):
        """Get news from the last N days"""
        cursor = self.connection.cursor(dictionary=True)
        
        query = """
            SELECT id, title, description, publishedAt, keywords, topic, source, url, imageurl
            FROM news 
            WHERE publishedAt >= DATE_SUB(NOW(), INTERVAL %s DAY)
            ORDER BY publishedAt DESC
        """
        cursor.execute(query, (days,))
        articles = cursor.fetchall()
        cursor.close()
        
        return pd.DataFrame(articles)
    
    def detect_topic_trends(self, df, num_topics=5):
        """Detect trending topics using LDA"""
        if len(df) < num_topics:
            num_topics = max(1, len(df) // 2)
        
        # Combine title and description for better topic modeling
        df['content'] = (df['title'].fillna('') + ' ' + df['description'].fillna(''))
        df['cleaned_content'] = df['content'].apply(self.preprocess_text)
        
        if df['cleaned_content'].str.len().sum() == 0:
            return {}
        
        # Vectorize text
        vectorizer = CountVectorizer(max_df=0.95, min_df=1, max_features=1000, stop_words='english')
        try:
            X = vectorizer.fit_transform(df['cleaned_content'])
            
            # Apply LDA
            lda = LatentDirichletAllocation(n_components=num_topics, random_state=42)
            lda.fit(X)
            
            # Extract top words for each topic
            feature_names = vectorizer.get_feature_names_out()
            topics = {}
            
            for topic_idx, topic in enumerate(lda.components_):
                top_words = [feature_names[i] for i in topic.argsort()[-10:][::-1]]
                topics[f"Topic {topic_idx + 1}"] = top_words
            
            return topics
        except Exception as e:
            print(f"Topic modeling error: {e}")
            return {}
    
    def detect_keyword_trends(self, df, top_n=10):
        """Detect trending keywords"""
        all_keywords = []
        
        # Extract keywords from keywords column
        for keywords in df['keywords'].dropna():
            if keywords:
                all_keywords.extend([kw.strip().lower() for kw in keywords.split(',')])
        
        # Also extract from titles
        for title in df['title'].dropna():
            processed = self.preprocess_text(title)
            all_keywords.extend(processed.split())
        
        # Count and get top trends
        keyword_counts = Counter(all_keywords)
        
        # Filter out very common words
        common_news_words = {'news', 'update', 'report', 'said', 'year', 'time', 'day'}
        trending_keywords = {
            word: count for word, count in keyword_counts.most_common(top_n * 2)
            if word not in common_news_words and len(word) > 2
        }
        
        return dict(list(trending_keywords.items())[:top_n])
    
    def detect_trending_articles(self, df, top_n=10):
        """Identify most relevant trending articles"""
        # Simple scoring based on recency and keyword frequency
        df = df.copy()
        df['publishedAt'] = pd.to_datetime(df['publishedAt'])
        df['recency_score'] = (df['publishedAt'].max() - df['publishedAt']).dt.total_seconds() / 3600
        
        # Articles from last 24 hours get higher score
        df['trend_score'] = 100 / (df['recency_score'] + 1)
        
        # Sort by trend score
        trending_articles = df.nlargest(top_n, 'trend_score')
        
        return trending_articles.to_dict('records')
    
    def get_daily_trends(self):
        """Main function to get all trends"""
        df = self.get_recent_news(days=3)  # Last 3 days for trends
        
        if df.empty:
            return {
                'topics': {},
                'keywords': {},
                'trending_articles': [],
                'trend_categories': {}
            }
        
        topics = self.detect_topic_trends(df)
        keywords = self.detect_keyword_trends(df)
        trending_articles = self.detect_trending_articles(df)
        
        # Categorize trends
        trend_categories = self.categorize_trends(keywords, topics)
        
        return {
            'topics': topics,
            'keywords': keywords,
            'trending_articles': trending_articles,
            'trend_categories': trend_categories
        }
    
    def categorize_trends(self, keywords, topics):
        """Categorize trends into broader categories"""
        categories = {
            'Technology': ['ai', 'tech', 'software', 'digital', 'innovation', 'data'],
            'Politics': ['government', 'election', 'policy', 'minister', 'political'],
            'Business': ['market', 'economy', 'business', 'company', 'stock', 'financial'],
            'Health': ['health', 'medical', 'hospital', 'disease', 'vaccine', 'doctor'],
            'Sports': ['sports', 'game', 'team', 'player', 'championship', 'match'],
            'Entertainment': ['movie', 'celebrity', 'film', 'music', 'show', 'entertainment']
        }
        
        trend_categories = {category: [] for category in categories.keys()}
        
        # Categorize keywords
        for keyword, count in keywords.items():
            for category, terms in categories.items():
                if any(term in keyword for term in terms):
                    trend_categories[category].append({'keyword': keyword, 'count': count})
                    break
        
        # Clean empty categories
        trend_categories = {k: v for k, v in trend_categories.items() if v}
        
        return trend_categories
    
    def __del__(self):
        if hasattr(self, 'connection') and self.connection.is_connected():
            self.connection.close()