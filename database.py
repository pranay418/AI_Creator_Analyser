import sqlite3
import os
from datetime import datetime
import pandas as pd

DB_FILE = "analytics.db"

def get_db_connection():
    """Establishes connection to the SQLite database."""
    conn = sqlite3.connect(DB_FILE, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database and creates required tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create creators table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS creators (
            profile_url TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            creator_name TEXT NOT NULL,
            safety_score REAL DEFAULT 100.0,
            last_scanned TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create comments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_url TEXT NOT NULL,
            author TEXT NOT NULL,
            text TEXT NOT NULL,
            timestamp TEXT,
            classification TEXT NOT NULL, -- Proper, Toxic, Abusive, Harmful, Spam
            severity_score REAL DEFAULT 0.0, -- Range: 0.0 to 1.0
            flagged_words TEXT DEFAULT "", -- Comma-separated triggers
            FOREIGN KEY (profile_url) REFERENCES creators (profile_url) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()

def add_or_update_creator(profile_url, platform, creator_name, safety_score=100.0):
    """Inserts or updates a creator profile in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO creators (profile_url, platform, creator_name, safety_score, last_scanned)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(profile_url) DO UPDATE SET
            creator_name = excluded.creator_name,
            safety_score = excluded.safety_score,
            last_scanned = excluded.last_scanned
    """, (profile_url, platform, creator_name, safety_score, now))
    
    conn.commit()
    conn.close()

def save_comments(profile_url, comments_list):
    """
    Saves a list of analyzed comments for a creator.
    Deletes existing comments for that creator first to avoid duplicates.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Delete old comments for this profile
    cursor.execute("DELETE FROM comments WHERE profile_url = ?", (profile_url,))
    
    # Batch insert new comments
    insert_data = []
    for c in comments_list:
        insert_data.append((
            profile_url,
            c.get("author", "Anonymous"),
            c.get("text", ""),
            c.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            c.get("classification", "Proper"),
            float(c.get("severity_score", 0.0)),
            c.get("flagged_words", "")
        ))
        
    cursor.executemany("""
        INSERT INTO comments (profile_url, author, text, timestamp, classification, severity_score, flagged_words)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, insert_data)
    
    # Recalculate average safety score
    # Safety score = (Count of Proper Comments / Total Comments) * 100
    cursor.execute("SELECT COUNT(*) FROM comments WHERE profile_url = ?", (profile_url,))
    total = cursor.fetchone()[0]
    
    if total > 0:
        cursor.execute("SELECT COUNT(*) FROM comments WHERE profile_url = ? AND classification = 'Proper'", (profile_url,))
        proper_count = cursor.fetchone()[0]
        safety_score = round((proper_count / total) * 100.0, 1)
    else:
        safety_score = 100.0
        
    cursor.execute("UPDATE creators SET safety_score = ? WHERE profile_url = ?", (safety_score, profile_url))
    
    conn.commit()
    conn.close()
    return safety_score

def get_creators():
    """Returns a DataFrame of all monitored content creators."""
    conn = get_db_connection()
    query = """
        SELECT profile_url, platform, creator_name, safety_score, last_scanned,
               (SELECT COUNT(*) FROM comments WHERE comments.profile_url = creators.profile_url) as total_comments,
               (SELECT COUNT(*) FROM comments WHERE comments.profile_url = creators.profile_url AND classification != 'Proper') as flagged_comments
        FROM creators
        ORDER BY last_scanned DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_comments(profile_url, classification_filter=None):
    """
    Retrieves analyzed comments for a creator.
    Can be filtered by classification list.
    """
    conn = get_db_connection()
    
    if classification_filter:
        placeholders = ",".join(["?"] * len(classification_filter))
        query = f"""
            SELECT author, text, timestamp, classification, severity_score, flagged_words
            FROM comments
            WHERE profile_url = ? AND classification IN ({placeholders})
            ORDER BY severity_score DESC
        """
        params = [profile_url] + list(classification_filter)
    else:
        query = """
            SELECT author, text, timestamp, classification, severity_score, flagged_words
            FROM comments
            WHERE profile_url = ?
            ORDER BY timestamp DESC
        """
        params = [profile_url]
        
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def get_creator_analytics(profile_url):
    """
    Computes summary analytics for a creator's profile comments.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Creator details
    cursor.execute("SELECT creator_name, platform, safety_score, last_scanned FROM creators WHERE profile_url = ?", (profile_url,))
    creator = cursor.fetchone()
    if not creator:
        conn.close()
        return None
        
    # Classification counts
    cursor.execute("""
        SELECT classification, COUNT(*) as count
        FROM comments
        WHERE profile_url = ?
        GROUP BY classification
    """, (profile_url,))
    class_counts = {row["classification"]: row["count"] for row in cursor.fetchall()}
    
    # Fill in missing classifications with 0
    categories = ["Proper", "Toxic", "Abusive", "Harmful", "Spam"]
    for cat in categories:
        if cat not in class_counts:
            class_counts[cat] = 0
            
    # Total comments
    cursor.execute("SELECT COUNT(*) FROM comments WHERE profile_url = ?", (profile_url,))
    total_comments = cursor.fetchone()[0]
    
    # Top abusive users (users with most non-Proper comments)
    abusive_users_query = """
        SELECT author, COUNT(*) as violations_count
        FROM comments
        WHERE profile_url = ? AND classification != 'Proper'
        GROUP BY author
        ORDER BY violations_count DESC
        LIMIT 5
    """
    df_abusive_users = pd.read_sql_query(abusive_users_query, conn, params=(profile_url,))
    
    # Fetch recent timeline (grouped by classification and timestamp if timestamps are dates)
    # We can fetch the raw comments DataFrame for charting in streamlit
    conn.close()
    
    return {
        "creator_name": creator["creator_name"],
        "platform": creator["platform"],
        "safety_score": creator["safety_score"],
        "last_scanned": creator["last_scanned"],
        "total_comments": total_comments,
        "class_counts": class_counts,
        "top_abusive_users": df_abusive_users
    }

def delete_creator(profile_url):
    """Deletes a creator and all associated comment records."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM creators WHERE profile_url = ?", (profile_url,))
    cursor.execute("DELETE FROM comments WHERE profile_url = ?", (profile_url,))
    conn.commit()
    conn.close()

def reset_db():
    """Resets the entire database by deleting and rebuilding it."""
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
        except Exception:
            # If database is locked, drop tables instead
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS comments")
            cursor.execute("DROP TABLE IF EXISTS creators")
            conn.commit()
            conn.close()
            return
            
    init_db()
