from flask import Flask, render_template, request, redirect, session
import mysql.connector as mysql
from text_preprocessing import preprocess_text
import fetch_news
import users
import os
from dotenv import load_dotenv

load_dotenv()

def fetch_from_db(search_query):
    fetch_news.fetch_and_store() 
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
            sql_query = "SELECT title, source, publishedAt, url, description, imageurl FROM news WHERE "
            sql_query += "title LIKE %s OR description LIKE %s"
            sql_query += " ORDER BY publishedAt DESC"
            
            cursor.execute(sql_query, (f"%{cleaned_search_query}%", f"%{cleaned_search_query}%"))
        else:
            articles = []
    else:
        sql_query = "SELECT title, source, publishedAt, url, description, imageurl FROM news ORDER BY publishedAt DESC"
        cursor.execute(sql_query)
        
    articles = cursor.fetchall()
    connection.close()
    return articles


app = Flask(__name__, template_folder='../templates')
app.secret_key = os.getenv("FLASK_SECRET_KEY")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        users.register_user(username, password)
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = users.login_user(username, password)
        if user:
            session["username"] = username
            return redirect("/dashboard")
        else:
            return "Invalid username or password!"
    return render_template("login.html")

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "username" not in session:
        return redirect("/login")

    query = None
    corrected_query = None
    news_items = []

    if request.method == "POST":
        query = request.form.get("query", "").strip()
        news_items = fetch_from_db(query)

    else:
        query = "latest"
        news_items = fetch_from_db(query)

    return render_template(
        "dashboard.html",
        news=news_items,
        user=session["username"],
        query=query,
        corrected_query=corrected_query
    )

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/login")

@app.route("/")
def home():
    return render_template("home.html")

if __name__ == "__main__":
    app.run(debug=True)
