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
import re
from datetime import datetime, timedelta
from collections import Counter

from analytics_utils import (
    get_existing_topics,
    get_news_volume_timeseries_and_forecast,
    get_sentiment_percentage_forecast,
    get_topic_timeseries_and_forecast,
    get_top_topics_from_db,
    get_sentiment_distribution_numerical,
    get_sentiment_numerical_trend_by_day,
    get_sentiment_stats_from_db,
    get_sentiment_trend_by_day,
    get_top_topics_from_db
)

# Import sentiment and NER logic
from sentiment import analyze_and_save_sentiments
from ner import analyze_and_save_entities

# ADD THIS IMPORT for trend analysis
from trend_detector import TrendDetector

app_start_time = datetime.now()

load_dotenv()

def fetch_from_db(search_query):
    fetch_news.fetch_and_store()
    keyword_extractor.extract_and_store_keywords()
    topic_selection.assign_topic()
    analyze_and_save_sentiments()
    analyze_and_save_entities()
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

    sql_select_clause = """SELECT
                            n.id, n.title, n.source, n.publishedAt, n.url, n.description, n.imageurl,
                            k.keywords,
                            s.positive, s.neutral, s.negative, s.overall,
                            t.name AS topic_name
                        FROM news n
                        LEFT JOIN keywords k ON n.id = k.article_id
                        LEFT JOIN sentiments s ON n.id = s.article_id
                        LEFT JOIN article_topics_mapping atm ON n.id = atm.article_id
                        LEFT JOIN topics t ON atm.topic_id = t.id"""
    articles_raw = []
    if search_query:
        cleaned_search_query = preprocess_text(search_query)
        if cleaned_search_query:
            # Add the WHERE clause for searching
            sql_query = sql_select_clause + """ WHERE
                                                LOWER(n.title) LIKE %s OR
                                                LOWER(n.description) LIKE %s OR
                                                LOWER(k.keywords) LIKE %s OR
                                                LOWER(t.name) LIKE %s
                                            ORDER BY n.publishedAt DESC"""
            query_param = f"%{cleaned_search_query.lower()}%"
            cursor.execute(sql_query, (query_param, query_param, query_param, query_param))
            articles_raw = cursor.fetchall()
        else:
            articles_raw = []
    else:
        sql_query = sql_select_clause + " ORDER BY n.publishedAt DESC"
        cursor.execute(sql_query)
        articles_raw = cursor.fetchall()

    if not articles_raw:
        connection.close()
        return []
    
    articles_dict = {}
    article_ids = []
    for row in articles_raw:
        # Nested sentiment dict
        row['sentiment'] = {
            'positive': row.get('positive'),
            'neutral': row.get('neutral'),
            'negative': row.get('negative'),
            'overall': row.get('overall')
        } if row.get('overall') else None
        
        # Placeholder for entities
        row['entities'] = {
            'people': [],
            'organizations': [],
            'locations': []
        }
        
        # Renaming 'topic_name' to 'topic' for the template
        row['topic'] = row.get('topic_name')
        
        # Cleaning up flat keys
        for key in ['positive', 'neutral', 'negative', 'overall', 'topic_name']:
            if key in row:
                del row[key]
        
        articles_dict[row['id']] = row
        article_ids.append(row['id'])

    ids_placeholder = ','.join(['%s'] * len(article_ids))
    entity_query = f"""SELECT article_id, name, type 
                    FROM entities 
                    WHERE article_id IN ({ids_placeholder})"""
    cursor.execute(entity_query, tuple(article_ids))
    entities_raw = cursor.fetchall()

    for entity in entities_raw:
        article_id = entity['article_id']
        if article_id in articles_dict:
            ent_type = entity['type']
            ent_name = entity['name']
            if ent_type == 'PERSON':
                articles_dict[article_id]['entities']['people'].append(ent_name)
            elif ent_type == 'ORG':
                articles_dict[article_id]['entities']['organizations'].append(ent_name)
            elif ent_type in ['GPE', 'LOC']:
                articles_dict[article_id]['entities']['locations'].append(ent_name)

    connection.close()
    
    return list(articles_dict.values())

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
            g.role = data.get('role', 'user')
        except jwt.ExpiredSignatureError:
            flash('Your session has expired. Please log in again.', 'danger')
            return redirect('/login')
        except Exception as e:
            print({e})
            flash('Authentication token is invalid!', 'danger')
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    @token_required  # First, ensure user is logged in
    def decorated(*args, **kwargs):
        if g.role != 'admin':
            flash('You do not have permission to access this page.', 'danger')
            return redirect('/dashboard')
        return f(*args, **kwargs)
    return decorated


def validate(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].strip()
        password = request.form["password"]

        # --- EMAIL VALIDATION ---
        if not validate(email):
            flash("Invalid email format! Please enter a correct email.", "danger")
            return redirect("/register")

        # --- PROCEED IF EMAIL IS VALID ---
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
        email = request.form["email"].strip()
        password = request.form["password"]

        # --- EMAIL VALIDATION ---
        if not validate(email):
            flash("Please enter a valid email.", "danger")
            return redirect("/login")

        secret_key = os.getenv("FLASK_SECRET_KEY")
        user_data = users.login_user(email, password)

        if user_data:
            token_payload = {
                'exp': datetime.utcnow() + timedelta(days=1),
                'iat': datetime.utcnow(),
                'sub': str(user_data['id']),
                'username': user_data.get('username', user_data['email']),
                'role': user_data.get('role', 'user')
            }

            token = jwt.encode(token_payload, secret_key, algorithm='HS256')

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
                'username': username,
                'role': g.role
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
    return render_template("profile.html", user=user, user_role=g.role)

@app.route("/dashboard", methods=["GET", "POST"])
@token_required
def dashboard():
    query = request.values.get("query", "latest").strip()
    news_items = fetch_from_db(query)
    summary = generate_summary(news_items, user_query=query)
    
    # ADD TREND ANALYSIS TO DASHBOARD
    detector = TrendDetector()
    trends_data = detector.get_daily_trends()
    
    return render_template(
        "dashboard.html",
        news=news_items,
        user=g.username,
        user_role=g.role,
        query=query,
        summary=summary,
        trends_data=trends_data,
        now=datetime.now()
    )

# ========== TREND ANALYSIS ROUTES ==========

@app.route("/trends")
@token_required
def trends():
    """Main trends page showing trending topics and articles"""
    detector = TrendDetector()
    trends_data = detector.get_daily_trends()
    
    return render_template(
        "trends.html",
        trends_data=trends_data,
        user=g.username,
        user_role=g.role,
        now=datetime.now()
    )

@app.route("/trending-articles")
@token_required
def trending_articles():
    """API endpoint to get trending articles"""
    detector = TrendDetector()
    trends_data = detector.get_daily_trends()
    
    return jsonify({
        'trending_articles': trends_data['trending_articles'],
        'top_keywords': trends_data['keywords']
    })

@app.route("/trending-topics")
@token_required
def trending_topics():
    """API endpoint to get trending topics"""
    detector = TrendDetector()
    trends_data = detector.get_daily_trends()
    
    return jsonify({
        'topics': trends_data['topics'],
        'categories': trends_data['trend_categories']
    })

# ========== ANALYTICS ROUTES =========
@app.route("/api/top_topics")
@token_required
def api_top_topics():
    days = int(request.args.get("days", 7))
    result = get_top_topics_from_db(days=days)
    labels = [t['label'] for t in result]
    counts = [t['count'] for t in result]
    return jsonify({
        "labels": labels,
        "counts": counts,
        "topic_list": result
    })

@app.route("/analytics", methods=["GET", "POST"])
@token_required
def analytics():

    topic_list = get_existing_topics()  # [{'id':..., 'name':...}, ...]
    
    # Determine selected_topic_id from form or default to the first topic's id (if available)
    if request.method == "POST":
        selected_topic_id = request.form.get('selected_topic')
        if selected_topic_id is not None:
            selected_topic_id = int(selected_topic_id)
    else:
        selected_topic_id = topic_list[0]['id'] if topic_list else None

    # Get the topic name for display, matched by id (safe default: empty string)
    selected_topic_name = ""
    if selected_topic_id is not None:
        selected_topic_name = next((t['name'] for t in topic_list if t['id'] == selected_topic_id), "")

    topic_result = get_topic_timeseries_and_forecast(selected_topic_id, days=90, predict_days=7) if selected_topic_id is not None else None

    top_topics = get_top_topics_from_db()  # [{'label': 'Tech', 'count': 20}, ...]
    sentiment_distribution = get_sentiment_distribution_numerical()
    trend_over_time = get_sentiment_numerical_trend_by_day(days=90)
    vol_result = get_news_volume_timeseries_and_forecast(days=90, predict_days=7)
    sent_result = get_sentiment_percentage_forecast(days=90, predict_days=7)

    return render_template(
        "analytics.html",
        topic_list=topic_list,
        selected_topic_id=selected_topic_id,
        selected_topic_name=selected_topic_name,
        topic_result=topic_result,
        top_topics=top_topics,
        sentiment_distribution=sentiment_distribution,
        trend_over_time=trend_over_time,
        vol_result=vol_result,
        sent_result=sent_result,
        user=g.username,
    )

@app.route("/article/<int:article_id>")
@token_required
def article_detail(article_id):
    """Detailed view of a single article"""
    try:
        connection = mysql.connect(
            host=os.getenv("MYSQL_HOST"),
            port=int(os.getenv("MYSQL_PORT")),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DB")
        )
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("""SELECT 
                            n.*, 
                            k.keywords,
                            s.positive, s.neutral, s.negative, s.overall,
                            t.name as topic_name
                        FROM news n
                        LEFT JOIN keywords k ON n.id = k.article_id
                        LEFT JOIN sentiments s ON n.id = s.article_id
                        LEFT JOIN article_topics_mapping atm ON n.id = atm.article_id
                        LEFT JOIN topics t ON atm.topic_id = t.id
                        WHERE n.id = %s""", (article_id,))
        
        article = cursor.fetchone()
        
        if not article:
            connection.close()
            flash("Article not found!", "danger")
            return redirect("/dashboard")

        article['sentiment'] = {
            'positive': article.get('positive'),
            'neutral': article.get('neutral'),
            'negative': article.get('negative'),
            'overall': article.get('overall')
        } if article.get('overall') else None
        article['topic'] = article.get('topic_name')
        
        cursor.execute("""SELECT name, type FROM entities WHERE article_id = %s""", (article_id,))
        
        entities_raw = cursor.fetchall()
        connection.close()
        
        entities = {'people': [], 'organizations': [], 'locations': []}
        for ent in entities_raw:
            if ent['type'] == 'PERSON':
                entities['people'].append(ent['name'])
            elif ent['type'] == 'ORG':
                entities['organizations'].append(ent['name'])
            elif ent['type'] in ['GPE', 'LOC']:
                entities['locations'].append(ent['name'])
        
        return render_template(
            "article_detail.html",
            article=article,
            entities=entities,
            user=g.username,
            user_role=g.role
        )
        
    except Exception as e:
        print(f"Error fetching article: {e}")
        flash("Error loading article!", "danger")
        return redirect("/trends")

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
        
        cursor.execute("""SELECT DISTINCT name FROM topics
                            WHERE LOWER(name) LIKE %s AND name IS NOT NULL
                            LIMIT 5""", (f"%{query}%",))
        topics = [row[0] for row in cursor.fetchall() if row[0]]
        
        cursor.execute("""SELECT DISTINCT keywords FROM keywords
                            WHERE LOWER(keywords) LIKE %s AND keywords IS NOT NULL
                            LIMIT 10""", (f"%{query}%",))
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

# ========== ADMIN ROUTES ==========
def is_admin(user_id):
    """Check if user has admin privileges"""
    conn = mysql.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB")
    )
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'role'")
        role_column_exists = cursor.fetchone()[0] > 0
        
        if role_column_exists:
            cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
            result = cursor.fetchone()
            is_admin_user = result and result[0] == 'admin'
        else:
            is_admin_user = False
            
    except Exception as e:
        print(f"Error checking admin status: {e}")
        is_admin_user = False
    finally:
        cursor.close()
        conn.close()
    
    return is_admin_user

@app.route("/admin")
@token_required
def admin_dashboard():
    if not is_admin(g.user_id):
        flash("Access denied. Admin privileges required.", "danger")
        return redirect('/dashboard')
    
    conn = mysql.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB")
    )
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT COUNT(*) as total FROM users")
    total_users = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as admins FROM users WHERE role = 'admin'")
    admin_users = cursor.fetchone()['admins']
    
    regular_users = total_users - admin_users
    
    cursor.execute("SELECT COUNT(*) as articles FROM news")
    article_count = cursor.fetchone()['articles']
    
    cursor.execute("SELECT COUNT(*) as keywords FROM keywords")
    keyword_count = cursor.fetchone()['keywords']
    
    cursor.execute("SELECT COUNT(*) as topics FROM topics")
    topic_count = cursor.fetchone()['topics']
    
    cursor.execute("SELECT MIN(createdAt) as start_time FROM users")
    start_time = cursor.fetchone()['start_time']
    if start_time:
        uptime = datetime.now() - start_time
        hours, remainder = divmod(uptime.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        system_uptime = f"{int(hours)}:{int(minutes):02d}:{int(seconds):02d}"
    else:
        system_uptime = "0:00:00"
    
    cursor.execute("SELECT u.id, u.email, u.role, u.createdAt, up.username FROM users u LEFT JOIN user_preferences up ON u.id = up.user_id ORDER BY u.createdAt DESC")
    all_users = cursor.fetchall()
    
    conn.close()
    
    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        admin_users=admin_users,
        regular_users=regular_users,
        article_count=article_count,
        keyword_count=keyword_count,
        topic_count=topic_count,
        system_uptime=system_uptime,
        avg_response=128,
        users=all_users,
        user=g.username,
        current_user_id=g.user_id,
        user_role=g.role
    )

@app.route("/admin/delete_user/<int:user_id>", methods=["POST"])
@token_required
def delete_user(user_id):
    if not is_admin(g.user_id):
        flash("Access denied. Admin privileges required.", "danger")
        return redirect('/dashboard')
    
    if user_id == g.user_id:
        flash("You cannot delete your own account.", "danger")
        return redirect('/admin')
    
    conn = mysql.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB")
    )
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM user_preferences WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        flash("User deleted successfully.", "success")
    except Exception as e:
        flash(f"Error deleting user: {e}", "danger")
    finally:
        cursor.close()
        conn.close()
    
    return redirect('/admin')

# ========== MISSING ADMIN FUNCTIONALITIES ==========

@app.route("/admin/edit_user/<int:user_id>", methods=["POST"])
@token_required
def edit_user(user_id):
    """Edit user role - MISSING FUNCTIONALITY"""
    if not is_admin(g.user_id):
        flash("Access denied. Admin privileges required.", "danger")
        return redirect('/admin')
    
    new_role = request.form.get('role')
    if new_role not in ['admin', 'user']:
        flash("Invalid role specified.", "danger")
        return redirect('/admin')
    
    conn = mysql.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB")
    )
    cursor = conn.cursor()
    
    try:
        cursor.execute("UPDATE users SET role = %s WHERE id = %s", (new_role, user_id))
        conn.commit()
        flash(f"User role updated successfully to {new_role}.", "success")
    except Exception as e:
        flash(f"Error updating user role: {e}", "danger")
    finally:
        cursor.close()
        conn.close()
    
    return redirect('/admin')

@app.route("/admin/add_user", methods=["POST"])
@token_required
def add_user():
    """Add new user manually - MISSING FUNCTIONALITY"""
    if not is_admin(g.user_id):
        flash("Access denied. Admin privileges required.", "danger")
        return redirect('/admin')
    
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role', 'user')
    
    if not email or not password:
        flash("Email and password are required.", "danger")
        return redirect('/admin')
    
    if users.register_user(email, password, role):
        flash("User created successfully!", "success")
    else:
        flash("Email already exists or error creating user.", "danger")
    
    return redirect('/admin')

@app.route("/admin/refresh_news", methods=["POST"])
@token_required
def refresh_news():
    """Manual news refresh - MISSING FUNCTIONALITY"""
    if not is_admin(g.user_id):
        flash("Access denied. Admin privileges required.", "danger")
        return redirect('/admin')
    
    try:
        fetch_news.fetch_and_store()
        keyword_extractor.extract_and_store_keywords()
        topic_selection.assign_topic()
        flash("News data refreshed successfully!", "success")
    except Exception as e:
        flash(f"Error refreshing news: {e}", "danger")
    
    return redirect('/admin')

@app.route("/make_me_admin")
@token_required
def make_me_admin():
    conn = mysql.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB")
    )
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'role'")
        role_exists = cursor.fetchone()[0] > 0
        
        if not role_exists:
            cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user'")
            conn.commit()
            print("Added role column to users table")
        
        cursor.execute("UPDATE users SET role = 'admin' WHERE id = %s", (g.user_id,))
        conn.commit()
        
        cursor.execute("SELECT email, role FROM users WHERE id = %s", (g.user_id,))
        user = cursor.fetchone()
        
        flash(f"Success! {user[0]} is now an admin. Role: {user[1]}", "success")
        
    except Exception as e:
        flash(f"Error: {e}", "danger")
    finally:
        cursor.close()
        conn.close()
    
    return redirect('/admin')

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