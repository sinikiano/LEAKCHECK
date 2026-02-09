"""
LEAKCHECK Server — Telegram Bot
Allows users to /search email directly from Telegram, tied to their API key.
Also sends admin webhook notifications for payments, key events, and alerts.

Commands:
  /start          — Welcome message
  /help           — Show available commands
  /link <api_key> — Link your LEAKCHECK API key to this Telegram account
  /unlink         — Unlink your API key
  /search <email> — Search for leaked passwords (uses daily quota)
  /quota          — Check remaining daily search quota
  /status         — Show your key info (plan, expiry)
  /stats          — Show your personal usage stats
"""

import os
import json
import time
import threading
import logging
import re
from datetime import datetime, timezone

import requests as _req

from config import CONFIG, BASE_DIR

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
#  Config
# ──────────────────────────────────────────────

TELEGRAM_LINKS_FILE = os.path.join(BASE_DIR, "telegram_links.json")

def _get_bot_token() -> str:
    return CONFIG.get("telegram_bot_token", "")

def _get_admin_chat_id() -> str:
    return CONFIG.get("telegram_admin_chat_id", "")

# ──────────────────────────────────────────────
#  Telegram Link Persistence  (chat_id → api_key)
# ──────────────────────────────────────────────

_links_lock = threading.Lock()

def _load_links() -> dict:
    if not os.path.isfile(TELEGRAM_LINKS_FILE):
        return {}
    try:
        with open(TELEGRAM_LINKS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_links(data: dict):
    with open(TELEGRAM_LINKS_FILE, "w") as f:
        json.dump(data, f, indent=4)

def link_telegram(chat_id: str, api_key: str):
    with _links_lock:
        data = _load_links()
        data[str(chat_id)] = {"api_key": api_key, "linked_at": time.time()}
        _save_links(data)

def unlink_telegram(chat_id: str) -> bool:
    with _links_lock:
        data = _load_links()
        if str(chat_id) in data:
            del data[str(chat_id)]
            _save_links(data)
            return True
    return False

def get_linked_key(chat_id: str) -> str | None:
    with _links_lock:
        data = _load_links()
    entry = data.get(str(chat_id))
    return entry["api_key"] if entry else None

# ──────────────────────────────────────────────
#  Telegram API Helpers
# ──────────────────────────────────────────────

def _tg_api(method: str, **kwargs) -> dict | None:
    token = _get_bot_token()
    if not token:
        return None
    try:
        r = _req.post(
            f"https://api.telegram.org/bot{token}/{method}",
            json=kwargs,
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
        logger.warning(f"Telegram API {method} returned {r.status_code}: {r.text[:200]}")
    except Exception as e:
        logger.warning(f"Telegram API error: {e}")
    return None

def send_message(chat_id: str | int, text: str, parse_mode: str = "HTML"):
    return _tg_api("sendMessage", chat_id=chat_id, text=text, parse_mode=parse_mode)

# ──────────────────────────────────────────────
#  Admin Webhook Notifications
# ──────────────────────────────────────────────

def notify_admin(text: str):
    """Send a notification to the admin Telegram chat."""
    admin_id = _get_admin_chat_id()
    if admin_id:
        send_message(admin_id, f"🔔 <b>LEAKCHECK Alert</b>\n\n{text}")

def notify_payment(order_id: str, username: str, plan: str, amount: float, api_key: str):
    """Notify admin of a successful payment."""
    notify_admin(
        f"💰 <b>Payment Received</b>\n"
        f"Order: <code>{order_id}</code>\n"
        f"User: <code>{username}</code>\n"
        f"Plan: {plan}\n"
        f"Amount: {amount} USDT\n"
        f"Key: <code>{api_key[:16]}...</code>"
    )

def notify_key_activation(username: str, plan: str, key: str):
    """Notify admin of a new key activation."""
    notify_admin(
        f"🔑 <b>Key Generated</b>\n"
        f"User: <code>{username}</code>\n"
        f"Plan: {plan}\n"
        f"Key: <code>{key[:16]}...</code>"
    )

def notify_suspicious(event: str, detail: str, ip: str = ""):
    """Notify admin of suspicious activity."""
    notify_admin(
        f"⚠️ <b>Suspicious Activity</b>\n"
        f"Event: {event}\n"
        f"Detail: {detail}\n"
        f"IP: <code>{ip}</code>"
    )

def notify_hwid_mismatch(username: str, platform: str, ip: str):
    """Notify admin when someone tries using a key from a wrong device."""
    notify_admin(
        f"🔒 <b>HWID Mismatch</b>\n"
        f"User: <code>{username}</code>\n"
        f"Platform: {platform}\n"
        f"IP: <code>{ip}</code>\n"
        f"Someone tried to use this key from a different device."
    )

# ──────────────────────────────────────────────
#  Bot Command Handlers
# ──────────────────────────────────────────────

def _handle_start(chat_id: str, _args: str):
    send_message(chat_id,
        "🔒 <b>LEAKCHECK Bot</b>\n\n"
        "Link your API key to search for leaked passwords directly from Telegram.\n\n"
        "Use <code>/link YOUR_API_KEY</code> to get started.\n"
        "Use <code>/help</code> to see all commands."
    )

def _handle_help(chat_id: str, _args: str):
    send_message(chat_id,
        "📖 <b>Available Commands</b>\n\n"
        "/link <code>API_KEY</code> — Link your LEAKCHECK API key\n"
        "/unlink — Unlink your key\n"
        "/search <code>email@example.com</code> — Search for leaked passwords\n"
        "/quota — Check daily search quota\n"
        "/status — Show your plan & expiry\n"
        "/stats — Show your personal usage stats\n"
        "/help — Show this message"
    )

def _handle_link(chat_id: str, args: str):
    api_key = args.strip()
    if not api_key:
        send_message(chat_id, "❌ Usage: <code>/link YOUR_API_KEY</code>")
        return

    from auth import is_valid_user_key
    if not is_valid_user_key(api_key):
        send_message(chat_id, "❌ Invalid or expired API key.")
        return

    link_telegram(chat_id, api_key)
    send_message(chat_id, "✅ API key linked successfully! You can now use /search.")

def _handle_unlink(chat_id: str, _args: str):
    if unlink_telegram(chat_id):
        send_message(chat_id, "✅ API key unlinked.")
    else:
        send_message(chat_id, "ℹ️ No key linked to this account.")

def _handle_search(chat_id: str, args: str):
    api_key = get_linked_key(chat_id)
    if not api_key:
        send_message(chat_id, "❌ No API key linked. Use <code>/link YOUR_API_KEY</code> first.")
        return

    from auth import is_valid_user_key
    if not is_valid_user_key(api_key):
        send_message(chat_id, "❌ Your linked API key is invalid or expired.")
        return

    email = args.strip().lower()
    if not email:
        send_message(chat_id, "❌ Usage: <code>/search email@example.com</code>")
        return

    if not re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email):
        send_message(chat_id, "❌ Invalid email format.")
        return

    from database import get_search_count_today, search_by_email, log_search
    from logger import log_activity

    daily_limit = CONFIG.get("daily_search_limit", 30)
    used = get_search_count_today(api_key)
    remaining = max(0, daily_limit - used)

    if remaining <= 0:
        send_message(chat_id,
            f"⏳ Daily search limit reached ({daily_limit}/day). Try again tomorrow.")
        return

    t0 = time.time()
    results = search_by_email(email)
    elapsed_ms = round((time.time() - t0) * 1000, 1)

    log_search(api_key, email, len(results))
    log_activity(api_key, "search_tg", f"email={email} results={len(results)}", "telegram", elapsed_ms)

    if not results:
        send_message(chat_id,
            f"🔍 <b>No results</b> for <code>{email}</code>\n"
            f"⏱ {elapsed_ms}ms • {remaining - 1} searches left today")
        return

    # Format results (limit to 50 to avoid message too long)
    lines = []
    for i, r in enumerate(results[:50], 1):
        lines.append(f"{i}. <code>{r['password']}</code>")

    result_text = "\n".join(lines)
    extra = f"\n\n<i>...and {len(results) - 50} more</i>" if len(results) > 50 else ""

    send_message(chat_id,
        f"🔍 <b>{len(results)} result(s)</b> for <code>{email}</code>\n\n"
        f"{result_text}{extra}\n\n"
        f"⏱ {elapsed_ms}ms • {remaining - 1} searches left today")

def _handle_quota(chat_id: str, _args: str):
    api_key = get_linked_key(chat_id)
    if not api_key:
        send_message(chat_id, "❌ No API key linked. Use <code>/link YOUR_API_KEY</code>")
        return

    from database import get_search_count_today
    daily_limit = CONFIG.get("daily_search_limit", 30)
    used = get_search_count_today(api_key)
    remaining = max(0, daily_limit - used)

    send_message(chat_id,
        f"📊 <b>Search Quota</b>\n\n"
        f"Used today: {used}/{daily_limit}\n"
        f"Remaining: {remaining}")

def _handle_status(chat_id: str, _args: str):
    api_key = get_linked_key(chat_id)
    if not api_key:
        send_message(chat_id, "❌ No API key linked. Use <code>/link YOUR_API_KEY</code>")
        return

    from auth import get_key_info
    info = get_key_info(api_key)
    if not info:
        send_message(chat_id, "❌ Could not retrieve key info.")
        return

    status_icon = "✅" if info["active"] else "❌"
    send_message(chat_id,
        f"🔑 <b>Key Status</b>\n\n"
        f"Status: {status_icon} {'Active' if info['active'] else 'Inactive'}\n"
        f"Plan: {info['plan_label']}\n"
        f"Expires: {info['expires_at']}\n"
        f"Days left: {info['days_remaining'] if info['days_remaining'] is not None else '∞'}")

def _handle_stats(chat_id: str, _args: str):
    api_key = get_linked_key(chat_id)
    if not api_key:
        send_message(chat_id, "❌ No API key linked. Use <code>/link YOUR_API_KEY</code>")
        return

    from database import get_user_stats
    stats = get_user_stats(api_key)
    if not stats:
        send_message(chat_id, "📊 No usage data yet.")
        return

    send_message(chat_id,
        f"📊 <b>Your Usage Stats</b>\n\n"
        f"Total checks: {stats['total_checks']:,}\n"
        f"Total combos checked: {stats['total_combos_checked']:,}\n"
        f"Searches used today: {stats['searches_today']}\n"
        f"Total searches: {stats['total_searches']:,}\n"
        f"Files downloaded: {stats['files_downloaded']}\n"
        f"Account age: {stats['account_age_days']} days\n"
        f"Last active: {stats['last_active']}")

# Command dispatcher
_COMMANDS = {
    "/start": _handle_start,
    "/help": _handle_help,
    "/link": _handle_link,
    "/unlink": _handle_unlink,
    "/search": _handle_search,
    "/quota": _handle_quota,
    "/status": _handle_status,
    "/stats": _handle_stats,
}

# ──────────────────────────────────────────────
#  Update Processing
# ──────────────────────────────────────────────

_last_update_id = 0

def _process_update(update: dict):
    """Process a single Telegram update (message)."""
    global _last_update_id
    uid = update.get("update_id", 0)
    if uid > _last_update_id:
        _last_update_id = uid

    msg = update.get("message")
    if not msg:
        return
    text = msg.get("text", "").strip()
    chat_id = str(msg["chat"]["id"])

    if not text.startswith("/"):
        return

    # Parse command and arguments
    parts = text.split(None, 1)
    cmd = parts[0].lower().split("@")[0]  # handle /command@botname
    args = parts[1] if len(parts) > 1 else ""

    handler = _COMMANDS.get(cmd)
    if handler:
        try:
            handler(chat_id, args)
        except Exception as e:
            logger.error(f"Telegram command error ({cmd}): {e}")
            send_message(chat_id, f"❌ Error: {str(e)[:200]}")
    else:
        send_message(chat_id, "❓ Unknown command. Use /help to see available commands.")

# ──────────────────────────────────────────────
#  Polling Loop (Long-poll)
# ──────────────────────────────────────────────

_bot_running = False
_bot_thread: threading.Thread | None = None

def start_telegram_bot():
    """Start the Telegram bot polling loop in a background thread."""
    global _bot_running, _bot_thread, _last_update_id
    token = _get_bot_token()
    if not token:
        logger.info("Telegram bot token not configured — bot disabled.")
        return
    if _bot_running:
        return

    _bot_running = True

    def _poll_loop():
        global _last_update_id
        logger.info("Telegram bot started polling.")
        while _bot_running:
            try:
                r = _req.get(
                    f"https://api.telegram.org/bot{token}/getUpdates",
                    params={"offset": _last_update_id + 1, "timeout": 30},
                    timeout=35,
                )
                if r.status_code == 200:
                    data = r.json()
                    for update in data.get("result", []):
                        _process_update(update)
            except _req.exceptions.Timeout:
                pass  # normal for long-poll
            except Exception as e:
                logger.warning(f"Telegram poll error: {e}")
                time.sleep(5)

    _bot_thread = threading.Thread(target=_poll_loop, daemon=True)
    _bot_thread.start()
    logger.info("Telegram bot thread started.")

def stop_telegram_bot():
    global _bot_running
    _bot_running = False
