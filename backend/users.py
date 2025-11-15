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
        role TEXT,
        createdAt DATETIME,
        updatedAt DATETIME);''')
    conn.commit()
    return conn

def register_user(email, password, role='user'):
    """Register a new user with optional role"""
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
        cursor.execute("INSERT INTO users (email, password, role, createdAt) VALUES (%s, %s, %s, %s)", (email, hashed_password, role, now))
        conn.commit()
        user_profile.update_user_profile(cursor.lastrowid, "", "", "")
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return False
    finally:
        cursor.close()
        conn.close()
    return True # Registration successful

def login_user(email, password):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user and check_password_hash(user['password'], password):
        conn = user_profile.connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM user_preferences WHERE user_id = %s", (user['id'],))
        username = cursor.fetchone()
        return {
        'id': user['id'],
        'email': user['email'],
        'role': user['role'],
        'username': username[0] if username else ""
        }
    return None

def create_admin_user():
    """Create an admin user if none exists"""
    conn = connect_db()
    cursor = conn.cursor()
    
    try:
        # Check if admin user exists
        cursor.execute("SELECT * FROM users WHERE role = 'admin'")
        admin_exists = cursor.fetchone()
        
        if not admin_exists:
            # Create default admin user
            email = "admin@newspulse.com"
            password = "admin123"
            hashed_password = generate_password_hash(password)
            now = datetime.now()
            
            cursor.execute(
                "INSERT INTO users (email, password, role, createdAt) VALUES (%s, %s, %s, %s)",
                (email, hashed_password, 'admin', now)
            )
            conn.commit()
            print("Admin user created: admin@newspulse.com / admin123")
        
    except Exception as e:
        print(f"Error creating admin user: {e}")
    finally:
        cursor.close()
        conn.close()

def login_user(email, password, secret_key):
    """
    Login user and return JWT token
    This function is used by newspulse.py for token generation
    """
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user and check_password_hash(user['password'], password):
        # Get username from user_preferences
        conn = user_profile.connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM user_preferences WHERE user_id = %s", (user['id'],))
        username_result = cursor.fetchone()
        username = username_result[0] if username_result else ""
        cursor.close()
        conn.close()

        # Create JWT token
        token = jwt.encode({
            'exp': datetime.utcnow() + timedelta(days=1),
            'iat': datetime.utcnow(),
            'sub': str(user['id']),
            'username': username,
            'role': user.get('role', 'user')
        }, secret_key, algorithm='HS256')
        
        return token
    return None