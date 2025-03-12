import sqlite3
from typing import List, Tuple, Optional
from config import DB_FILE

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_message(session_id: str, role: str, message: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO conversation_history (session_id, role, message) VALUES (?, ?, ?)",
        (session_id, role, message)
    )
    conn.commit()
    conn.close()

def load_conversation(session_id: str) -> List[dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, message FROM conversation_history WHERE session_id = ? ORDER BY timestamp",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"role": row["role"], "content": row["message"]} for row in rows]

def list_sessions(cursor_value: Optional[str], limit: int) -> Tuple[List[dict], Optional[str]]:
    conn = get_db_connection()
    cur = conn.cursor()
    params = []
    query = """
        SELECT session_id, MAX(timestamp) as last_updated
        FROM conversation_history
        GROUP BY session_id
    """
    if cursor_value:
        query += " HAVING last_updated < ?"
        params.append(cursor_value)
    query += " ORDER BY last_updated DESC LIMIT ?"
    params.append(limit)
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    sessions = [{"session_id": row["session_id"], "last_updated": row["last_updated"]} for row in rows]
    next_cursor = sessions[-1]["last_updated"] if len(sessions) == limit else None
    return sessions, next_cursor
