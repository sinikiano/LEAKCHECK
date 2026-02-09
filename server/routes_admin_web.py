"""
LEAKCHECK Server — Admin Web Dashboard
Blueprint: /panel/*
Flask-rendered HTML dashboard for remote server management.
"""

import os
import json
import time
import secrets
from functools import wraps
from datetime import datetime, timezone

from flask import (Blueprint, request, redirect, url_for,
                   render_template, session, flash, jsonify, send_file)
from config import CONFIG, BASE_DIR, MESSAGES_FILE, SHARED_DIR, UPDATES_DIR, UPDATE_META
from auth import (generate_key, revoke_key, list_all_keys, reset_hwid,
                  get_key_info, PLANS)
import hashlib
from database import (get_db_stats, init_referral_table, optimize_db,
                      vacuum_db, get_table_sizes, rebuild_indexes,
                      purge_old_logs, list_all_referrals, get_per_user_summary,
                      insert_leak_data_iter)
from logger import get_recent_activity, get_recent_uploads
from binance_pay import list_all_orders, fulfill_order, cancel_order

admin_web_bp = Blueprint(
    "admin_web", __name__,
    url_prefix="/panel",
    template_folder=os.path.join(BASE_DIR, "templates"),
)


# ──────────────────────────────────────────────
#  Session-based Authentication
# ──────────────────────────────────────────────

def _login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_authed"):
            return redirect(url_for("admin_web.login"))
        return fn(*args, **kwargs)
    return wrapper


@admin_web_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        key = request.form.get("admin_key", "").strip()
        if key == CONFIG["admin_key"]:
            session["admin_authed"] = True
            session.permanent = True
            return redirect(url_for("admin_web.dashboard"))
        flash("Invalid admin key.", "error")
    return render_template("login.html")


@admin_web_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin_web.login"))


# ──────────────────────────────────────────────
#  Dashboard
# ──────────────────────────────────────────────

@admin_web_bp.route("/")
@_login_required
def dashboard():
    stats = get_db_stats()
    keys = list_all_keys()
    active_count = sum(1 for v in keys.values() if v.get("active"))
    orders = list_all_orders()
    pending_orders = sum(1 for o in orders.values() if o.get("status") == "pending")
    paid_orders = sum(1 for o in orders.values() if o.get("status") == "paid")
    total_revenue = sum(
        float(o.get("amount", 0)) for o in orders.values() if o.get("status") == "paid"
    )
    activity = get_recent_activity(20)
    uploads = get_recent_uploads(10)
    referrals = list_all_referrals(10)

    return render_template("dashboard.html",
        stats=stats,
        total_keys=len(keys),
        active_keys=active_count,
        pending_orders=pending_orders,
        paid_orders=paid_orders,
        total_orders=len(orders),
        total_revenue=round(total_revenue, 2),
        activity=activity,
        uploads=uploads,
        referrals=referrals,
    )


# ──────────────────────────────────────────────
#  Key Management
# ──────────────────────────────────────────────

@admin_web_bp.route("/keys")
@_login_required
def keys_page():
    keys = list_all_keys()
    return render_template("keys.html", keys=keys, plans=PLANS)


@admin_web_bp.route("/keys/generate", methods=["POST"])
@_login_required
def keys_generate():
    username = request.form.get("username", "").strip()
    plan = request.form.get("plan", "1_month")
    if not username:
        flash("Username is required.", "error")
        return redirect(url_for("admin_web.keys_page"))
    key = generate_key(username, plan)
    flash(f"Key generated for {username}: {key}", "success")
    return redirect(url_for("admin_web.keys_page"))


@admin_web_bp.route("/keys/revoke", methods=["POST"])
@_login_required
def keys_revoke():
    target = request.form.get("api_key", "").strip()
    if revoke_key(target):
        flash("Key revoked.", "success")
    else:
        flash("Key not found.", "error")
    return redirect(url_for("admin_web.keys_page"))


@admin_web_bp.route("/keys/reset-hwid", methods=["POST"])
@_login_required
def keys_reset_hwid():
    target = request.form.get("api_key", "").strip()
    platform = request.form.get("platform", "").strip() or None
    if reset_hwid(target, platform):
        flash("HWID reset.", "success")
    else:
        flash("Key not found.", "error")
    return redirect(url_for("admin_web.keys_page"))


# ──────────────────────────────────────────────
#  Orders
# ──────────────────────────────────────────────

@admin_web_bp.route("/orders")
@_login_required
def orders_page():
    orders = list_all_orders()
    return render_template("orders.html", orders=orders)


@admin_web_bp.route("/orders/fulfill", methods=["POST"])
@_login_required
def orders_fulfill():
    order_id = request.form.get("order_id", "").strip()
    key = fulfill_order(order_id, txid="manual_web")
    if key:
        flash(f"Order {order_id} fulfilled. Key: {key}", "success")
    else:
        flash("Order not found or already fulfilled.", "error")
    return redirect(url_for("admin_web.orders_page"))


@admin_web_bp.route("/orders/cancel", methods=["POST"])
@_login_required
def orders_cancel():
    order_id = request.form.get("order_id", "").strip()
    if cancel_order(order_id):
        flash(f"Order {order_id} cancelled.", "success")
    else:
        flash("Order not found or not pending.", "error")
    return redirect(url_for("admin_web.orders_page"))


# ──────────────────────────────────────────────
#  Messages
# ──────────────────────────────────────────────

@admin_web_bp.route("/messages")
@_login_required
def messages_page():
    msgs = []
    if os.path.isfile(MESSAGES_FILE):
        try:
            with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
                msgs = json.load(f)
        except Exception:
            pass
    return render_template("messages.html", messages=msgs)


@admin_web_bp.route("/messages/save", methods=["POST"])
@_login_required
def messages_save():
    text = request.form.get("text", "").strip()
    level = request.form.get("level", "info").strip()
    if not text:
        flash("Message text is required.", "error")
        return redirect(url_for("admin_web.messages_page"))

    msgs = []
    if os.path.isfile(MESSAGES_FILE):
        try:
            with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
                msgs = json.load(f)
        except Exception:
            pass

    msgs.append({
        "text": text,
        "level": level,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "active": True,
    })

    with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
        json.dump(msgs, f, indent=4)

    flash("Message added.", "success")
    return redirect(url_for("admin_web.messages_page"))


@admin_web_bp.route("/messages/delete", methods=["POST"])
@_login_required
def messages_delete():
    idx = request.form.get("index", type=int)
    msgs = []
    if os.path.isfile(MESSAGES_FILE):
        try:
            with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
                msgs = json.load(f)
        except Exception:
            pass

    if idx is not None and 0 <= idx < len(msgs):
        msgs.pop(idx)
        with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
            json.dump(msgs, f, indent=4)
        flash("Message deleted.", "success")
    else:
        flash("Invalid message index.", "error")

    return redirect(url_for("admin_web.messages_page"))


# ──────────────────────────────────────────────
#  Shared Files
# ──────────────────────────────────────────────

@admin_web_bp.route("/files")
@_login_required
def files_page():
    os.makedirs(SHARED_DIR, exist_ok=True)
    files = []
    for fname in sorted(os.listdir(SHARED_DIR)):
        fpath = os.path.join(SHARED_DIR, fname)
        if os.path.isfile(fpath):
            stat = os.stat(fpath)
            files.append({
                "name": fname,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            })
    return render_template("files.html", files=files)


@admin_web_bp.route("/files/upload", methods=["POST"])
@_login_required
def files_upload():
    if "file" not in request.files:
        flash("No file selected.", "error")
        return redirect(url_for("admin_web.files_page"))

    uploaded = request.files["file"]
    filename = os.path.basename(uploaded.filename or "combo.txt")
    os.makedirs(SHARED_DIR, exist_ok=True)
    save_path = os.path.join(SHARED_DIR, filename)
    uploaded.save(save_path)

    flash(f"Uploaded {filename}.", "success")
    return redirect(url_for("admin_web.files_page"))


@admin_web_bp.route("/files/delete", methods=["POST"])
@_login_required
def files_delete():
    filename = request.form.get("filename", "").strip()
    safe_name = os.path.basename(filename)
    fpath = os.path.join(SHARED_DIR, safe_name)

    if os.path.isfile(fpath):
        os.remove(fpath)
        flash(f"Deleted {safe_name}.", "success")
    else:
        flash("File not found.", "error")

    return redirect(url_for("admin_web.files_page"))


# ──────────────────────────────────────────────
#  Activity Logs
# ──────────────────────────────────────────────

@admin_web_bp.route("/logs")
@_login_required
def logs_page():
    limit = request.args.get("limit", 100, type=int)
    activity = get_recent_activity(limit)
    uploads = get_recent_uploads(limit)
    return render_template("logs.html", activity=activity, uploads=uploads, limit=limit)


# ──────────────────────────────────────────────
#  Users (per-user activity summary)
# ──────────────────────────────────────────────

@admin_web_bp.route("/users")
@_login_required
def users_page():
    users = get_per_user_summary()
    keys = list_all_keys()
    # Attach username from keys
    for u in users:
        key_entry = keys.get(u["user_key"])
        u["username"] = key_entry.get("username", "unknown") if key_entry else ("admin" if u["user_key"] == CONFIG["admin_key"] else "unknown")
        u["plan"] = key_entry.get("plan_label", "?") if key_entry else "-"
    return render_template("users.html", users=users)


# ──────────────────────────────────────────────
#  Referrals
# ──────────────────────────────────────────────

@admin_web_bp.route("/referrals")
@_login_required
def referrals_page():
    referrals = list_all_referrals(500)
    keys = list_all_keys()
    for r in referrals:
        ref_entry = keys.get(r["referrer_key"])
        r["referrer_name"] = ref_entry.get("username", "unknown") if ref_entry else "unknown"
        rd_entry = keys.get(r["referred_key"])
        r["referred_name"] = rd_entry.get("username", "unknown") if rd_entry else "unknown"
    return render_template("referrals.html", referrals=referrals)


# ──────────────────────────────────────────────
#  Database Maintenance
# ──────────────────────────────────────────────

@admin_web_bp.route("/maintenance")
@_login_required
def maintenance_page():
    stats = get_db_stats()
    try:
        table_sizes = get_table_sizes()
    except Exception:
        table_sizes = []
    return render_template("maintenance.html", stats=stats, table_sizes=table_sizes)


@admin_web_bp.route("/maintenance/vacuum", methods=["POST"])
@_login_required
def maintenance_vacuum():
    try:
        vacuum_db()
        flash("VACUUM completed successfully.", "success")
    except Exception as e:
        flash(f"VACUUM failed: {e}", "error")
    return redirect(url_for("admin_web.maintenance_page"))


@admin_web_bp.route("/maintenance/optimize", methods=["POST"])
@_login_required
def maintenance_optimize():
    try:
        result = optimize_db()
        flash(f"Optimization complete. Before: {result['size_before_mb']}MB, After: {result['size_after_mb']}MB, Saved: {result['saved_mb']}MB", "success")
    except Exception as e:
        flash(f"Optimization failed: {e}", "error")
    return redirect(url_for("admin_web.maintenance_page"))


@admin_web_bp.route("/maintenance/rebuild-indexes", methods=["POST"])
@_login_required
def maintenance_rebuild_indexes():
    try:
        count = rebuild_indexes()
        flash(f"Rebuilt {count} indexes.", "success")
    except Exception as e:
        flash(f"Index rebuild failed: {e}", "error")
    return redirect(url_for("admin_web.maintenance_page"))


@admin_web_bp.route("/maintenance/purge-logs", methods=["POST"])
@_login_required
def maintenance_purge_logs():
    days = request.form.get("days", 30, type=int)
    try:
        result = purge_old_logs(days)
        total = sum(result.values())
        flash(f"Purged {total} log entries older than {days} days.", "success")
    except Exception as e:
        flash(f"Log purge failed: {e}", "error")
    return redirect(url_for("admin_web.maintenance_page"))


# ──────────────────────────────────────────────
#  Combo Import (web panel)
# ──────────────────────────────────────────────

@admin_web_bp.route("/import", methods=["GET", "POST"])
@_login_required
def import_page():
    if request.method == "POST":
        if "file" not in request.files:
            flash("No file selected.", "error")
            return redirect(url_for("admin_web.import_page"))

        uploaded = request.files["file"]
        if not uploaded.filename:
            flash("No file selected.", "error")
            return redirect(url_for("admin_web.import_page"))

        import tempfile, shutil
        from logger import log_upload

        # Save uploaded file to temp location
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        try:
            uploaded.save(tmp.name)
            tmp.close()

            # Count lines and import
            with open(tmp.name, "r", encoding="utf-8", errors="ignore") as f:
                total_lines = sum(1 for _ in f)

            def line_iter():
                with open(tmp.name, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        yield line.rstrip("\n\r")

            new_count = 0
            for new_in_batch in insert_leak_data_iter(line_iter(), batch_size=50000):
                new_count += new_in_batch

            log_upload("admin_web", uploaded.filename, total_lines, new_count, request.remote_addr or "")
            flash(f"Imported {uploaded.filename}: {total_lines:,} lines, {new_count:,} new records.", "success")
        except Exception as e:
            flash(f"Import failed: {e}", "error")
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

        return redirect(url_for("admin_web.import_page"))

    return render_template("import.html")


# ──────────────────────────────────────────────
#  Push Client Update
# ──────────────────────────────────────────────

@admin_web_bp.route("/update", methods=["GET", "POST"])
@_login_required
def update_page():
    if request.method == "POST":
        if "file" not in request.files or not request.files["file"].filename:
            flash("No file selected.", "error")
            return redirect(url_for("admin_web.update_page"))
        version = request.form.get("version", "").strip()
        if not version:
            flash("Version is required.", "error")
            return redirect(url_for("admin_web.update_page"))

        changelog = request.form.get("changelog", "")
        uploaded = request.files["file"]
        filename = uploaded.filename

        os.makedirs(UPDATES_DIR, exist_ok=True)
        save_path = os.path.join(UPDATES_DIR, filename)
        uploaded.save(save_path)

        sha = hashlib.sha256()
        with open(save_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)

        from datetime import timezone as _tz
        meta = {
            "version": version,
            "filename": filename,
            "sha256": sha.hexdigest(),
            "changelog": changelog,
            "date": datetime.now(_tz.utc).isoformat(),
        }
        with open(UPDATE_META, "w") as f:
            json.dump(meta, f, indent=4)

        from logger import log_activity
        log_activity(CONFIG["admin_key"], "push_update",
                     f"v{version} file={filename}", request.remote_addr or "")
        flash(f"Update v{version} pushed successfully ({filename}).", "success")
        return redirect(url_for("admin_web.update_page"))

    # GET — load current meta
    meta = None
    if os.path.isfile(UPDATE_META):
        try:
            with open(UPDATE_META) as f:
                meta = json.load(f)
        except Exception:
            pass
    return render_template("update.html", meta=meta)


# ──────────────────────────────────────────────
#  Server Log Viewer
# ──────────────────────────────────────────────

@admin_web_bp.route("/server-log")
@_login_required
def server_log_page():
    lines_count = request.args.get("lines", 250, type=int)
    log_file = CONFIG.get("log_file", "server.log")
    log_path = os.path.join(BASE_DIR, log_file)

    log_content = ""
    log_size = "0 B"
    if os.path.isfile(log_path):
        size = os.path.getsize(log_path)
        if size < 1024:
            log_size = f"{size} B"
        elif size < 1024 * 1024:
            log_size = f"{size / 1024:.1f} KB"
        else:
            log_size = f"{size / (1024*1024):.1f} MB"

        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
            log_content = "".join(all_lines[-lines_count:])
        except Exception as e:
            log_content = f"Error reading log: {e}"
    else:
        log_content = "(log file not found)"

    return render_template("server_log.html",
                           log_content=log_content,
                           log_file=log_file,
                           log_size=log_size,
                           lines_count=lines_count)


@admin_web_bp.route("/server-log/download")
@_login_required
def server_log_download():
    log_file = CONFIG.get("log_file", "server.log")
    log_path = os.path.join(BASE_DIR, log_file)
    if os.path.isfile(log_path):
        return send_file(log_path, as_attachment=True, download_name=log_file)
    flash("Log file not found.", "error")
    return redirect(url_for("admin_web.server_log_page"))
