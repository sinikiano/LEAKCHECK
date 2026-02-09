"""
LEAKCHECK Server — Binance Payment Integration
Monitors USDT deposits on Binance and auto-fulfils subscription orders.

Flow:
  1. Client creates an order  →  server assigns a unique USDT amount
  2. Customer sends EXACT amount to the configured USDT address
  3. Background thread polls Binance deposit history every 30 s
  4. On match (amount + time window)  →  generate API key  →  mark paid
"""

import os
import json
import time
import hmac
import hashlib
import threading
import urllib.parse
from datetime import datetime, timezone, timedelta

import requests as _req

from config import CONFIG, ORDERS_FILE

# ──────────────────────────────────────────────
#  Subscription Plans  &  Prices (USDT)
# ──────────────────────────────────────────────

PRICES: dict[str, dict] = {
    "1_month":  {"label": "1 Month",   "days": 30,  "price": 10.00},
    "3_month":  {"label": "3 Months",  "days": 90,  "price": 25.00},
    "6_month":  {"label": "6 Months",  "days": 180, "price": 45.00},
    "1_year":   {"label": "1 Year",    "days": 365, "price": 80.00},
    "lifetime": {"label": "Lifetime",  "days": 0,   "price": 150.00},
}

# ──────────────────────────────────────────────
#  Order Persistence  (orders.json)
# ──────────────────────────────────────────────

_lock = threading.Lock()


def _load_orders() -> dict:
    if not os.path.isfile(ORDERS_FILE):
        return {"counter": 0, "orders": {}}
    try:
        with open(ORDERS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"counter": 0, "orders": {}}


def _save_orders(data: dict):
    with open(ORDERS_FILE, "w") as f:
        json.dump(data, f, indent=4)


# ──────────────────────────────────────────────
#  Create / Query Orders
# ──────────────────────────────────────────────

def list_plans() -> list[dict]:
    """Return plan info + prices for the client."""
    return [
        {"plan": k, "label": v["label"], "price": v["price"]}
        for k, v in PRICES.items()
    ]


def create_order(plan: str, username: str = "") -> dict | None:
    """Create a pending order with a unique USDT amount.

    The unique amount = base_price + counter/10000 so that no two
    pending orders share the same amount (up to ~9 999 concurrent).
    """
    if plan not in PRICES:
        return None

    base_price = PRICES[plan]["price"]

    with _lock:
        data = _load_orders()
        data["counter"] = data.get("counter", 0) + 1
        counter = data["counter"]

        suffix = (counter % 9999) + 1          # 1 … 9999
        amount = round(base_price + suffix / 10000, 4)

        order_id = f"ORD-{counter:06d}"
        now = datetime.now(timezone.utc)

        order = {
            "plan": plan,
            "plan_label": PRICES[plan]["label"],
            "amount": amount,
            "username": username or f"buyer_{counter}",
            "status": "pending",               # pending | paid | expired | cancelled
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=1)).isoformat(),
            "paid_at": None,
            "api_key": None,
            "txid": None,
        }

        data["orders"][order_id] = order
        _save_orders(data)

    return {
        "order_id": order_id,
        "plan": plan,
        "plan_label": PRICES[plan]["label"],
        "amount": amount,
        "address": CONFIG.get("usdt_address", ""),
        "network": CONFIG.get("usdt_network", "TRC20"),
        "expires_at": order["expires_at"],
    }


def get_order(order_id: str) -> dict | None:
    with _lock:
        data = _load_orders()
    order = data["orders"].get(order_id)
    if not order:
        return None
    return {
        "order_id": order_id,
        "status": order["status"],
        "plan": order["plan"],
        "plan_label": order.get("plan_label", order["plan"]),
        "amount": order["amount"],
        "api_key": order.get("api_key"),
        "created_at": order["created_at"],
        "expires_at": order["expires_at"],
        "paid_at": order.get("paid_at"),
    }


def list_all_orders() -> dict:
    """Return the raw orders dict for the admin panel."""
    with _lock:
        data = _load_orders()
    return data.get("orders", {})


def fulfill_order(order_id: str, txid: str = "manual") -> str | None:
    """Manually or automatically fulfil a pending order.
    Returns the generated API key, or None if the order wasn't found/pending.
    """
    from auth import generate_key  # local import avoids circular

    with _lock:
        data = _load_orders()
        order = data["orders"].get(order_id)
        if not order or order["status"] != "pending":
            return None

        key = generate_key(order["username"], order["plan"])
        order["status"] = "paid"
        order["paid_at"] = datetime.now(timezone.utc).isoformat()
        order["api_key"] = key
        order["txid"] = txid
        _save_orders(data)

    # Notify admin via Telegram
    try:
        from telegram_bot import notify_payment
        notify_payment(order_id, order["username"], order.get("plan_label", order["plan"]),
                        order["amount"], key)
    except Exception:
        pass

    return key


def cancel_order(order_id: str) -> bool:
    with _lock:
        data = _load_orders()
        order = data["orders"].get(order_id)
        if not order or order["status"] != "pending":
            return False
        order["status"] = "cancelled"
        _save_orders(data)
    return True


# ──────────────────────────────────────────────
#  Binance API — Deposit History Polling
# ──────────────────────────────────────────────

def _sign(params: dict, secret: str) -> str:
    qs = urllib.parse.urlencode(params)
    return hmac.new(secret.encode(), qs.encode(), hashlib.sha256).hexdigest()


def _fetch_deposits() -> list[dict]:
    """Fetch recent successful USDT deposits from Binance."""
    api_key = CONFIG.get("binance_api_key", "")
    api_secret = CONFIG.get("binance_api_secret", "")
    if not api_key or not api_secret:
        return []

    params: dict = {
        "coin": "USDT",
        "status": 1,                               # success
        "startTime": int((time.time() - 7200) * 1000),  # last 2 h
        "timestamp": int(time.time() * 1000),
    }
    params["signature"] = _sign(params, api_secret)

    try:
        r = _req.get(
            "https://api.binance.com/sapi/v1/capital/deposit/hisrec",
            params=params,
            headers={"X-MBX-APIKEY": api_key},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []


def _match_deposits():
    """Compare recent deposits against pending orders and fulfil matches."""
    deposits = _fetch_deposits()
    if not deposits:
        return

    with _lock:
        data = _load_orders()
        changed = False

        for dep in deposits:
            dep_amount = float(dep.get("amount", 0))
            dep_txid = dep.get("txId", dep.get("id", ""))

            for oid, order in data["orders"].items():
                if order["status"] != "pending":
                    continue
                # already matched by a previous deposit?
                if order.get("txid"):
                    continue
                # amount match within tiny tolerance (float rounding)
                if abs(order["amount"] - dep_amount) < 0.00009:
                    from auth import generate_key
                    key = generate_key(order["username"], order["plan"])
                    order["status"] = "paid"
                    order["paid_at"] = datetime.now(timezone.utc).isoformat()
                    order["api_key"] = key
                    order["txid"] = dep_txid
                    changed = True
                    # Notify admin via Telegram
                    try:
                        from telegram_bot import notify_payment
                        notify_payment(oid, order["username"],
                                       order.get("plan_label", order["plan"]),
                                       order["amount"], key)
                    except Exception:
                        pass
                    break  # one deposit → one order

        if changed:
            _save_orders(data)


def _expire_old_orders():
    """Mark pending orders past their expiration as expired."""
    now = datetime.now(timezone.utc)
    with _lock:
        data = _load_orders()
        changed = False
        for order in data["orders"].values():
            if order["status"] == "pending":
                try:
                    exp = datetime.fromisoformat(order["expires_at"])
                    if now > exp:
                        order["status"] = "expired"
                        changed = True
                except Exception:
                    pass
        if changed:
            _save_orders(data)


# ──────────────────────────────────────────────
#  Background Monitor Thread
# ──────────────────────────────────────────────

_poll_running = False
_poll_thread: threading.Thread | None = None


def start_payment_monitor():
    """Start background polling loop (call once at server start)."""
    global _poll_running, _poll_thread
    if _poll_running:
        return
    _poll_running = True

    def _loop():
        while _poll_running:
            try:
                _expire_old_orders()
                _match_deposits()
            except Exception:
                pass
            time.sleep(30)

    _poll_thread = threading.Thread(target=_loop, daemon=True)
    _poll_thread.start()


def stop_payment_monitor():
    global _poll_running
    _poll_running = False
