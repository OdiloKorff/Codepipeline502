
import sqlite3

def unsafe_query(user_input):
    """VULNERABLE: SQL Injection möglich"""
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    
    # VULNERABILITY: Direkte String-Interpolation ohne Parametrisierung
    query = f"SELECT * FROM users WHERE name = '{user_input}'"
    cursor.execute(query)
    
    return cursor.fetchall()

def unsafe_login(username, password):
    """VULNERABLE: SQL Injection in Login"""
    conn = sqlite3.connect("users.db")
    
    # VULNERABILITY: String-Formatierung mit user input
    sql = "SELECT id FROM users WHERE username='%s' AND password='%s'" % (username, password)
    cursor = conn.execute(sql)
    
    return cursor.fetchone() is not None
