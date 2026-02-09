"""
Build script — LEAKCHECK Server .exe
Uses PyInstaller to create a single-file executable for the server admin panel.
Run from the project root:  python build_server.py
"""

import PyInstaller.__main__
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.join(HERE, "server")

PyInstaller.__main__.run([
    os.path.join(SERVER_DIR, "server_app.py"),
    "--onefile",
    "--windowed",
    "--name", "LeakCheck_Server",
    "--icon", os.path.join(HERE, "logo.ico"),
    # Bundle all server modules
    "--add-data", f"{os.path.join(SERVER_DIR, 'config.py')};.",
    "--add-data", f"{os.path.join(SERVER_DIR, 'database.py')};.",
    "--add-data", f"{os.path.join(SERVER_DIR, 'auth.py')};.",
    "--add-data", f"{os.path.join(SERVER_DIR, 'logger.py')};.",
    "--add-data", f"{os.path.join(SERVER_DIR, 'routes_api.py')};.",
    "--add-data", f"{os.path.join(SERVER_DIR, 'routes_admin.py')};.",
    "--add-data", f"{os.path.join(SERVER_DIR, 'routes_payment.py')};.",
    "--add-data", f"{os.path.join(SERVER_DIR, 'routes_admin_web.py')};.",
    "--add-data", f"{os.path.join(SERVER_DIR, 'routes_referral.py')};.",
    "--add-data", f"{os.path.join(SERVER_DIR, 'binance_pay.py')};.",
    "--add-data", f"{os.path.join(SERVER_DIR, 'telegram_bot.py')};.",
    "--add-data", f"{os.path.join(SERVER_DIR, 'server.py')};.",
    "--add-data", f"{os.path.join(SERVER_DIR, 'server_config.json')};.",
    "--add-data", f"{os.path.join(SERVER_DIR, 'templates')};templates",
    "--add-data", f"{os.path.join(HERE, 'logo.ico')};.",
    # Hidden imports for Flask + our modules
    "--hidden-import", "flask",
    "--hidden-import", "flask.json",
    "--hidden-import", "jinja2",
    "--hidden-import", "config",
    "--hidden-import", "database",
    "--hidden-import", "auth",
    "--hidden-import", "logger",
    "--hidden-import", "routes_api",
    "--hidden-import", "routes_admin",
    "--hidden-import", "routes_payment",
    "--hidden-import", "routes_admin_web",
    "--hidden-import", "routes_referral",
    "--hidden-import", "binance_pay",
    "--hidden-import", "telegram_bot",
    "--hidden-import", "server",
    "--hidden-import", "requests",
    # Output
    "--distpath", os.path.join(HERE, "dist"),
    "--workpath", os.path.join(HERE, "build"),
    "--specpath", HERE,
    # Clean
    "--clean",
    "--noconfirm",
])

print("\n[OK] Server .exe built -> dist/LeakCheck_Server.exe")
