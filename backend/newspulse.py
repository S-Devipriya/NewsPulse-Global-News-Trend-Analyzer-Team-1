from flask import Flask, render_template, request, redirect, flash, make_response, g, current_app
import mysql.connector as mysql
from text_preprocessing import preprocess_text
import fetch_news
import keyword_extractor
import topic_selection
import users
import os
from dotenv import load_dotenv
from functools import wraps
import jwt

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
        
    if search_query:
        cleaned_search_query = preprocess_text(search_query)
        
        if cleaned_search_query:
            sql_query = "SELECT title, source, publishedAt, url, description, imageurl, keywords, topic FROM news WHERE "
            sql_query += "title LIKE %s OR description LIKE %s"
            sql_query += " ORDER BY publishedAt DESC"
            
            cursor.execute(sql_query, (f"%{cleaned_search_query}%", f"%{cleaned_search_query}%"))
        else:
            articles = []
    else:
        sql_query = "SELECT title, source, publishedAt, url, description, imageurl, keywords, topic FROM news ORDER BY publishedAt DESC"
        cursor.execute(sql_query)
        
    articles = cursor.fetchall()
    connection.close()
    return articles


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
        username = request.form["username"]
        password = request.form["password"]
        if users.register_user(username, password):
            flash("Registration successful! Please log in.", "success")
            return redirect("/login")
        else:
            flash("Username already exists. Please choose another.", "danger")
            return redirect("/register")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        secret_key = os.getenv("FLASK_SECRET_KEY")
        
        # Pass the key to the login function
        token = users.login_user(username, password, secret_key)
        
        if token:
            response = make_response(redirect('/dashboard'))
            response.set_cookie('token', token, httponly=True, samesite='Lax')
            return response
        else:
            flash("Invalid username or password!", "danger")
            return redirect("/login")
    return render_template("login.html")

@app.route("/dashboard", methods=["GET", "POST"])
@token_required
def dashboard():
    query = request.form.get("query", "latest").strip()
    news_items = fetch_from_db(query)
    
    return render_template(
        "dashboard.html",
        news=news_items,
        user=g.username,
        query=query
    )

@app.route("/logout")
def logout():
    # Clear the token cookie upon logout
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
