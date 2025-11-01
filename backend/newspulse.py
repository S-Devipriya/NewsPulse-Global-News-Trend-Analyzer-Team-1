from flask import Flask, render_template, request, redirect, flash, make_response, g, current_app, jsonify
import mysql.connector as mysql
from text_preprocessing import preprocess_text
import fetch_news
import keyword_extractor
import user_profile
import topic_selection
import users
import os
from dotenv import load_dotenv
from functools import wraps
import jwt
from datetime import datetime, timedelta
from collections import Counter

# Import sentiment and NER logic
from sentiment import analyze_sentiment, save_sentiment
from ner import extract_entities, save_entities

load_dotenv()

def fetch_from_db(search_query):
    fetch_news.fetch_and_store()
    keyword_extractor.extract_and_store_keywords()
    topic_selection.analyze_topics()
    try:
        connection = mysql.connect(
            host = os.getenv("MYSQL_HOST"),
            port = int(os.getenv("MYSQL_PORT")),
            user = os.getenv("MYSQL_USER"),
            password = os.getenv("MYSQL_PASSWORD"),
            database = os.getenv("MYSQL_DB")
        )
        cursor = connection.cursor(dictionary=True)
    except mysql.Error as err:
        print(f"Error: {err}")
        articles = []
        return articles

    articles = []
    if search_query:
        cleaned_search_query = preprocess_text(search_query)
        if cleaned_search_query:
            sql_query = """
                SELECT id, title, source, publishedAt, url, description, imageurl, keywords, topic FROM news
                WHERE
                    LOWER(title) LIKE %s OR
                    LOWER(description) LIKE %s OR
                    LOWER(keywords) LIKE %s OR
                    LOWER(topic) LIKE %s
                ORDER BY publishedAt DESC
            """
            query_param = f"%{cleaned_search_query.lower()}%"
            cursor.execute(sql_query, (query_param, query_param, query_param, query_param))
            articles = cursor.fetchall()
        else:
            articles = []
    else:
        sql_query = "SELECT id, title, source, publishedAt, url, description, imageurl, keywords, topic FROM news ORDER BY publishedAt DESC"
        cursor.execute(sql_query)
        articles = cursor.fetchall()

    connection.close()
    return articles

def generate_summary(articles, user_query=None, max_keywords=3, max_entities=3):
    keyword_list = []
    topic_list = []
    headline = ""
    entity_list = []
    sentiment_list = []

    for article in articles:
        if not headline and article.get('title'):
            headline = article['title']
        if article.get('keywords'):
            keyword_list.extend([k.strip().lower() for k in article['keywords'].split(',') if k.strip()])
        if article.get('topic'):
            topic_list.append(article['topic'].strip())
        if article.get('entities'):
            for k in ("people", "organizations", "locations"):
                entity_list.extend(article['entities'].get(k, []))
        if article.get('sentiment') and isinstance(article['sentiment'], dict):
            sentiment_list.append(article['sentiment'].get('overall', '').lower())

    keyword_counts = Counter(keyword_list)
    entity_counts = Counter(entity_list)
    topic_counts = Counter(topic_list)
    sentiment_counts = Counter(sentiment_list)

    top_keywords = [kw for kw, _ in keyword_counts.most_common(max_keywords)]
    top_entities = [e for e, _ in entity_counts.most_common(max_entities)]
    most_common_sentiment = ""
    if sentiment_counts:
        most_common_sentiment = sentiment_counts.most_common(1)[0][0].capitalize()

    if not articles:
        return "No news found for your search."

    pieces = []
    if user_query and user_query.lower() != "latest":
        pieces.append(f"Today's news about {user_query} focuses on")
    else:
        pieces.append("Today's top news focuses on")

    if headline:
        pieces.append(f"{headline.lower()}.")

    if top_keywords:
        pieces.append(f"Prominent themes include {', '.join(top_keywords)}.")

    if top_entities:
        pieces.append(f"Notable figures or organizations are {', '.join(top_entities)}.")

    if most_common_sentiment:
        pieces.append(f"The overall tone is {most_common_sentiment.lower()}.")

    return " ".join(pieces)

app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# Decorator to protect routes
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('token')
        if not token:
            flash('Authentication token is missing!', 'danger')
            return redirect('/login')
        try:
            secret_key = os.getenv("FLASK_SECRET_KEY")
            data = jwt.decode(token, secret_key, algorithms=['HS256'])
            g.user_id = data['sub']
            g.username = data['username']
        except jwt.ExpiredSignatureError:
            flash('Your session has expired. Please log in again.', 'danger')
            return redirect('/login')
        except Exception as e:
            flash('Authentication token is invalid!', 'danger')
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        if users.register_user(email, password):
            flash("Registration successful! Please Login.", "success")
            return redirect("/login")
        else:
            flash("Email already exists. Please choose another.", "danger")
            return redirect("/register")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        secret_key = os.getenv("FLASK_SECRET_KEY")
        token = users.login_user(email, password, secret_key)
        if token:
            response = make_response(redirect('/dashboard'))
            response.set_cookie('token', token, httponly=True, samesite='Lax')
            return response
        else:
            flash("Invalid email or password!", "danger")
            return redirect("/login")
    return render_template("login.html")

@app.route("/profile", methods=["GET", "POST"])
@token_required
def profile():
    user_id = g.user_id
    if request.method == "POST":
        username = request.form.get("username")
        language = request.form.get("language")
        interests = request.form.get("interests")
        user_profile.update_user_profile(user_id, username, language, interests)
        try:
            secret_key = current_app.config['SECRET_KEY']
            new_payload = {
                'exp': datetime.utcnow() + timedelta(days=1),
                'iat': datetime.utcnow(),
                'sub': str(g.user_id),
                'username': username
            }
            new_token = jwt.encode(new_payload, secret_key, algorithm='HS256')
            response = make_response(redirect("/profile"))
            response.set_cookie('token', new_token, httponly=True, samesite='Lax')
            flash("Profile updated successfully!", "success")
            return response
        except Exception as e:
            print(f"Error re-issuing token: {e}")
            flash("Profile updated, but session could not be refreshed. Please log in again.", "warning")
            return redirect("/login")
    user = user_profile.get_user_profile(user_id)
    return render_template("profile.html", user=user)

@app.route("/dashboard", methods=["GET", "POST"])
@token_required
def dashboard():
    query = request.values.get("query", "latest").strip()
    news_items = fetch_from_db(query)
    summary = generate_summary(news_items, user_query=query)
    enriched_news = []
    for article in news_items:
        text = f"{article.get('title', '')}. {article.get('description', '')}"
        article_id = article['id']
        sentiment = analyze_sentiment(text)
        save_sentiment(article_id, sentiment)
        entities_dict = extract_entities(text)
        save_entities(article_id, entities_dict['entities'])
        article['sentiment'] = sentiment
        article['entities'] = entities_dict
        enriched_news.append(article)
    return render_template(
        "dashboard.html",
        news=enriched_news,
        user=g.username,
        query=query,
        summary=summary
    )

@app.route("/analyze-sentiment", methods=["POST"])
@token_required
def sentiment_api():
    data = request.get_json()
    text = data.get('text', '')
    article_id = data.get('article_id')
    sentiment = analyze_sentiment(text)
    if article_id:
        save_sentiment(article_id, sentiment)
    return jsonify(sentiment)

@app.route("/extract-entities", methods=["POST"])
@token_required
def ner_api():
    data = request.get_json()
    text = data.get('text', '')
    article_id = data.get('article_id')
    entities_dict = extract_entities(text)
    if article_id:
        save_entities(article_id, entities_dict['entities'])
    return jsonify(entities_dict)

@app.route('/api/suggest')
def suggest():
    query = request.args.get('q', '').strip().lower()
    if not query or len(query) < 2:
        return jsonify([])
    try:
        connection = mysql.connect(
            host = os.getenv("MYSQL_HOST"),
            port = int(os.getenv("MYSQL_PORT")),
            user = os.getenv("MYSQL_USER"),
            password = os.getenv("MYSQL_PASSWORD"),
            database = os.getenv("MYSQL_DB")
        )
        cursor = connection.cursor()
        cursor.execute("""
            SELECT DISTINCT topic FROM news
            WHERE LOWER(topic) LIKE %s AND topic IS NOT NULL
            LIMIT 5
        """, (f"%{query}%",))
        topics = [row[0] for row in cursor.fetchall() if row[0]]
        cursor.execute("""
            SELECT DISTINCT keywords FROM news
            WHERE LOWER(keywords) LIKE %s AND keywords IS NOT NULL
            LIMIT 10
        """, (f"%{query}%",))
        keywords = []
        for row in cursor.fetchall():
            for word in row[0].split(","):
                word = word.strip()
                if word and query in word.lower() and word not in keywords:
                    keywords.append(word)
        suggestions = list(dict.fromkeys(topics + keywords))[:5]
        connection.close()
        return jsonify(suggestions)
    except mysql.Error as err:
        print(f"Database error in suggestions: {err}")
        return jsonify([])

@app.route("/logout")
def logout():
    response = make_response(redirect('/login'))
    response.set_cookie('token', '', expires=0)
    flash("You have been logged out.", "success")
    return response

@app.route("/")
def home():
    fetch_news.create_database()
    return render_template("home.html")

if __name__ == "__main__":
    app.run(debug=True)
