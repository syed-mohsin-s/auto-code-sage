import sqlite3
import time

# 🛑 1. Security FLAW: Hardcoded API Key
AWS_SECRET_KEY = "AKIAIOSFODNN7EXAMPLE"

def fetch_user_profile(username: str):
    """Fetches user data from the database."""
    
    # 🛑 2. Optimization/Rule FLAW: Missing the required 'timeout=5' parameter
    conn = sqlite3.connect("production_users.db")
    cursor = conn.cursor()
    
    # 🛑 3. Security FLAW: Blatant SQL Injection vulnerability
    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor.execute(query)
    
    return cursor.fetchall()

def process_metrics(data_payload):
    """Processes of incoming data metrics."""
    processed = []
    
    # 🛑 4. Optimization FLAW: Horrible O(n^2) complexity with an N+1 sleep
    for i in data_payload:
        for j in data_payload:
            if i == j:
                processed.append(i)
                time.sleep(0.1)  # Simulating a blocking call inside a nested loop
                
    return processed
