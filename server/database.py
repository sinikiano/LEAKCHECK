"""
LEAKCHECK Server — SQLite Database Layer
Stores email:password pairs in a WAL-mode SQLite database.

Schema:
  • leak_data(email TEXT NOCASE, password TEXT, UNIQUE(email,password))
  • Indexed on email and (email,password) for fast lookups
"""

import os
import sqlite3
import threading
import time
from config import CONFIG

_DB_LOCK = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    """Return a new SQLite connection with optimised PRAGMAs."""
    conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA mmap_size=2147483648")    # 2 GB memory-mapped I/O
    conn.execute("PRAGMA cache_size=-131072")       # 128 MB page cache
    conn.execute("PRAGMA temp_store=MEMORY")        # temp tables in RAM
    conn.execute("PRAGMA busy_timeout=10000")       # 10 s retry on lock
    return conn


def _fresh_conn() -> sqlite3.Connection:
    """Alias kept for clarity — identical to _get_conn()."""
    return _get_conn()


def init_db():
    """Create tables and indexes if they don't exist."""
    conn = _get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS leak_data (
                email     TEXT NOT NULL COLLATE NOCASE,
                password  TEXT NOT NULL,
                UNIQUE(email, password)
            );
            CREATE INDEX IF NOT EXISTS idx_leak_email ON leak_data(email COLLATE NOCASE);
            CREATE INDEX IF NOT EXISTS idx_leak_email_pass ON leak_data(email COLLATE NOCASE, password);

            CREATE TABLE IF NOT EXISTS search_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_key  TEXT NOT NULL,
                email     TEXT NOT NULL,
                results   INTEGER NOT NULL DEFAULT 0,
                timestamp REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_search_day ON search_log(user_key, timestamp);

            CREATE TABLE IF NOT EXISTS activity_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   REAL    NOT NULL,
                user_key    TEXT    NOT NULL,
                action      TEXT    NOT NULL,
                detail      TEXT,
                ip          TEXT,
                duration_ms REAL
            );
            CREATE INDEX IF NOT EXISTS idx_activity_ts ON activity_log(timestamp);
            CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_log(user_key);

            CREATE TABLE IF NOT EXISTS upload_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   REAL    NOT NULL,
                user_key    TEXT    NOT NULL,
                filename    TEXT,
                record_count INTEGER,
                new_count   INTEGER,
                ip          TEXT
            );
        """)
        conn.commit()
    finally:
        conn.close()


def get_db_stats() -> dict:
    """Return database statistics."""
    conn = _get_conn()
    try:
        cur = conn.cursor()

        # Fast approximate count via MAX(rowid) — avoids full table scan on large DBs
        try:
            cur.execute("SELECT MAX(rowid) FROM leak_data")
            row = cur.fetchone()
            total = row[0] if row and row[0] else 0
        except Exception:
            total = 0

        # Use upload_log for last-update timestamp (added column removed)
        cur.execute("SELECT MAX(timestamp) FROM upload_log")
        last_update = cur.fetchone()[0]

        db_size = os.path.getsize(CONFIG["db_path"]) if os.path.isfile(CONFIG["db_path"]) else 0

        cur.execute("SELECT COUNT(DISTINCT user_key) FROM activity_log WHERE timestamp > ?",
                    (time.time() - 86400,))
        active_users_24h = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM activity_log WHERE action='check' AND timestamp > ?",
                    (time.time() - 3600,))
        queries_1h = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM activity_log WHERE action='check' AND timestamp > ?",
                    (time.time() - 86400,))
        queries_24h = cur.fetchone()[0]

    finally:
        conn.close()
    return {
        "total_records": total,
        "leak_data_count": total,
        "db_size_bytes": db_size,
        "db_size_mb": round(db_size / (1024 * 1024), 2),
        "last_update": last_update,
        "active_users_24h": active_users_24h,
        "queries_1h": queries_1h,
        "queries_24h": queries_24h,
    }


def vacuum_db() -> None:
    """
    Maintenance: VACUUM the database to reclaim unused space.
    """
    conn = _get_conn()
    try:
        conn.execute("VACUUM")
        conn.commit()
    finally:
        conn.close()


# ── Email search (leak_data) ─────────────────

def _parse_combo_lines(combo_lines: list[str]) -> list[tuple[str, str]]:
    """Parse raw 'email:password' strings into (email, password) tuples."""
    pairs = []
    for line in combo_lines:
        line = line.strip()
        if not line:
            continue
        idx = line.find(":")
        if idx < 1:
            continue
        email = line[:idx].strip().lower()
        password = line[idx + 1:].strip()
        if email and password:
            pairs.append((email, password))
    return pairs


def insert_leak_data(combo_lines: list[str]) -> int:
    """
    Bulk-insert email:password pairs into leak_data.
    Expects raw 'email:password' strings. Skips duplicates.
    Returns count of newly inserted.

    Performance: uses a dedicated connection with relaxed durability
    settings during the bulk insert, then restores normal sync.
    """
    pairs = _parse_combo_lines(combo_lines)
    if not pairs:
        return 0

    conn = _fresh_conn()          # dedicated connection for bulk work
    try:
        with _DB_LOCK:
            conn.execute("PRAGMA synchronous=OFF")     # fastest writes
            conn.execute("PRAGMA locking_mode=EXCLUSIVE")  # avoid WAL lock churn
            before = conn.total_changes
            conn.execute("BEGIN")
            conn.executemany(
                "INSERT OR IGNORE INTO leak_data (email, password) VALUES (?, ?)",
                pairs,
            )
            conn.execute("COMMIT")
            new_count = conn.total_changes - before
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA locking_mode=NORMAL")
    finally:
        conn.close()
    return new_count


def insert_leak_data_iter(line_iter, batch_size: int = 50_000,
                          progress_cb=None) -> int:
    """
    Streaming bulk-insert from an iterator of raw lines.
    Inserts in large batches inside a single connection for maximum throughput.
    progress_cb(inserted_so_far, parsed_so_far) is called after each batch.
    Returns total newly-inserted count.
    """
    conn = _fresh_conn()
    total_inserted = 0
    total_parsed = 0
    batch: list[tuple[str, str]] = []

    try:
        conn.execute("PRAGMA synchronous=OFF")
        conn.execute("PRAGMA locking_mode=EXCLUSIVE")

        for raw_line in line_iter:
            line = raw_line.strip()
            if not line:
                continue
            idx = line.find(":")
            if idx < 1:
                continue
            email = line[:idx].strip().lower()
            password = line[idx + 1:].strip()
            if email and password:
                batch.append((email, password))

            if len(batch) >= batch_size:
                with _DB_LOCK:
                    before = conn.total_changes
                    conn.execute("BEGIN")
                    conn.executemany(
                        "INSERT OR IGNORE INTO leak_data (email, password) VALUES (?, ?)",
                        batch,
                    )
                    conn.execute("COMMIT")
                    total_inserted += conn.total_changes - before
                total_parsed += len(batch)
                batch.clear()
                if progress_cb:
                    progress_cb(total_inserted, total_parsed)

        # flush remainder
        if batch:
            with _DB_LOCK:
                before = conn.total_changes
                conn.execute("BEGIN")
                conn.executemany(
                    "INSERT OR IGNORE INTO leak_data (email, password) VALUES (?, ?)",
                    batch,
                )
                conn.execute("COMMIT")
                total_inserted += conn.total_changes - before
            total_parsed += len(batch)
            if progress_cb:
                progress_cb(total_inserted, total_parsed)

        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA locking_mode=NORMAL")
    finally:
        conn.close()
    return total_inserted


def search_by_email(email: str, limit: int = 200) -> list[dict]:
    """
    Search leak_data for all entries matching an email (case-insensitive).
    Returns list of {email, password} dicts.
    """
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT email, password FROM leak_data WHERE email = ? COLLATE NOCASE LIMIT ?",
            (email.strip().lower(), limit),
        )
        results = [{"email": row[0], "password": row[1]} for row in cur.fetchall()]
    finally:
        conn.close()
    return results


def check_combos_bulk(combos: list[str]) -> list[str]:
    """
    Check a batch of raw 'email:password' combos against leak_data.
    Returns list of combos that were NOT found in the database (private).

    Performance: loads all candidates into a temp table, then does a
    single indexed JOIN to find matches — O(n log n) instead of O(n²).
    """
    if not combos:
        return []

    # Parse combos into (email, password) pairs
    pairs: dict[tuple[str, str], str] = {}
    for line in combos:
        line = line.strip()
        if not line:
            continue
        idx = line.find(":")
        if idx < 1:
            continue
        email = line[:idx].strip().lower()
        password = line[idx + 1:].strip()
        if email and password:
            pairs[(email, password)] = line  # map normalised → original

    if not pairs:
        return []

    conn = _get_conn()
    cur = conn.cursor()
    found_keys: set[tuple[str, str]] = set()

    try:
        # Create in-memory temp table and bulk-load candidates
        cur.execute("CREATE TEMP TABLE IF NOT EXISTS _check_batch "
                    "(email TEXT COLLATE NOCASE, password TEXT)")
        cur.execute("DELETE FROM _check_batch")
        cur.executemany("INSERT INTO _check_batch VALUES (?, ?)", pairs.keys())

        # Single JOIN: find all matches at once using the composite index
        cur.execute(
            "SELECT b.email, b.password FROM _check_batch b "
            "INNER JOIN leak_data d ON d.email = b.email COLLATE NOCASE "
            "AND d.password = b.password"
        )
        for row in cur.fetchall():
            found_keys.add((row[0].lower(), row[1]))

        cur.execute("DELETE FROM _check_batch")  # tidy up
    except Exception:
        # Fallback: if temp-table approach fails, use batched OR (old method)
        items = list(pairs.keys())
        sub_batch = 500
        for i in range(0, len(items), sub_batch):
            batch = items[i:i + sub_batch]
            clauses = " OR ".join(
                ["(email = ? COLLATE NOCASE AND password = ?)"] * len(batch))
            params: list[str] = []
            for em, pw in batch:
                params.extend([em, pw])
            cur.execute(
                f"SELECT email, password FROM leak_data WHERE {clauses}",
                params,
            )
            for row in cur.fetchall():
                found_keys.add((row[0].lower(), row[1]))

    # Return combos NOT found in DB
    not_found = []
    for key, original in pairs.items():
        if key not in found_keys:
            not_found.append(original)
    return not_found


def get_search_count_today(user_key: str) -> int:
    """Return how many email searches this key has made today (UTC)."""
    import calendar
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    # Start of today UTC
    start_of_day = calendar.timegm(now.replace(hour=0, minute=0, second=0, microsecond=0).timetuple())

    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM search_log WHERE user_key = ? AND timestamp >= ?",
            (user_key, float(start_of_day)),
        )
        count = cur.fetchone()[0]
    finally:
        conn.close()
    return count


def log_search(user_key: str, email: str, result_count: int):
    """Log an email search for rate-limiting."""
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO search_log (user_key, email, results, timestamp) VALUES (?, ?, ?, ?)",
            (user_key, email.lower(), result_count, time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def get_leak_data_count() -> int:
    """Return approximate row count of leak_data (fast, no full scan)."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT MAX(rowid) FROM leak_data")
        row = cur.fetchone()
        count = row[0] if row and row[0] else 0
    finally:
        conn.close()
    return count


# ── User Stats ───────────────────────────────

def get_user_stats(user_key: str) -> dict | None:
    """Return personal usage stats for the given API key."""
    conn = _get_conn()
    try:
        cur = conn.cursor()

        # Total check operations
        cur.execute("SELECT COUNT(*) FROM activity_log WHERE user_key = ? AND action = 'check'",
                    (user_key,))
        total_checks = cur.fetchone()[0]

        # Total combos checked (sum from detail field: "total=NNNN")
        cur.execute(
            "SELECT detail FROM activity_log WHERE user_key = ? AND action = 'check'",
            (user_key,))
        total_combos = 0
        for (detail,) in cur.fetchall():
            if detail:
                import re
                m = re.search(r'total=(\d+)', detail)
                if m:
                    total_combos += int(m.group(1))

        # Total searches ever
        cur.execute("SELECT COUNT(*) FROM search_log WHERE user_key = ?", (user_key,))
        total_searches = cur.fetchone()[0]

        # Searches today
        import calendar
        from datetime import datetime, timezone as tz
        now = datetime.now(tz.utc)
        start_of_day = calendar.timegm(
            now.replace(hour=0, minute=0, second=0, microsecond=0).timetuple())
        cur.execute("SELECT COUNT(*) FROM search_log WHERE user_key = ? AND timestamp >= ?",
                    (user_key, float(start_of_day)))
        searches_today = cur.fetchone()[0]

        # Files downloaded
        cur.execute(
            "SELECT COUNT(*) FROM activity_log WHERE user_key = ? AND action = 'download_file'",
            (user_key,))
        files_downloaded = cur.fetchone()[0]

        # Account age (from first activity)
        cur.execute(
            "SELECT MIN(timestamp) FROM activity_log WHERE user_key = ?",
            (user_key,))
        first_ts = cur.fetchone()[0]
        if first_ts:
            account_age_days = int((time.time() - first_ts) / 86400)
        else:
            account_age_days = 0

        # Last active
        cur.execute(
            "SELECT MAX(timestamp) FROM activity_log WHERE user_key = ?",
            (user_key,))
        last_ts = cur.fetchone()[0]
        if last_ts:
            from datetime import datetime as dt
            last_active = dt.fromtimestamp(last_ts).strftime("%Y-%m-%d %H:%M:%S")
        else:
            last_active = "Never"

    finally:
        conn.close()

    return {
        "total_checks": total_checks,
        "total_combos_checked": total_combos,
        "total_searches": total_searches,
        "searches_today": searches_today,
        "files_downloaded": files_downloaded,
        "account_age_days": account_age_days,
        "last_active": last_active,
    }


# ── Referral Tracking ────────────────────────

def init_referral_table():
    """Create referral tracking table if it doesn't exist."""
    conn = _get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS referrals (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_key  TEXT NOT NULL,
                referred_key  TEXT NOT NULL,
                bonus_days    INTEGER NOT NULL DEFAULT 0,
                created_at    REAL NOT NULL,
                UNIQUE(referred_key)
            );
            CREATE INDEX IF NOT EXISTS idx_referral_referrer ON referrals(referrer_key);
        """)
        conn.commit()
    finally:
        conn.close()


def log_referral(referrer_key: str, referred_key: str, bonus_days: int):
    """Log a referral and the bonus days awarded."""
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO referrals (referrer_key, referred_key, bonus_days, created_at) "
            "VALUES (?, ?, ?, ?)",
            (referrer_key, referred_key, bonus_days, time.time()))
        conn.commit()
    finally:
        conn.close()


def get_referral_stats(user_key: str) -> dict:
    """Get referral stats for a user key."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*), COALESCE(SUM(bonus_days), 0) FROM referrals WHERE referrer_key = ?",
                    (user_key,))
        count, total_bonus = cur.fetchone()
    finally:
        conn.close()
    return {"referral_count": count, "total_bonus_days": total_bonus}


def is_already_referred(user_key: str) -> bool:
    """Check if a user key was already referred by someone."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM referrals WHERE referred_key = ?", (user_key,))
        return cur.fetchone()[0] > 0
    finally:
        conn.close()


def list_all_referrals(limit: int = 200) -> list[dict]:
    """List all referrals for admin panel."""
    conn = _get_conn()
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM referrals ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_per_user_summary() -> list[dict]:
    """
    Return aggregate stats per user_key: total checks, total combos,
    total searches, last active timestamp.
    """
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT user_key,
                   COUNT(*) as total_actions,
                   SUM(CASE WHEN action='check' THEN 1 ELSE 0 END) as checks,
                   SUM(CASE WHEN action='search' OR action='search_tg' THEN 1 ELSE 0 END) as searches,
                   SUM(CASE WHEN action='download_file' THEN 1 ELSE 0 END) as downloads,
                   MAX(timestamp) as last_active
            FROM activity_log
            GROUP BY user_key
            ORDER BY last_active DESC
            LIMIT 500
        """)
        rows = cur.fetchall()
        return [
            {
                "user_key": r[0],
                "total_actions": r[1],
                "checks": r[2],
                "searches": r[3],
                "downloads": r[4],
                "last_active": r[5],
            }
            for r in rows
        ]
    finally:
        conn.close()


# ── Database Size Analysis & Optimization ─────

def get_table_sizes() -> list[dict]:
    """
    Return per-table size estimates.
    Tries the dbstat virtual table first (accurate page counts).
    Falls back to row-count-based estimation if dbstat is unavailable.
    """
    conn = _get_conn()
    try:
        cur = conn.cursor()
        page_size = cur.execute("PRAGMA page_size").fetchone()[0]
        total_pages = cur.execute("PRAGMA page_count").fetchone()[0]
        free_pages = cur.execute("PRAGMA freelist_count").fetchone()[0]
        used_pages = total_pages - free_pages

        # Check if dbstat is available
        has_dbstat = False
        try:
            cur.execute("SELECT 1 FROM dbstat LIMIT 1")
            has_dbstat = True
        except Exception:
            pass

        tables = [r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()]

        result = []
        total_row_weighted = 0  # for fallback estimation
        table_rows = {}

        for tbl in tables:
            try:
                row_count = cur.execute(f"SELECT COUNT(*) FROM [{tbl}]").fetchone()[0]
            except Exception:
                row_count = 0
            table_rows[tbl] = row_count

            if has_dbstat:
                try:
                    page_count = cur.execute(
                        "SELECT COUNT(DISTINCT pageno) FROM dbstat WHERE name = ?",
                        (tbl,)
                    ).fetchone()[0] or 0
                except Exception:
                    page_count = 0
            else:
                page_count = 0  # will estimate below

            result.append({
                "name": tbl,
                "row_count": row_count,
                "page_count": page_count,
                "size_bytes": page_count * page_size,
                "size_mb": round(page_count * page_size / (1024 * 1024), 2),
            })

        # If dbstat not available, estimate sizes proportionally from row counts
        if not has_dbstat:
            # Weight by estimated row size (larger tables like leak_data have 2 text cols)
            row_weights = {}
            for tbl in tables:
                rc = table_rows.get(tbl, 0)
                # Estimate avg row size — leak_data ~60 bytes, logs ~100 bytes
                if tbl == "leak_data":
                    row_weights[tbl] = rc * 60
                else:
                    row_weights[tbl] = rc * 100
            total_weight = sum(row_weights.values()) or 1

            for entry in result:
                tbl = entry["name"]
                weight = row_weights.get(tbl, 0)
                est_pages = int(used_pages * weight / total_weight)
                entry["page_count"] = est_pages
                entry["size_bytes"] = est_pages * page_size
                entry["size_mb"] = round(est_pages * page_size / (1024 * 1024), 2)

        # Also account for indexes
        indexes = cur.execute(
            "SELECT name, tbl_name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        for idx_name, tbl_name in indexes:
            if has_dbstat:
                try:
                    idx_pages = cur.execute(
                        "SELECT COUNT(DISTINCT pageno) FROM dbstat WHERE name = ?",
                        (idx_name,)
                    ).fetchone()[0] or 0
                    if idx_pages > 0:
                        result.append({
                            "name": f"  \u21b3 index: {idx_name}",
                            "row_count": 0,
                            "page_count": idx_pages,
                            "size_bytes": idx_pages * page_size,
                            "size_mb": round(idx_pages * page_size / (1024 * 1024), 2),
                        })
                except Exception:
                    pass

        # Sort descending by size
        result.sort(key=lambda x: x["size_bytes"], reverse=True)
    finally:
        conn.close()
    return result


def purge_old_logs(days: int = 30) -> dict:
    """
    Delete activity_log, search_log, and upload_log entries older than `days`.
    Returns dict with counts deleted per table.
    """
    cutoff = time.time() - (days * 86400)
    conn = _get_conn()
    deleted = {}
    try:
        with _DB_LOCK:
            cur = conn.cursor()
            for table in ("activity_log", "search_log", "upload_log"):
                cur.execute(f"SELECT COUNT(*) FROM [{table}] WHERE timestamp < ?", (cutoff,))
                count = cur.fetchone()[0]
                cur.execute(f"DELETE FROM [{table}] WHERE timestamp < ?", (cutoff,))
                deleted[table] = count
            conn.commit()
    finally:
        conn.close()
    return deleted


def optimize_db() -> dict:
    """
    Full database optimization:
      1. Purge logs older than 30 days
      2. Analyze (updates query planner statistics)
      3. Incremental vacuum / full VACUUM
    Returns summary dict.
    """
    conn = _get_conn()
    try:
        db_path = CONFIG["db_path"]
        size_before = os.path.getsize(db_path) if os.path.isfile(db_path) else 0

        # 1. Purge old logs
        log_deleted = purge_old_logs(30)

        # 2. Re-analyze for optimal query plans
        conn.execute("ANALYZE")
        conn.commit()

        # 3. VACUUM to reclaim free pages and defragment
        conn.execute("VACUUM")
        conn.commit()

        size_after = os.path.getsize(db_path) if os.path.isfile(db_path) else 0
    finally:
        conn.close()

    return {
        "size_before_mb": round(size_before / (1024 * 1024), 2),
        "size_after_mb": round(size_after / (1024 * 1024), 2),
        "saved_mb": round((size_before - size_after) / (1024 * 1024), 2),
        "logs_purged": log_deleted,
    }


def rebuild_indexes() -> int:
    """
    Drop and recreate all secondary indexes to reclaim fragmented space.
    Returns count of indexes rebuilt.
    """
    conn = _get_conn()
    try:
        cur = conn.cursor()
        # Collect non-autoindex indexes
        indexes = cur.execute("""
            SELECT name, sql FROM sqlite_master
            WHERE type='index' AND sql IS NOT NULL
        """).fetchall()

        count = 0
        with _DB_LOCK:
            for idx_name, idx_sql in indexes:
                cur.execute(f"DROP INDEX IF EXISTS [{idx_name}]")
                cur.execute(idx_sql)
                count += 1
            conn.commit()

        # ANALYZE after rebuild
        conn.execute("ANALYZE")
        conn.commit()
    finally:
        conn.close()
    return count


def repack_db_larger_pages(new_page_size: int = 8192) -> dict:
    """
    Rebuild the database with a larger page size.
    Larger pages (8192 or 16384 vs default 4096) reduce B-tree overhead
    and can shrink BLOB-heavy databases by 5-15%.
    Returns dict with sizes before/after.
    """
    db_path = CONFIG["db_path"]
    size_before = os.path.getsize(db_path) if os.path.isfile(db_path) else 0

    conn = _get_conn()
    try:
        current_ps = conn.execute("PRAGMA page_size").fetchone()[0]
        if current_ps >= new_page_size:
            conn.close()
            return {
                "status": "skipped",
                "reason": f"Current page size ({current_ps}) >= requested ({new_page_size})",
                "size_before_mb": round(size_before / (1024 * 1024), 2),
                "size_after_mb": round(size_before / (1024 * 1024), 2),
                "saved_mb": 0,
            }
        conn.execute(f"PRAGMA page_size = {new_page_size}")
        conn.execute("VACUUM")
        conn.commit()
        size_after = os.path.getsize(db_path) if os.path.isfile(db_path) else 0
    finally:
        conn.close()

    return {
        "status": "ok",
        "old_page_size": current_ps,
        "new_page_size": new_page_size,
        "size_before_mb": round(size_before / (1024 * 1024), 2),
        "size_after_mb": round(size_after / (1024 * 1024), 2),
        "saved_mb": round((size_before - size_after) / (1024 * 1024), 2),
    }
