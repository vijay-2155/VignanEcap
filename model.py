import sqlite3
from contextlib import contextmanager

@contextmanager
def get_db():
    db = sqlite3.connect('users.db')
    try:
        yield db
    finally:
        db.close()

def init_db():
    with get_db() as db:
        db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            phone TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            keyword TEXT NOT NULL
        )
        ''')
        db.commit()

def save_user(phone, username, password, keyword):
    """Save user credentials - keyword is stored lowercase"""
    with get_db() as db:
        db.execute('''
        INSERT OR REPLACE INTO users (phone, username, password, keyword)
        VALUES (?, ?, ?, ?)
        ''', (phone, username, password, keyword.lower()))
        db.commit()

def get_user(phone):
    with get_db() as db:
        cursor = db.execute('SELECT * FROM users WHERE phone = ?', (phone,))
        return cursor.fetchone()

def get_user_by_keyword(phone, keyword):
    with get_db() as db:
        cursor = db.execute('SELECT * FROM users WHERE phone = ? AND keyword = ?', 
                          (phone, keyword))
        return cursor.fetchone()