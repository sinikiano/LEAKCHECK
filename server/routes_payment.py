"""
LEAKCHECK Server — Payment API Routes
Blueprint: /api/*  (public — no API key required for purchasing)
"""

import time
import threading
from functools import wraps
from flask import Blueprint, request, jsonify

from binance_pay import list_plans, create_order, get_order

pay_bp = Blueprint("payment", __name__, url_prefix="/api")

# ──────────────────────────────────────────────
#  Simple IP-based rate limiter for order creation
# ──────────────────────────────────────────────

_ip_lock = threading.Lock()
_ip_buckets: dict[str, list[float]] = {}


def _rate_limit_ip(max_per_hour: int = 10):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            ip = request.remote_addr or "unknown"
            now = time.time()
            with _ip_lock:
                bucket = _ip_buckets.setdefault(ip, [])
                _ip_buckets[ip] = [t for t in bucket if now - t < 3600]
                if len(_ip_buckets[ip]) >= max_per_hour:
                    return jsonify({"error": "Rate limited",
                                    "message": "Too many orders. Try again later."}), 429
                _ip_buckets[ip].append(now)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ──────────────────────────────────────────────
#  Endpoints
# ──────────────────────────────────────────────

@pay_bp.route("/plans", methods=["GET"])
def plans():
    """Return available plans with prices (public)."""
    return jsonify({"status": "ok", "plans": list_plans()})


@pay_bp.route("/create-order", methods=["POST"])
@_rate_limit_ip(max_per_hour=20)
def create_payment_order():
    """Create a pending payment order (public).

    Body: { "plan": "1_month", "username": "optional" }
    Returns: order_id, amount (unique), address, network, expires_at
    """
    data = request.get_json(silent=True) or {}
    plan = data.get("plan", "").strip()
    username = data.get("username", "").strip()

    if not plan:
        return jsonify({"status": "error", "message": "plan is required."}), 400

    result = create_order(plan, username)
    if not result:
        return jsonify({"status": "error",
                        "message": "Invalid plan. Use /api/plans to see options."}), 400

    return jsonify({"status": "ok", **result})


@pay_bp.route("/order-status/<order_id>", methods=["GET"])
def order_status(order_id: str):
    """Check the status of a payment order (public).

    Returns: status (pending/paid/expired/cancelled), api_key (if paid)
    """
    info = get_order(order_id)
    if not info:
        return jsonify({"status": "error", "message": "Order not found."}), 404

    return jsonify({"status": "ok", **info})
