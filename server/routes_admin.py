"""
LEAKCHECK Server — Admin Routes
Blueprint: /admin/*
"""

import os
import json
import hashlib
import time
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from config import CONFIG, UPDATES_DIR, UPDATE_META, SHARED_DIR
from auth import require_admin_key, generate_key, revoke_key, list_all_keys
from database import get_db_stats, insert_leak_data, vacuum_db
from logger import log_activity, log_upload, get_recent_activity, get_recent_uploads

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ── Dashboard ────────────────────────────────

@admin_bp.route("/dashboard", methods=["GET"])
@require_admin_key
def dashboard():
    """Full admin dashboard data."""
    stats = get_db_stats()
    keys = list_all_keys()
    active_keys = sum(1 for v in keys.values() if v.get("active"))
    recent_activity = get_recent_activity(50)
    recent_uploads = get_recent_uploads(20)

    return jsonify({
        "status": "ok",
        "db": stats,
        "keys": {"total": len(keys), "active": active_keys},
        "recent_activity": recent_activity,
        "recent_uploads": recent_uploads,
    })


# ── Key Management ───────────────────────────

@admin_bp.route("/genkey", methods=["POST"])
@require_admin_key
def gen_key():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    if not username:
        return jsonify({"status": "error", "message": "username is required."}), 400
    plan = data.get("plan", "1_month").strip()

    key = generate_key(username, plan)
    log_activity(CONFIG["admin_key"], "genkey", f"user={username} plan={plan}", request.remote_addr)
    return jsonify({"status": "ok", "username": username, "plan": plan, "api_key": key})


@admin_bp.route("/keys", methods=["GET"])
@require_admin_key
def keys_list():
    keys = list_all_keys()
    return jsonify({"status": "ok", "keys": keys, "total": len(keys)})


@admin_bp.route("/revokekey", methods=["POST"])
@require_admin_key
def revoke():
    data = request.get_json(silent=True) or {}
    target = data.get("api_key", "").strip()
    if not target:
        return jsonify({"status": "error", "message": "api_key is required."}), 400
    if not revoke_key(target):
        return jsonify({"status": "error", "message": "Key not found."}), 404
    log_activity(CONFIG["admin_key"], "revokekey", f"key={target[:12]}...", request.remote_addr)
    return jsonify({"status": "ok", "message": "Key revoked."})


# ── Import (admin only) ─────────────────────

@admin_bp.route("/import", methods=["POST"])
@require_admin_key
def import_hashes():
    """
    Bulk-import email:password combos.
    Body: { "combos": ["email:password", ...], "filename": "optional.txt" }
    """
    data = request.get_json(silent=True) or {}
    combos = data.get("combos", [])
    filename = data.get("filename", "admin_import")

    if not combos:
        return jsonify({"status": "error", "message": "No combos provided."}), 400

    t0 = time.time()
    inserted = insert_leak_data(combos)
    elapsed_ms = round((time.time() - t0) * 1000, 1)

    log_activity(CONFIG["admin_key"], "import",
                 f"file={filename} total={len(combos)} inserted={inserted}",
                 request.remote_addr, elapsed_ms)
    log_upload(CONFIG["admin_key"], filename, len(combos), inserted, request.remote_addr)

    return jsonify({"status": "ok", "imported": inserted,
                    "total_sent": len(combos), "elapsed_ms": elapsed_ms})


# ── Maintain ─────────────────────────────────

@admin_bp.route("/maintain", methods=["POST"])
@require_admin_key
def maintain():
    t0 = time.time()
    vacuum_db()
    elapsed_ms = round((time.time() - t0) * 1000, 1)
    log_activity(CONFIG["admin_key"], "maintain", f"vacuum",
                 request.remote_addr, elapsed_ms)
    return jsonify({"status": "ok", "message": "VACUUM complete", "elapsed_ms": elapsed_ms})


# ── Activity Logs ────────────────────────────

@admin_bp.route("/logs", methods=["GET"])
@require_admin_key
def logs():
    limit = request.args.get("limit", 100, type=int)
    return jsonify({"status": "ok", "logs": get_recent_activity(limit)})


@admin_bp.route("/uploads", methods=["GET"])
@require_admin_key
def uploads():
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"status": "ok", "uploads": get_recent_uploads(limit)})


# ── Push Update ──────────────────────────────

@admin_bp.route("/push_update", methods=["POST"])
@require_admin_key
def push_update():
    """
    Upload a new client version.
    multipart/form-data: file, version, changelog (optional)
    """
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file. Use field 'file'."}), 400
    version = request.form.get("version", "").strip()
    if not version:
        return jsonify({"status": "error", "message": "'version' required."}), 400

    changelog = request.form.get("changelog", "")
    uploaded = request.files["file"]
    filename = uploaded.filename or "leakcheck.py"

    os.makedirs(UPDATES_DIR, exist_ok=True)
    save_path = os.path.join(UPDATES_DIR, filename)
    uploaded.save(save_path)

    sha = hashlib.sha256()
    with open(save_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)

    meta = {
        "version": version,
        "filename": filename,
        "sha256": sha.hexdigest(),
        "changelog": changelog,
        "date": datetime.now(timezone.utc).isoformat(),
    }
    with open(UPDATE_META, "w") as f:
        json.dump(meta, f, indent=4)

    log_activity(CONFIG["admin_key"], "push_update", f"v{version} file={filename}", request.remote_addr)
    return jsonify({"status": "ok", "update": meta})


# ── Shared Files (Private Combos) ────────────

@admin_bp.route("/shared_files", methods=["GET"])
@require_admin_key
def shared_files_list():
    """List all files in the shared/ directory."""
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
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })
    return jsonify({"status": "ok", "files": files, "total": len(files)})


@admin_bp.route("/upload_file", methods=["POST"])
@require_admin_key
def upload_shared_file():
    """
    Upload a combo file to the shared/ directory for client downloads.
    multipart/form-data: file
    """
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file. Use field 'file'."}), 400

    uploaded = request.files["file"]
    filename = uploaded.filename or "combo.txt"
    # Sanitise
    filename = os.path.basename(filename)

    os.makedirs(SHARED_DIR, exist_ok=True)
    save_path = os.path.join(SHARED_DIR, filename)
    uploaded.save(save_path)

    size_mb = round(os.path.getsize(save_path) / (1024 * 1024), 2)
    log_activity(CONFIG["admin_key"], "upload_shared",
                 f"file={filename} size={size_mb}MB", request.remote_addr)

    return jsonify({"status": "ok", "filename": filename, "size_mb": size_mb})


@admin_bp.route("/delete_file", methods=["POST"])
@require_admin_key
def delete_shared_file():
    """Delete a file from the shared/ directory."""
    data = request.get_json(silent=True) or {}
    filename = data.get("filename", "").strip()
    if not filename:
        return jsonify({"status": "error", "message": "'filename' is required."}), 400

    safe_name = os.path.basename(filename)
    fpath = os.path.join(SHARED_DIR, safe_name)

    if not os.path.isfile(fpath):
        return jsonify({"status": "error", "message": "File not found."}), 404

    os.remove(fpath)
    log_activity(CONFIG["admin_key"], "delete_shared",
                 f"file={safe_name}", request.remote_addr)

    return jsonify({"status": "ok", "message": f"Deleted {safe_name}"})
