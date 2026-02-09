"""
LEAKCHECK Server — User API Routes
Blueprint: /api/*
"""

import re
import time
import os
import json
from flask import Blueprint, request, jsonify, send_file
from config import CONFIG, SHARED_DIR, MESSAGES_FILE, UPDATES_DIR, UPDATE_META
from auth import require_user_key, get_key_info
from database import (get_db_stats, search_by_email, get_search_count_today,
                      log_search, get_user_stats, get_referral_stats,
                      check_combos_bulk)
from logger import log_activity

api_bp = Blueprint("api", __name__, url_prefix="/api")


# ── Public ───────────────────────────────────

SERVER_VERSION = "2.3.0"

@api_bp.route("/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok", "version": SERVER_VERSION})


@api_bp.route("/messages", methods=["GET"])
def messages():
    """Return server messages / news for clients (public)."""
    if not os.path.isfile(MESSAGES_FILE):
        return jsonify({"status": "ok", "messages": []})
    try:
        with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
            msgs = json.load(f)
        # Only return active messages
        active = [m for m in msgs if m.get("active", True)]
        return jsonify({"status": "ok", "messages": active})
    except Exception:
        return jsonify({"status": "ok", "messages": []})


@api_bp.route("/version", methods=["GET"])
def version():
    """Return latest client version info (for auto-updater)."""
    if not os.path.isfile(UPDATE_META):
        return jsonify({"status": "ok", "version": "1.0.0", "update_available": False})
    with open(UPDATE_META, "r") as f:
        meta = json.load(f)
    return jsonify({
        "status": "ok",
        "version": meta.get("version", "1.0.0"),
        "sha256": meta.get("sha256", ""),
        "changelog": meta.get("changelog", ""),
        "date": meta.get("date", ""),
        "update_available": True,
    })


@api_bp.route("/download", methods=["GET"])
def download_update():
    """Download latest client file."""
    if not os.path.isfile(UPDATE_META):
        return jsonify({"status": "error", "message": "No update available."}), 404
    with open(UPDATE_META, "r") as f:
        meta = json.load(f)
    filepath = os.path.join(UPDATES_DIR, meta["filename"])
    if not os.path.isfile(filepath):
        return jsonify({"status": "error", "message": "Update file missing."}), 404
    return send_file(filepath, as_attachment=True, download_name=meta["filename"])


# ── Authenticated ────────────────────────────
@api_bp.route("/keyinfo", methods=["GET"])
@require_user_key
def key_info():
    """Return the calling user's key info (plan, expiry, days remaining)."""
    key = request.headers.get("X-API-Key", "")
    info = get_key_info(key)
    if not info:
        # admin key or unknown
        return jsonify({"status": "ok", "plan": "admin", "plan_label": "Admin",
                        "expires_at": "never", "days_remaining": -1, "expired": False, "active": True})
    return jsonify({"status": "ok", **info})



@api_bp.route("/search", methods=["POST"])
@require_user_key
def search_email():
    """
    Search for all leaked passwords linked to an email.
    Rate-limited to 30 searches per day per key.
    Body: { "email": "user@example.com" }
    """
    key = request.headers.get("X-API-Key", "")
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify({"status": "error", "message": "Email is required."}), 400

    # Basic email validation
    if not re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email):
        return jsonify({"status": "error", "message": "Invalid email format."}), 400

    # Rate-limit check
    daily_limit = CONFIG.get("daily_search_limit", 30)
    used = get_search_count_today(key)
    remaining = max(0, daily_limit - used)
    if remaining <= 0:
        resp = jsonify({
            "status": "error",
            "error": "rate_limit",
            "message": f"Daily search limit reached ({daily_limit}/day). Try again tomorrow.",
            "used": used,
            "limit": daily_limit,
            "remaining": 0,
        })
        resp.headers["Retry-After"] = "3600"
        return resp, 429

    t0 = time.time()
    results = search_by_email(email)
    elapsed_ms = round((time.time() - t0) * 1000, 1)

    # Log this search
    log_search(key, email, len(results))
    log_activity(key, "search", f"email={email} results={len(results)}", request.remote_addr, elapsed_ms)

    return jsonify({
        "status": "ok",
        "email": email,
        "results": results,
        "count": len(results),
        "elapsed_ms": elapsed_ms,
        "searches_used": used + 1,
        "searches_remaining": remaining - 1,
        "daily_limit": daily_limit,
    })


@api_bp.route("/search/quota", methods=["GET"])
@require_user_key
def search_quota():
    """Return the user's remaining daily search quota."""
    key = request.headers.get("X-API-Key", "")
    daily_limit = CONFIG.get("daily_search_limit", 30)
    used = get_search_count_today(key)
    return jsonify({
        "status": "ok",
        "used": used,
        "remaining": max(0, daily_limit - used),
        "limit": daily_limit,
    })


@api_bp.route("/status", methods=["GET"])
@require_user_key
def db_status():
    key = request.headers.get("X-API-Key", "")
    t0 = time.time()
    try:
        stats = get_db_stats()
        elapsed = round((time.time() - t0) * 1000, 1)
        log_activity(key, "status", f"db_total={stats['total_records']}", request.remote_addr, elapsed)
        return jsonify({"status": "ok", **stats})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@api_bp.route("/check", methods=["POST"])
@require_user_key
def check_combos():
    """
    Bulk combo-check endpoint.
    Accepts raw email:password combos and checks against leak_data.
    Body: { "combos": ["email:pass", ...] }
    Returns: { "not_found": [...], "total": N, "found": N, "elapsed_ms": N }
    """
    key = request.headers.get("X-API-Key", "")
    data = request.get_json(silent=True) or {}
    combos = data.get("combos", [])

    if not combos or not isinstance(combos, list):
        return jsonify({"status": "error", "message": "No combos provided."}), 400

    t0 = time.time()
    not_found = check_combos_bulk(combos)
    elapsed_ms = round((time.time() - t0) * 1000, 1)

    total = len(combos)
    found = total - len(not_found)

    log_activity(key, "check",
                 f"total={total} found={found} not_found={len(not_found)}",
                 request.remote_addr, elapsed_ms)

    return jsonify({
        "status": "ok",
        "not_found": not_found,
        "total": total,
        "found": found,
        "elapsed_ms": elapsed_ms,
    })


# ── File downloads (private combos) ─────────

@api_bp.route("/files", methods=["GET"])
@require_user_key
def list_files():
    """List all files available for download in the shared/ directory."""
    key = request.headers.get("X-API-Key", "")
    os.makedirs(SHARED_DIR, exist_ok=True)

    files = []
    for fname in sorted(os.listdir(SHARED_DIR)):
        fpath = os.path.join(SHARED_DIR, fname)
        if os.path.isfile(fpath):
            stat = os.stat(fpath)
            size_mb = round(stat.st_size / (1024 * 1024), 2)
            files.append({
                "name": fname,
                "size_bytes": stat.st_size,
                "size_mb": size_mb,
                "modified": time.strftime("%Y-%m-%d %H:%M:%S",
                                          time.localtime(stat.st_mtime)),
            })

    log_activity(key, "list_files", f"count={len(files)}", request.remote_addr)
    return jsonify({"status": "ok", "files": files, "total": len(files)})


@api_bp.route("/files/download/<path:filename>", methods=["GET"])
@require_user_key
def download_shared_file(filename):
    """Download a specific file from the shared/ directory."""
    key = request.headers.get("X-API-Key", "")
    os.makedirs(SHARED_DIR, exist_ok=True)

    # Prevent directory traversal
    safe_name = os.path.basename(filename)
    fpath = os.path.join(SHARED_DIR, safe_name)

    if not os.path.isfile(fpath):
        return jsonify({"status": "error", "message": "File not found."}), 404

    log_activity(key, "download_file", f"file={safe_name}", request.remote_addr)
    return send_file(fpath, as_attachment=True, download_name=safe_name)


# ── User Stats ───────────────────────────────

@api_bp.route("/user/stats", methods=["GET"])
@require_user_key
def user_stats():
    """Return personal usage statistics for the calling user."""
    key = request.headers.get("X-API-Key", "")
    stats = get_user_stats(key)
    if not stats:
        return jsonify({"status": "ok", "total_checks": 0, "total_combos_checked": 0,
                        "total_searches": 0, "searches_today": 0, "files_downloaded": 0,
                        "account_age_days": 0, "last_active": "Never",
                        "referral_count": 0, "referral_bonus_days": 0})

    # Add referral stats
    ref_stats = get_referral_stats(key)
    stats["referral_count"] = ref_stats["referral_count"]
    stats["referral_bonus_days"] = ref_stats["total_bonus_days"]

    return jsonify({"status": "ok", **stats})
