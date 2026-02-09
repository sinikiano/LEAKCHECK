"""
LEAKCHECK Server — Entry Point
Run:  python server.py
"""

import os
import sys
import gzip
import io
import logging
from flask import Flask, request, jsonify

from config import CONFIG, BASE_DIR
from database import init_db, init_referral_table
from routes_api import api_bp
from routes_admin import admin_bp
from routes_payment import pay_bp
from routes_admin_web import admin_web_bp
from routes_referral import referral_bp
from telegram_bot import start_telegram_bot, stop_telegram_bot
from binance_pay import start_payment_monitor, stop_payment_monitor


class GzipMiddleware:
    """WSGI middleware that transparently decompresses gzip-encoded request bodies."""
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        content_encoding = environ.get("HTTP_CONTENT_ENCODING", "").lower()
        if content_encoding == "gzip":
            try:
                raw = environ["wsgi.input"].read()
                decompressed = gzip.decompress(raw)
                environ["wsgi.input"] = io.BytesIO(decompressed)
                environ["CONTENT_LENGTH"] = str(len(decompressed))
                # Remove encoding header so Flask doesn't see it
                environ.pop("HTTP_CONTENT_ENCODING", None)
            except Exception:
                pass  # let Flask handle malformed data normally
        return self.app(environ, start_response)


def create_app():
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 256 * 1024 * 1024  # 256 MB upload limit
    app.secret_key = CONFIG.get("admin_web_secret", "change_me_to_a_random_secret")

    # Wrap app in gzip decompression middleware
    app.wsgi_app = GzipMiddleware(app.wsgi_app)

    # ── Jinja2 template filter: epoch → readable date ──
    from datetime import datetime as _dt, timezone as _tz
    @app.template_filter("epoch_to_date")
    def _epoch_to_date(value):
        try:
            return _dt.fromtimestamp(float(value), tz=_tz.utc).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(value)

    # Register blueprints
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(pay_bp)
    app.register_blueprint(admin_web_bp)
    app.register_blueprint(referral_bp)

    # ── Request logging (visible in Server Log tab) ──
    @app.after_request
    def log_request(response):
        # Skip /shutdown and static files
        path = request.path
        if path in ("/shutdown",) or path.startswith("/panel/static"):
            return response
        ip = request.remote_addr or "-"
        method = request.method
        status = response.status_code
        key_header = request.headers.get("X-API-Key", "")
        key_short = key_header[:12] + "..." if len(key_header) > 12 else key_header or "-"
        logging.info(f"{method} {path} → {status}  key={key_short}  ip={ip}")
        return response

    # Shutdown endpoint (used by server_app GUI) — requires admin key
    @app.route("/shutdown", methods=["POST"])
    def shutdown():
        key = request.headers.get("X-API-Key", "")
        if key != CONFIG["admin_key"]:
            return jsonify({"error": "Forbidden", "message": "Admin access only."}), 403
        func = request.environ.get("werkzeug.server.shutdown")
        if func:
            func()
            return jsonify({"status": "ok", "message": "Shutting down..."})
        # For newer Werkzeug that removed server.shutdown
        import signal
        os.kill(os.getpid(), signal.SIGINT)
        return jsonify({"status": "ok", "message": "Shutting down..."})

    # Init database tables
    init_db()
    init_referral_table()

    # Start background services
    start_payment_monitor()
    start_telegram_bot()

    return app


def setup_logging():
    log_path = os.path.join(BASE_DIR, CONFIG.get("log_file", "server.log"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.info("LEAKCHECK Server starting...")


if __name__ == "__main__":
    setup_logging()
    app = create_app()
    port = CONFIG.get("port", 5000)
    host = CONFIG.get("host", "0.0.0.0")
    debug = CONFIG.get("debug", False)
    logging.info(f"Admin key: {CONFIG['admin_key'][:12]}...")
    logging.info(f"Listening on {host}:{port}")
    app.run(host=host, port=port, debug=debug)
