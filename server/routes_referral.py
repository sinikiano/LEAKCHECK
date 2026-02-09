"""
LEAKCHECK Server — Referral System
Users share a referral code (their API key prefix). When someone buys a key
and applies the referral code, the referrer gets bonus days added to their key.

API endpoints:
  GET  /api/referral/code    — Get your referral code
  POST /api/referral/apply   — Apply a referral code (after purchase)
  GET  /api/referral/stats   — Get your referral stats
"""

import json
import time
import hashlib
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify
from config import CONFIG
from auth import require_user_key, _load_keys, _save_keys, _is_key_expired
from database import log_referral, get_referral_stats, is_already_referred
from logger import log_activity

referral_bp = Blueprint("referral", __name__, url_prefix="/api/referral")


def _generate_referral_code(api_key: str) -> str:
    """Derive a short, shareable referral code from an API key.
    Uses first 8 chars of SHA-256(key) for privacy (don't expose the key itself).
    """
    return "REF-" + hashlib.sha256(api_key.encode()).hexdigest()[:8].upper()


def _find_key_by_referral_code(code: str) -> str | None:
    """Find which API key owns this referral code."""
    keys = _load_keys()
    for key in keys:
        if _generate_referral_code(key) == code:
            return key
    return None


def _add_bonus_days(api_key: str, bonus_days: int) -> bool:
    """Add bonus days to a key's expiration (only for non-lifetime keys)."""
    keys = _load_keys()
    entry = keys.get(api_key)
    if not entry or not entry.get("active"):
        return False

    expires_at = entry.get("expires_at")
    if not expires_at:
        # Lifetime key — no days to add, but referral still counts
        return True

    try:
        exp_dt = datetime.fromisoformat(expires_at)
        # If already expired, extend from now instead
        now = datetime.now(timezone.utc)
        base = max(exp_dt, now)
        new_exp = base + timedelta(days=bonus_days)
        entry["expires_at"] = new_exp.isoformat()
        keys[api_key] = entry
        _save_keys(keys)
        return True
    except Exception:
        return False


# ──────────────────────────────────────────────
#  API Endpoints
# ──────────────────────────────────────────────

@referral_bp.route("/code", methods=["GET"])
@require_user_key
def get_code():
    """Return the user's unique referral code."""
    key = request.headers.get("X-API-Key", "")
    code = _generate_referral_code(key)
    return jsonify({
        "status": "ok",
        "referral_code": code,
        "bonus_days": CONFIG.get("referral_bonus_days", 7),
        "message": f"Share this code! When someone buys a key and uses it, you get {CONFIG.get('referral_bonus_days', 7)} bonus days.",
    })


@referral_bp.route("/apply", methods=["POST"])
@require_user_key
def apply_code():
    """Apply a referral code. Both the referrer and the referred user get bonus days.
    Body: { "referral_code": "REF-XXXXXXXX" }
    This should be called ONCE after a user purchases a new key.
    """
    key = request.headers.get("X-API-Key", "")
    data = request.get_json(silent=True) or {}
    code = (data.get("referral_code") or "").strip().upper()

    if not code:
        return jsonify({"status": "error", "message": "referral_code is required."}), 400

    if not code.startswith("REF-"):
        return jsonify({"status": "error", "message": "Invalid referral code format."}), 400

    # Find referrer
    referrer_key = _find_key_by_referral_code(code)
    if not referrer_key:
        return jsonify({"status": "error", "message": "Referral code not found."}), 404

    # Can't refer yourself
    if referrer_key == key:
        return jsonify({"status": "error", "message": "You cannot use your own referral code."}), 400

    # Check if this key has already used a referral code
    stats = get_referral_stats(key)
    # Check if this key was already referred
    already_referred = is_already_referred(key)

    if already_referred:
        return jsonify({"status": "error",
                        "message": "This key has already used a referral code."}), 400

    bonus = CONFIG.get("referral_bonus_days", 7)

    # Add bonus to referrer
    _add_bonus_days(referrer_key, bonus)

    # Add bonus to the new user too
    _add_bonus_days(key, bonus)

    # Log the referral
    log_referral(referrer_key, key, bonus)
    log_activity(key, "referral_apply",
                 f"code={code} referrer={referrer_key[:12]}... bonus={bonus}d",
                 request.remote_addr)

    # Notify referrer via Telegram if linked
    try:
        from telegram_bot import get_linked_key, send_message, _load_links
        links = _load_links()
        for chat_id, link_data in links.items():
            if link_data.get("api_key") == referrer_key:
                send_message(chat_id,
                    f"🎉 <b>Referral Bonus!</b>\n\n"
                    f"Someone used your referral code!\n"
                    f"+{bonus} days added to your subscription.")
                break
    except Exception:
        pass

    return jsonify({
        "status": "ok",
        "message": f"Referral applied! +{bonus} bonus days for you and the referrer.",
        "bonus_days": bonus,
    })


@referral_bp.route("/stats", methods=["GET"])
@require_user_key
def referral_stats():
    """Return referral statistics for the current user."""
    key = request.headers.get("X-API-Key", "")
    code = _generate_referral_code(key)
    stats = get_referral_stats(key)

    return jsonify({
        "status": "ok",
        "referral_code": code,
        "referral_count": stats["referral_count"],
        "total_bonus_days": stats["total_bonus_days"],
        "bonus_per_referral": CONFIG.get("referral_bonus_days", 7),
    })
