import mysql.connector
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

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
    cursor.execute('''CREATE TABLE IF NOT EXISTS user_preferences (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT UNIQUE,
        username VARCHAR(255),
        language VARCHAR(50),
        interests VARCHAR(255),
        createdAt DATETIME,
        updatedAt DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id));''')
    conn.commit()
    return conn

def get_user_profile(user_id):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM user_preferences WHERE user_id = %s", (user_id,))
    profile = cursor.fetchone()
    cursor.close()
    conn.close()
    return profile

def update_user_profile(user_id, username, language, interests):
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM user_preferences WHERE user_id = %s", (user_id,))
    existing_profile = cursor.fetchone()
    
    now = datetime.now()
    if existing_profile:
        cursor.execute("""
            UPDATE user_preferences 
            SET username = %s, language = %s, interests = %s, updatedAt = %s 
            WHERE user_id = %s
        """, (username, language, interests, now, user_id))
    else:
        cursor.execute("""
            INSERT INTO user_preferences (user_id, username, language, interests, createdAt, updatedAt) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, username, language, interests, now, now))
    
    conn.commit()
    cursor.close()
    conn.close()