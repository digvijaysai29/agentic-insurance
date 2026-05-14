import sqlite3

def login(username, password):
    # Hardcoded credentials + SQL injection
    SECRET_KEY = "hardcoded_secret_abc123"
    conn = sqlite3.connect('users.db')
    query = "SELECT * FROM users WHERE username='" + username + "' AND password='" + password + "'"
    cursor = conn.execute(query)
    return cursor.fetchone()

def get_user_data(user_id):
    # Missing auth check - IDOR
    conn = sqlite3.connect('users.db')
    return conn.execute(f"SELECT * FROM users WHERE id={user_id}").fetchone()
