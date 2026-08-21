import sqlite3
from core.config import DB_PATH

def get_db_connection():
    """Create and return a database connection with Row factory"""
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.row_factory = sqlite3.Row
    return conn

def _get_columns(cursor, table):
    """Return list of column names for a table (empty list if table missing)"""
    try:
        cursor.execute(f"PRAGMA table_info({table})")
        return [row[1] for row in cursor.fetchall()]
    except Exception:
        return []

def _rebuild_table(cursor, table, create_sql, column_map):
    """
    Rebuild a legacy table into the canonical schema without losing data.
    column_map: {canonical_column: legacy_column_or_None}
    """
    existing = _get_columns(cursor, table)
    cursor.execute(f"ALTER TABLE {table} RENAME TO {table}_legacy")
    cursor.execute(create_sql)

    targets, sources = [], []
    for canonical, legacy in column_map.items():
        source = legacy if legacy in existing else (canonical if canonical in existing else None)
        if source:
            targets.append(canonical)
            sources.append(source)

    if targets:
        cursor.execute(
            f"INSERT INTO {table} ({', '.join(targets)}) SELECT {', '.join(sources)} FROM {table}_legacy"
        )
    cursor.execute(f"DROP TABLE {table}_legacy")
    print(f"DB Auto-Migration: Rebuilt table '{table}' to canonical schema")

# === Canonical schemas (single source of truth for the whole project) ===
LAST_POST_TIME_SQL = '''
    CREATE TABLE IF NOT EXISTS last_post_time (
        page_id TEXT PRIMARY KEY,
        timestamp TEXT,
        cooldown_until TEXT
    )
'''

POST_QUEUE_SQL = '''
    CREATE TABLE IF NOT EXISTS post_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        page_id TEXT,
        content TEXT,
        image_path TEXT,
        scheduled_time TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        posted_at TEXT,
        error_message TEXT
    )
'''

def init_db():
    """Initialize the database tables if they do not exist, and auto-migrate legacy schemas"""
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
            error_message TEXT,
            layout_name TEXT,
            hook_type TEXT
        )
    ''')
    cursor.execute(LAST_POST_TIME_SQL)
    cursor.execute(POST_QUEUE_SQL)
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
            user_id TEXT,
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
    # Cache engagement Facebook (dipakai halaman Analytics & AI insights)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS engagement_cache (
            fb_post_id TEXT PRIMARY KEY,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            cached_at TEXT NOT NULL
        )
    ''')

    # === Auto Migration: Cek & Tambahkan Kolom yang Belum Ada ===
    migrations = [
        ('topic_preferences', 'last_updated', 'DATETIME'),
        ('topic_preferences', 'page_id', 'TEXT'),
        ('posts', 'layout_name', 'TEXT'),
        ('posts', 'hook_type', 'TEXT'),
        ('engagement_baseline', 'last_updated', 'DATETIME'),
        ('replied_comments', 'user_id', 'TEXT'),
        # Skor editor AI disimpan agar bisa diuji: apakah nilai tinggi dari
        # editor benar-benar berkorelasi dengan engagement nyata?
        ('posts', 'editor_score', 'REAL'),
        # Hook yang DIMINTA sistem (vs hook_type = yang benar-benar terdeteksi),
        # supaya tingkat kepatuhan generator bisa diukur, bukan ditebak
        ('posts', 'requested_hook', 'TEXT'),
    ]
    for table, col, col_type in migrations:
        try:
            columns = _get_columns(cursor, table)
            if columns and col not in columns:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                if col_type == 'DATETIME':
                    cursor.execute(f"UPDATE {table} SET {col} = CURRENT_TIMESTAMP WHERE {col} IS NULL")
                print(f"DB Auto-Migration: Added column '{col}' to table '{table}'")
        except Exception as e:
            print(f"WARNING: DB Migration check for {table}.{col}: {e}")

    # === Auto Migration: Normalisasi tabel yang pernah dibuat dengan skema berbeda ===
    # Versi lama auto_poster.py memakai nama kolom 'last_posted' dan 'caption',
    # sementara sisa aplikasi memakai 'timestamp' dan 'content'.
    try:
        cols = _get_columns(cursor, 'last_post_time')
        if cols and ('timestamp' not in cols or 'cooldown_until' not in cols or 'last_posted' in cols):
            _rebuild_table(cursor, 'last_post_time', LAST_POST_TIME_SQL, {
                'page_id': 'page_id',
                'timestamp': 'last_posted',
                'cooldown_until': 'cooldown_until',
            })
    except Exception as e:
        print(f"WARNING: DB Migration last_post_time: {e}")

    try:
        cols = _get_columns(cursor, 'post_queue')
        required = {'content', 'scheduled_time', 'created_at', 'posted_at', 'error_message'}
        if cols and (not required.issubset(cols) or 'caption' in cols):
            _rebuild_table(cursor, 'post_queue', POST_QUEUE_SQL, {
                'id': 'id',
                'page_id': 'page_id',
                'content': 'caption',
                'image_path': 'image_path',
                'scheduled_time': 'scheduled_time',
                'status': 'status',
                'created_at': 'created_at',
                'posted_at': 'posted_at',
                'error_message': 'error_message',
            })
            # Antrean lama tidak punya scheduled_time — pakai created_at agar urutan proses tetap benar
            cursor.execute("UPDATE post_queue SET scheduled_time = created_at WHERE scheduled_time IS NULL")
    except Exception as e:
        print(f"WARNING: DB Migration post_queue: {e}")

    conn.commit()
    conn.close()
