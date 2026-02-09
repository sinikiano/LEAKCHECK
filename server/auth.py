"""
LEAKCHECK Server — Authentication & Rate Limiting
Manages API keys (keys.json) with plan-based expiration and request throttling.
"""

import os
import json
import time
import secrets
import threading
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import request, jsonify
from config import CONFIG, KEYS_FILE

# ──────────────────────────────────────────────
#  Subscription Plans
# ──────────────────────────────────────────────

PLANS = {
    "1_month":   {"label": "1 Month",   "days": 30},
    "3_month":   {"label": "3 Months",  "days": 90},
    "6_month":   {"label": "6 Months",  "days": 180},
    "1_year":    {"label": "1 Year",    "days": 365},
    "lifetime":  {"label": "Lifetime",  "days": 0},   # 0 = never expires
}


# ──────────────────────────────────────────────
#  API Keys  (persisted in keys.json)
# ──────────────────────────────────────────────

def _load_keys() -> dict:
    if not os.path.isfile(KEYS_FILE):
        return {}
    with open(KEYS_FILE, "r") as f:
        return json.load(f)


def _save_keys(keys: dict):
    with open(KEYS_FILE, "w") as f:
        json.dump(keys, f, indent=4)


def _is_key_expired(entry: dict) -> bool:
    """Return True if the key has passed its expiration date."""
    expires = entry.get("expires_at")
    if not expires:          # lifetime or legacy key
        return False
    try:
        exp_dt = datetime.fromisoformat(expires)
        return datetime.now(timezone.utc) > exp_dt
    except Exception:
        return False


def is_valid_user_key(key: str) -> bool:
    keys = _load_keys()
    entry = keys.get(key)
    if not entry:
        return False
    if not entry.get("active", False):
        return False
    if _is_key_expired(entry):
        return False
    return True


def is_key_expired(key: str) -> bool:
    """Public helper: check if a specific key is expired (but exists)."""
    keys = _load_keys()
    entry = keys.get(key)
    if not entry:
        return False
    return _is_key_expired(entry)


# ──────────────────────────────────────────────
#  HWID Lock  (bind key to one PC)
# ──────────────────────────────────────────────

def check_hwid(key: str, hwid: str, platform: str = "desktop") -> str | None:
    """
    Check HWID for a key on the given platform.
    Returns None if OK, or an error string.
    Each platform (desktop, android) gets its own HWID slot so
    the same key can be used on one PC + one phone.
    """
    if not hwid:
        return None  # client didn't send HWID, skip check
    keys = _load_keys()
    entry = keys.get(key)
    if not entry:
        return None

    # ── Migrate legacy single-hwid → per-platform dict ──
    hwids = entry.get("hwids")
    if hwids is None:
        old = entry.get("hwid")
        if old and old != "":
            hwids = {"desktop": old}
        else:
            hwids = {}
        entry["hwids"] = hwids
        entry.pop("hwid", None)
        keys[key] = entry
        _save_keys(keys)

    stored = hwids.get(platform)
    if stored is None or stored == "":
        # First use on this platform — bind
        hwids[platform] = hwid
        entry["hwids"] = hwids
        keys[key] = entry
        _save_keys(keys)
        return None
    if stored != hwid:
        # Notify admin via Telegram
        try:
            from telegram_bot import notify_hwid_mismatch
            username = entry.get("username", "unknown")
            notify_hwid_mismatch(username, platform, "")
        except Exception:
            pass
        return (f"HWID mismatch — this key is already bound to another "
                f"{platform} device. Contact @BionicSailor.")
    return None


def reset_hwid(key: str, platform: str | None = None) -> bool:
    """Admin action: unbind a key from its device(s).
    If platform is given, only reset that slot; otherwise reset all."""
    keys = _load_keys()
    if key not in keys:
        return False
    entry = keys[key]
    # Support both legacy 'hwid' and new 'hwids' dict
    if platform:
        hwids = entry.get("hwids", {})
        hwids.pop(platform, None)
        entry["hwids"] = hwids
    else:
        entry["hwids"] = {}
        entry.pop("hwid", None)  # clean up legacy field too
    _save_keys(keys)
    return True


def get_key_username(key: str) -> str:
    keys = _load_keys()
    entry = keys.get(key)
    if entry:
        return entry.get("username", "unknown")
    if key == CONFIG["admin_key"]:
        return "admin"
    return "unknown"


def get_key_info(key: str) -> dict | None:
    """Return full key info dict for a given key (used by /api/keyinfo)."""
    keys = _load_keys()
    entry = keys.get(key)
    if not entry:
        return None

    plan = entry.get("plan", "lifetime")
    plan_label = PLANS.get(plan, {}).get("label", plan)
    expires_at = entry.get("expires_at")
    expired = _is_key_expired(entry)

    days_remaining = None  # lifetime = None
    if expires_at:
        try:
            exp_dt = datetime.fromisoformat(expires_at)
            delta = exp_dt - datetime.now(timezone.utc)
            days_remaining = max(0, delta.days)
        except Exception:
            days_remaining = 0

    return {
        "username": entry.get("username", "unknown"),
        "plan": plan,
        "plan_label": plan_label,
        "created": entry.get("created", ""),
        "expires_at": expires_at or "never",
        "days_remaining": days_remaining,
        "expired": expired,
        "active": entry.get("active", False) and not expired,
        "hwid_bound": bool(entry.get("hwids", {})),
    }


def generate_key(username: str, plan: str = "1_month") -> str:
    """Generate a new API key with a subscription plan."""
    key = secrets.token_urlsafe(32)
    keys = _load_keys()

    now = datetime.now(timezone.utc)
    plan_info = PLANS.get(plan, PLANS["1_month"])
    days = plan_info["days"]

    entry = {
        "username": username,
        "plan": plan,
        "plan_label": plan_info["label"],
        "created": now.isoformat(),
        "active": True,
        "hwids": {},
    }
    if days > 0:
        entry["expires_at"] = (now + timedelta(days=days)).isoformat()
    else:
        entry["expires_at"] = None  # lifetime

    keys[key] = entry
    _save_keys(keys)

    # Notify admin via Telegram
    try:
        from telegram_bot import notify_key_activation
        notify_key_activation(username, plan_info["label"], key)
    except Exception:
        pass

    return key


def revoke_key(target_key: str) -> bool:
    keys = _load_keys()
    if target_key not in keys:
        return False
    keys[target_key]["active"] = False
    _save_keys(keys)
    return True


def list_all_keys() -> dict:
    return _load_keys()


# ──────────────────────────────────────────────
#  Rate Limiter  (in-memory, per API key)
# ──────────────────────────────────────────────

_rate_lock = threading.Lock()
_rate_buckets: dict[str, list[float]] = {}  # key → list of timestamps


def _is_rate_limited(api_key: str, weight: int = 1) -> bool:
    """Returns True if the key has exceeded rate_limit_per_minute.
    weight: how many 'slots' this request costs (default 1).
    """
    limit = CONFIG.get("rate_limit_per_minute", 300)
    now = time.time()
    window = 60.0

    with _rate_lock:
        if api_key not in _rate_buckets:
            _rate_buckets[api_key] = []

        # Purge old entries
        _rate_buckets[api_key] = [t for t in _rate_buckets[api_key] if now - t < window]

        if len(_rate_buckets[api_key]) + weight > limit:
            return True

        # Record 'weight' hits
        for _ in range(weight):
            _rate_buckets[api_key].append(now)
        return False


def _get_retry_after(api_key: str) -> int:
    """Return seconds until the oldest entry in the bucket expires."""
    with _rate_lock:
        bucket = _rate_buckets.get(api_key, [])
        if not bucket:
            return 1
        oldest = min(bucket)
        retry = max(1, int(60.0 - (time.time() - oldest)) + 1)
        return retry


# ──────────────────────────────────────────────
#  Flask Decorators
# ──────────────────────────────────────────────

def require_user_key(fn):
    """Requires any valid user key OR the admin key. Enforces rate limiting."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        key = request.headers.get("X-API-Key", "")
        if not key:
            return jsonify({"error": "Unauthorized",
                            "message": "API key required. Contact @BionicSailor on Telegram."}), 401

        if key != CONFIG["admin_key"]:
            if not is_valid_user_key(key):
                # Distinguish expired vs invalid
                if is_key_expired(key):
                    return jsonify({"error": "Expired",
                                    "message": "Your API key has expired. Contact @BionicSailor to renew."}), 403
                return jsonify({"error": "Unauthorized",
                                "message": "Invalid API key. Contact @BionicSailor on Telegram."}), 401

            # HWID lock check (per-platform)
            hwid = request.headers.get("X-HWID", "")
            platform = request.headers.get("X-Platform", "desktop")
            hwid_err = check_hwid(key, hwid, platform)
            if hwid_err:
                return jsonify({"error": "HWID Locked",
                                "message": hwid_err}), 403

        if _is_rate_limited(key):
            retry_after = _get_retry_after(key)
            resp = jsonify({"error": "Too Many Requests",
                            "message": f"Rate limit exceeded. Please wait {retry_after}s.",
                            "retry_after": retry_after})
            resp.headers["Retry-After"] = str(retry_after)
            return resp, 429

        return fn(*args, **kwargs)
    return wrapper


def require_admin_key(fn):
    """Requires the admin key only."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        key = request.headers.get("X-API-Key", "")
        if key != CONFIG["admin_key"]:
            return jsonify({"error": "Forbidden", "message": "Admin access only."}), 403
        return fn(*args, **kwargs)
    return wrapper
