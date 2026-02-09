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
from config import CONFIG, BASE_DIR, MESSAGES_FILE, SHARED_DIR
from auth import (generate_key, revoke_key, list_all_keys, reset_hwid,
                  get_key_info, PLANS)
from database import get_db_stats, init_referral_table
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
    activity = get_recent_activity(20)
    uploads = get_recent_uploads(10)

    return render_template("dashboard.html",
        stats=stats,
        total_keys=len(keys),
        active_keys=active_count,
        pending_orders=pending_orders,
        paid_orders=paid_orders,
        total_orders=len(orders),
        activity=activity,
        uploads=uploads,
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
