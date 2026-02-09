"""
LEAKCHECK Server — Activity Logger
Logs all user interactions, uploads, and queries to SQLite.
"""

import time
import sqlite3
from config import CONFIG


def _get_conn():
    return sqlite3.connect(CONFIG["db_path"], check_same_thread=False)


def log_activity(user_key: str, action: str, detail: str = "", ip: str = "", duration_ms: float = 0):
    """Log a user action (check, ping, import, etc.)."""
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO activity_log (timestamp, user_key, action, detail, ip, duration_ms) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (time.time(), user_key, action, detail, ip, duration_ms)
        )
        conn.commit()
    finally:
        conn.close()


def log_upload(user_key: str, filename: str, record_count: int, new_count: int, ip: str = ""):
    """Log a combo file upload/import."""
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO upload_log (timestamp, user_key, filename, record_count, new_count, ip) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (time.time(), user_key, filename, record_count, new_count, ip)
        )
        conn.commit()
    finally:
        conn.close()


def get_recent_activity(limit: int = 100) -> list[dict]:
    """Return recent activity logs."""
    conn = _get_conn()
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM activity_log ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
    return rows


def get_recent_uploads(limit: int = 50) -> list[dict]:
    """Return recent upload logs."""
    conn = _get_conn()
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM upload_log ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
    return rows
