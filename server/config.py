"""
LEAKCHECK Server — Configuration
"""

import os
import sys
import json

# When running as a frozen .exe, use the directory containing the .exe,
# NOT the temp extraction dir (_MEIPASS). This ensures the database,
# keys, config, and logs are stored next to the .exe and persist.
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "server_config.json")

DEFAULT_CONFIG = {
    "host": "0.0.0.0",
    "port": 5000,
    "admin_key": "oOEvIZg1BDDZ96UOC1ViNcclDdWi7PIiQHr04fZsug0",
    "db_path": "leakcheck.db",
    "max_combo_batch": 50000,
    "rate_limit_per_minute": 300,
    "daily_search_limit": 30,
    "log_file": "server.log",
    "debug": False,
    # ── Binance Payment Settings ──
    "binance_api_key": "",
    "binance_api_secret": "",
    "usdt_address": "",
    "usdt_network": "TRC20",
    # ── Telegram Bot Settings ──
    "telegram_bot_token": "",
    "telegram_admin_chat_id": "",
    # ── Referral System Settings ──
    "referral_bonus_days": 7,
    # ── Admin Web Dashboard ──
    "admin_web_enabled": True,
    "admin_web_secret": "change_me_to_a_random_secret",
}

KEYS_FILE = os.path.join(BASE_DIR, "keys.json")
ORDERS_FILE = os.path.join(BASE_DIR, "orders.json")
MESSAGES_FILE = os.path.join(BASE_DIR, "messages.json")
UPDATES_DIR = os.path.join(BASE_DIR, "updates")
UPDATE_META = os.path.join(UPDATES_DIR, "update.json")
SHARED_DIR = os.path.join(BASE_DIR, "shared")


def load_config() -> dict:
    if os.path.isfile(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            user = json.load(f)
        cfg = {**DEFAULT_CONFIG, **user}
    else:
        cfg = DEFAULT_CONFIG.copy()
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=4)
        print(f"[!] Created default config → {CONFIG_FILE}")

    if not os.path.isabs(cfg["db_path"]):
        cfg["db_path"] = os.path.join(BASE_DIR, cfg["db_path"])
    return cfg


CONFIG = load_config()
