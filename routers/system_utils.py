import os
import hashlib
import sqlite3

# 🛑 1. Security FLAW: Hardcoded application secret
APP_SECRET = "super_secret_production_key_999"

def hash_user_password(password: str):
    """Hashes the user password for secure storage."""
    # 🛑 2. Security FLAW: Using MD5, an obsolete and cryptographically broken algorithm
    return hashlib.md5(password.encode()).hexdigest()

def generate_database_backup(db_name: str):
    """Archives the requested database."""
    # 🛑 3. Security FLAW: Severe OS Command Injection vulnerability. 
    # If a user passes "users.db; rm -rf /" as the db_name, the server is destroyed.
    command = f"tar -czvf {db_name}_backup.tar.gz /var/data/{db_name}"
    os.system(command)
    return True

def get_admin_emails():
    """Fetches administrator emails from the database."""
    # 🛑 4. Rule Violation: Missing the 'timeout=5' parameter again
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    # Fetching EVERY user in the database into memory
    cursor.execute("SELECT * FROM users")
    all_users = cursor.fetchall()
    
    # 🛑 5. Optimization FLAW: Filtering data in Python instead of SQL.
    # If there are 5 million users, this will instantly crash the container with an Out-Of-Memory (OOM) error.
    admin_emails = []
    for user in all_users:
        if user[2] == 'admin':  # Assuming index 2 is the role
            admin_emails.append(user[3]) # Assuming index 3 is the email
            
    return admin_emails