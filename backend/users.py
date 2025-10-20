import mysql.connector
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from datetime import datetime, timedelta
import user_profile

load_dotenv()

def connect_db():
    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB")
    )
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(255) UNIQUE,
        password LONGTEXT,
        createdAt DATETIME,
        updatedAt DATETIME);''')
    conn.commit()
    return conn

def register_user(email, password):
    conn = connect_db()
    cursor = conn.cursor()
    
    # Check if user already exists
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return False # User already exists

    # Hash the password before storing
    hashed_password = generate_password_hash(password)
    now = datetime.now()
    
    try:
        cursor.execute("INSERT INTO users (email, password, createdAt) VALUES (%s, %s, %s)", (email, hashed_password, now))
        conn.commit()
        user_profile.update_user_profile(cursor.lastrowid, "", "", "")
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return False
    finally:
        cursor.close()
        conn.close()
    return True # Registration successful

def login_user(email, password, secret_key):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    cursor.close
    conn.close()

    if user and check_password_hash(user['password'], password):
        try:
            conn = user_profile.connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM user_preferences WHERE user_id = %s", (user['id'],))
            username = cursor.fetchone()
            payload = {
                'exp': datetime.utcnow() + timedelta(days=1),
                'iat': datetime.utcnow(),
                'sub': str(user['id']),
                'username': username[0] if username else ""
            }
            token = jwt.encode(
                payload,
                secret_key,
                algorithm='HS256'
            )
            cursor.close()
            conn.close()
            return token
        except Exception as e:
            print(f"Error encoding JWT: {e}")
            return None
    return None
