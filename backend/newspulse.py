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

# ADD THIS IMPORT for trend analysis
from trend_detector import TrendDetector

load_dotenv()

def fetch_from_db(search_query):
    fetch_news.fetch_and_store()
    keyword_extractor.extract_and_store_keywords()
    topic_selection.assign_topic()
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
            g.role = data.get('role', 'user')
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
    
    # ADD TREND ANALYSIS TO DASHBOARD
    detector = TrendDetector()
    trends_data = detector.get_daily_trends()
    
    enriched_news = []
    for article in news_items:
        text = f"{article.get('title', '')}. {article.get('description', '')}"
        article_id = article['id']
        sentiment = analyze_sentiment(text)
        save_sentiment(article_id, sentiment)
        entities_list = extract_entities(text)  # This returns a LIST, not dict
        save_entities(article_id, entities_list)  # Pass the list directly
        article['sentiment'] = sentiment
        article['entities'] = entities_list  # Store the list
        enriched_news.append(article)
    
    return render_template(
        "dashboard.html",
        news=enriched_news,
        user=g.username,
        query=query,
        summary=summary,
        trends_data=trends_data,
        now=datetime.now(),
        role=g.role
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
        now=datetime.now(),
        role=g.role
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
        
        cursor.execute("""
            SELECT n.*, s.sentiment_score, s.sentiment_label 
            FROM news n
            LEFT JOIN sentiment s ON n.id = s.article_id
            WHERE n.id = %s
        """, (article_id,))
        
        article = cursor.fetchone()
        
        # Get entities separately
        cursor.execute("""
            SELECT people, organizations, locations 
            FROM entities 
            WHERE article_id = %s
        """, (article_id,))
        
        entities_result = cursor.fetchone()
        connection.close()
        
        if not article:
            flash("Article not found!", "danger")
            return redirect("/trends")
        
        # Process entities
        entities = {
            'people': entities_result['people'].split(',') if entities_result and entities_result['people'] else [],
            'organizations': entities_result['organizations'].split(',') if entities_result and entities_result['organizations'] else [],
            'locations': entities_result['locations'].split(',') if entities_result and entities_result['locations'] else []
        }
        
        return render_template(
            "article_detail.html",
            article=article,
            entities=entities,
            user=g.username,
            role=g.role
        )
        
    except Exception as e:
        print(f"Error fetching article: {e}")
        flash("Error loading article!", "danger")
        return redirect("/trends")

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
    entities_list = extract_entities(text)  # FIXED: This returns a LIST
    if article_id:
        save_entities(article_id, entities_list)  # FIXED: Pass list directly
    return jsonify(entities_list)  # FIXED: Return the list

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

# ========== ADMIN: Check if user is admin ==========
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
        # Check if role column exists
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'users' 
            AND COLUMN_NAME = 'role'
        """)
        role_column_exists = cursor.fetchone()[0] > 0
        
        if role_column_exists:
            cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
            result = cursor.fetchone()
            is_admin_user = result and result[0] == 'admin'
        else:
            # If role column doesn't exist, no one is admin yet
            is_admin_user = False
            
    except Exception as e:
        print(f"Error checking admin status: {e}")
        is_admin_user = False
    finally:
        cursor.close()
        conn.close()
    
    return is_admin_user

# ========== ADMIN: Enhanced Admin Dashboard Route ==========
@app.route("/admin")
@token_required
def admin_dashboard():
    # Check if user is admin
    if not is_admin(g.user_id):
        flash("Access denied. Admin privileges required.", "danger")
        return redirect('/dashboard')
    
    # Get admin statistics
    conn = mysql.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB")
    )
    cursor = conn.cursor(dictionary=True)
    
    # Get user statistics
    cursor.execute("SELECT COUNT(*) as total FROM users")
    total_users = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as admins FROM users WHERE role = 'admin'")
    admin_users = cursor.fetchone()['admins']
    
    regular_users = total_users - admin_users
    
    # Get other statistics
    cursor.execute("SELECT COUNT(*) as articles FROM news")
    article_count = cursor.fetchone()['articles']
    
    cursor.execute("SELECT COUNT(*) as keywords FROM keywords")
    keyword_count = cursor.fetchone()['keywords']
    
    cursor.execute("SELECT COUNT(*) as topics FROM topics")
    topic_count = cursor.fetchone()['topics']
    
    # Get system uptime (simplified - you can enhance this)
    cursor.execute("SELECT MIN(createdAt) as start_time FROM users")
    start_time = cursor.fetchone()['start_time']
    if start_time:
        uptime = datetime.now() - start_time
        hours, remainder = divmod(uptime.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        system_uptime = f"{int(hours)}:{int(minutes):02d}:{int(seconds):02d}"
    else:
        system_uptime = "0:00:00"
    
    # Get all users for the table with usernames
    cursor.execute("""
        SELECT u.id, u.email, u.role, u.createdAt, up.username 
        FROM users u 
        LEFT JOIN user_preferences up ON u.id = up.user_id 
        ORDER BY u.createdAt DESC
    """)
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
        avg_response=128,  # You can calculate this dynamically later
        users=all_users,
        username=g.username,
        current_user_id=g.user_id,
        role=g.role
    )

# ========== ADMIN: Delete User Route ==========
@app.route("/admin/delete_user/<int:user_id>", methods=["POST"])
@token_required
def delete_user(user_id):
    # Check if user is admin
    if not is_admin(g.user_id):
        flash("Access denied. Admin privileges required.", "danger")
        return redirect('/dashboard')
    
    # Prevent admin from deleting themselves
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
        # First delete user preferences
        cursor.execute("DELETE FROM user_preferences WHERE user_id = %s", (user_id,))
        # Then delete the user
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        flash("User deleted successfully.", "success")
    except Exception as e:
        flash(f"Error deleting user: {e}", "danger")
    finally:
        cursor.close()
        conn.close()
    
    return redirect('/admin')

# ========== TEMPORARY: Make current user admin ==========
@app.route("/make_me_admin")
@token_required
def make_me_admin():
    """Temporary route to make current user admin"""
    conn = mysql.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB")
    )
    cursor = conn.cursor()
    
    try:
        # First, ensure role column exists
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'users' 
            AND COLUMN_NAME = 'role'
        """)
        role_exists = cursor.fetchone()[0] > 0
        
        if not role_exists:
            cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user'")
            conn.commit()
            print("Added role column to users table")
        
        # Make current user admin
        cursor.execute("UPDATE users SET role = 'admin' WHERE id = %s", (g.user_id,))
        conn.commit()
        
        # Get user email to confirm
        cursor.execute("SELECT email, role FROM users WHERE id = %s", (g.user_id,))
        user = cursor.fetchone()
        
        flash(f"Success! {user[0]} is now an admin. Role: {user[1]}", "success")
        
    except Exception as e:
        flash(f"Error: {e}", "danger")
    finally:
        cursor.close()
        conn.close()
    
    return redirect('/admin')

# ========== DEBUG: Check user status ==========
@app.route("/debug_user")
@token_required
def debug_user():
    """Debug route to check user status"""
    conn = mysql.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB")
    )
    cursor = conn.cursor(dictionary=True)
    
    # Check current user
    cursor.execute("SELECT id, email, role FROM users WHERE id = %s", (g.user_id,))
    current_user = cursor.fetchone()
    
    # Check all users
    cursor.execute("SELECT id, email, role FROM users")
    all_users = cursor.fetchall()
    
    # Check if role column exists
    cursor.execute("""
        SELECT COUNT(*) as exists_flag FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = 'users' 
        AND COLUMN_NAME = 'role'
    """)
    role_column_exists = cursor.fetchone()['exists_flag'] > 0
    
    conn.close()
    
    return f"""
    <h1>Debug Info</h1>
    <h3>Current User:</h3>
    <pre>{current_user}</pre>
    <h3>All Users:</h3>
    <pre>{all_users}</pre>
    <h3>Role Column Exists: {role_column_exists}</h3>
    <h3>Is Admin: {is_admin(g.user_id)}</h3>
    <br>
    <a href="/make_me_admin">Make Me Admin</a> | 
    <a href="/admin">Try Admin Again</a>
    """

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

# ========== ADMIN: Initialize admin user on startup ==========
with app.app_context():
    users.create_admin_user()

if __name__ == "__main__":
    app.run(debug=True)