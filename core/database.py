import sqlite3
from core.config import DB_PATH

def get_db_connection():
    """Create and return a database connection with Row factory"""
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database tables if they do not exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            page_name TEXT,
            page_id TEXT,
            content TEXT,
            image_path TEXT,
            fb_post_id TEXT,
            status TEXT,
            error_message TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS last_post_time (
            page_id TEXT PRIMARY KEY,
            timestamp TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS post_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_id TEXT,
            content TEXT,
            image_path TEXT,
            scheduled_time TEXT,
            status TEXT DEFAULT 'pending'
        )
    ''')
    # === Learning / ML Research tables ===
    # Tabel insight dari analisis komentar & engagement
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comment_insights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            page_id TEXT,
            page_name TEXT,
            total_comments_analyzed INTEGER,
            top_keywords TEXT,
            requested_topics TEXT,
            sentiment TEXT,
            suggested_topics TEXT,
            raw_analysis TEXT
        )
    ''')
    # Preferensi topik audience (boost_score makin tinggi makin diprioritaskan)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS topic_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_id TEXT,
            topic_keyword TEXT NOT NULL,
            boost_score INTEGER DEFAULT 1,
            source TEXT DEFAULT 'comment_analysis',
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Tracking komentar yang sudah dibalas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS replied_comments (
            comment_id TEXT PRIMARY KEY,
            post_id TEXT,
            user_name TEXT,
            comment_text TEXT,
            reply_text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Baseline engagement historis per page (untuk normalisasi skor)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS engagement_baseline (
            page_id TEXT PRIMARY KEY,
            avg_engagement REAL DEFAULT 0,
            sample_count INTEGER DEFAULT 0,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

