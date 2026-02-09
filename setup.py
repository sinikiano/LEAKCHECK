"""
LEAKCHECK Server — Setup & Deploy Script
=========================================
Interactive wizard that:
  1. Prompts for all required configuration (admin key, port, Binance, Telegram, etc.)
  2. Writes server_config.json
  3. Installs Python dependencies
  4. Initialises the database
  5. Starts the server (Flask + Web Panel + Telegram Bot + Payment Monitor)

Run:
  python setup.py

All services start together — the web panel, Telegram bot, and payment monitor
are integrated into the Flask server process.
"""

import os
import sys
import json
import secrets
import subprocess
import shutil

# ──────────────────────────────────────────────
#  Paths
# ──────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.join(SCRIPT_DIR, "server")
CONFIG_FILE = os.path.join(SERVER_DIR, "server_config.json")
REQUIREMENTS = os.path.join(SERVER_DIR, "requirements.txt")
SERVER_ENTRY = os.path.join(SERVER_DIR, "server.py")

# ANSI colours (works in Windows 10+ and all Unix terminals)
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_CYAN = "\033[36m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_DIM = "\033[2m"


def _banner():
    print(f"""
{C_CYAN}{C_BOLD}╔══════════════════════════════════════════════════╗
║           LEAKCHECK  SERVER  SETUP               ║
║      Server  +  Web Panel  +  Telegram Bot       ║
╚══════════════════════════════════════════════════╝{C_RESET}
""")


def _prompt(label: str, default: str = "", secret: bool = False, required: bool = False) -> str:
    """Interactive prompt with optional default."""
    suffix = f" [{C_DIM}{default}{C_RESET}]" if default else ""
    if secret:
        suffix += f" {C_DIM}(input hidden){C_RESET}"
    while True:
        try:
            if secret:
                import getpass
                value = getpass.getpass(f"  {C_CYAN}{label}{C_RESET}{suffix}: ")
            else:
                value = input(f"  {C_CYAN}{label}{C_RESET}{suffix}: ")
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(1)
        value = value.strip()
        if not value and default:
            return default
        if not value and required:
            print(f"  {C_RED}This field is required.{C_RESET}")
            continue
        return value


def _prompt_int(label: str, default: int) -> int:
    while True:
        raw = _prompt(label, str(default))
        try:
            return int(raw)
        except ValueError:
            print(f"  {C_RED}Enter a valid number.{C_RESET}")


def _prompt_yn(label: str, default: bool = True) -> bool:
    d = "Y/n" if default else "y/N"
    raw = _prompt(f"{label} ({d})", "").lower()
    if not raw:
        return default
    return raw.startswith("y")


def _section(title: str):
    print(f"\n{C_BOLD}{C_GREEN}── {title} ──{C_RESET}\n")


# ──────────────────────────────────────────────
#  Gather Configuration
# ──────────────────────────────────────────────

def gather_config() -> dict[str, object]:
    """Interactive prompts → config dict."""

    # Load existing config if present
    existing: dict[str, object] = {}
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                existing = json.load(f)
            print(f"  {C_YELLOW}Existing config found at {CONFIG_FILE}{C_RESET}")
            if not _prompt_yn("Reconfigure? (No = keep existing and start)"):
                return existing
        except Exception:
            pass

    cfg: dict[str, object] = {}

    # ── Server ──
    _section("Server Settings")
    cfg["host"] = _prompt("Bind host", existing.get("host", "0.0.0.0"))
    cfg["port"] = _prompt_int("Port", existing.get("port", 5000))
    cfg["debug"] = _prompt_yn("Debug mode?", existing.get("debug", False))

    # ── Admin Key ──
    _section("Admin Authentication")
    default_admin = existing.get("admin_key", "")
    if not default_admin:
        default_admin = secrets.token_urlsafe(32)
        print(f"  {C_DIM}Auto-generated admin key: {default_admin}{C_RESET}")
    cfg["admin_key"] = _prompt("Admin API key", default_admin, required=True)

    # ── Web Panel Secret ──
    default_secret = existing.get("admin_web_secret", "")
    if not default_secret or default_secret == "change_me_to_a_random_secret":
        default_secret = secrets.token_urlsafe(32)
    cfg["admin_web_secret"] = _prompt("Web panel session secret", default_secret, required=True)
    cfg["admin_web_enabled"] = True

    # ── Database ──
    _section("Database")
    cfg["db_path"] = _prompt("Database file path", existing.get("db_path", "leakcheck.db"))

    # ── Rate Limits ──
    _section("Rate Limiting")
    cfg["rate_limit_per_minute"] = _prompt_int("Requests per minute per key", existing.get("rate_limit_per_minute", 300))
    cfg["daily_search_limit"] = _prompt_int("Daily email search limit per key", existing.get("daily_search_limit", 30))
    cfg["max_combo_batch"] = _prompt_int("Max combo batch size", existing.get("max_combo_batch", 50000))

    # ── Binance Payment ──
    _section("Binance Pay (USDT Payments)")
    print(f"  {C_DIM}Leave empty to disable automatic payments.{C_RESET}")
    cfg["binance_api_key"] = _prompt("Binance API key", existing.get("binance_api_key", ""))
    cfg["binance_api_secret"] = _prompt("Binance API secret", existing.get("binance_api_secret", ""), secret=True)
    cfg["usdt_address"] = _prompt("USDT deposit address", existing.get("usdt_address", ""))
    cfg["usdt_network"] = _prompt("USDT network (TRC20/BEP20/ERC20)", existing.get("usdt_network", "TRC20"))

    # ── Telegram Bot ──
    _section("Telegram Bot")
    print(f"  {C_DIM}Leave empty to disable Telegram integration.{C_RESET}")
    cfg["telegram_bot_token"] = _prompt("Telegram bot token (from @BotFather)", existing.get("telegram_bot_token", ""))
    cfg["telegram_admin_chat_id"] = _prompt("Admin Telegram chat ID", existing.get("telegram_admin_chat_id", ""))

    # ── Referral ──
    _section("Referral System")
    cfg["referral_bonus_days"] = _prompt_int("Referral bonus days", existing.get("referral_bonus_days", 7))

    # ── Logging ──
    cfg["log_file"] = _prompt("Log file name", existing.get("log_file", "server.log"))

    return cfg


# ──────────────────────────────────────────────
#  Write Config
# ──────────────────────────────────────────────

def write_config(cfg: dict[str, object]):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)
    print(f"\n  {C_GREEN}Config saved → {CONFIG_FILE}{C_RESET}")


# ──────────────────────────────────────────────
#  Install Dependencies
# ──────────────────────────────────────────────

def install_deps():
    _section("Installing Dependencies")
    if not os.path.isfile(REQUIREMENTS):
        print(f"  {C_YELLOW}No requirements.txt found, skipping.{C_RESET}")
        return

    python = sys.executable
    print(f"  {C_DIM}Using Python: {python}{C_RESET}")
    print(f"  {C_DIM}Installing from: {REQUIREMENTS}{C_RESET}\n")

    result = subprocess.run(
        [python, "-m", "pip", "install", "-r", REQUIREMENTS, "--quiet"],
        cwd=SERVER_DIR,
    )
    if result.returncode == 0:
        print(f"  {C_GREEN}Dependencies installed successfully.{C_RESET}")
    else:
        print(f"  {C_RED}pip install failed (exit {result.returncode}). Check output above.{C_RESET}")
        if not _prompt_yn("Continue anyway?", False):
            sys.exit(1)


# ──────────────────────────────────────────────
#  Verify Connectivity
# ──────────────────────────────────────────────

def verify_setup(cfg: dict[str, object]):
    _section("Verification")

    # Check Binance credentials
    if cfg.get("binance_api_key") and cfg.get("binance_api_secret"):
        print(f"  Binance API key: {C_GREEN}configured{C_RESET}")
        print(f"  USDT address:    {C_GREEN}{cfg.get('usdt_address', 'not set')}{C_RESET}")
    else:
        print(f"  Binance Pay:     {C_YELLOW}disabled (no API key){C_RESET}")

    # Check Telegram
    if cfg.get("telegram_bot_token"):
        print(f"  Telegram bot:    {C_GREEN}configured{C_RESET}")
        if cfg.get("telegram_admin_chat_id"):
            print(f"  Admin chat ID:   {C_GREEN}{cfg['telegram_admin_chat_id']}{C_RESET}")
        else:
            print(f"  Admin chat ID:   {C_YELLOW}not set (admin notifications disabled){C_RESET}")
    else:
        print(f"  Telegram bot:    {C_YELLOW}disabled{C_RESET}")

    # Web panel
    print(f"  Web panel:       {C_GREEN}http://{cfg.get('host', '0.0.0.0')}:{cfg.get('port', 5000)}/panel/{C_RESET}")
    print(f"  API base:        {C_GREEN}http://{cfg.get('host', '0.0.0.0')}:{cfg.get('port', 5000)}/api/{C_RESET}")
    print(f"  Admin key:       {C_DIM}{cfg['admin_key'][:16]}...{C_RESET}")


# ──────────────────────────────────────────────
#  Start Server
# ──────────────────────────────────────────────

def start_server():
    _section("Starting Server")
    print(f"  {C_DIM}Entry point: {SERVER_ENTRY}{C_RESET}")
    print(f"  {C_DIM}Services: Flask API + Web Panel + Telegram Bot + Payment Monitor{C_RESET}")
    print(f"  {C_GREEN}Press Ctrl+C to stop.{C_RESET}\n")
    print("=" * 60)

    try:
        # Run server.py as a subprocess so it inherits the correct config
        result = subprocess.run(
            [sys.executable, SERVER_ENTRY],
            cwd=SERVER_DIR,
        )
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print(f"\n  {C_YELLOW}Server stopped by user.{C_RESET}")
        sys.exit(0)


# ──────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────

def main():
    _banner()

    # Check Python version
    if sys.version_info < (3, 10):
        print(f"  {C_RED}Python 3.10+ required. Current: {sys.version}{C_RESET}")
        sys.exit(1)

    # Check server directory exists
    if not os.path.isdir(SERVER_DIR):
        print(f"  {C_RED}Server directory not found: {SERVER_DIR}{C_RESET}")
        print(f"  {C_DIM}Make sure setup.py is in the project root alongside the server/ folder.{C_RESET}")
        sys.exit(1)

    # Step 1: Gather config
    cfg = gather_config()

    # Step 2: Write config
    write_config(cfg)

    # Step 3: Install deps
    install_deps()

    # Step 4: Verify
    verify_setup(cfg)

    # Step 5: Start
    if _prompt_yn("\nStart the server now?"):
        start_server()
    else:
        print(f"\n  {C_GREEN}Setup complete.{C_RESET} Start manually with:")
        print(f"  {C_CYAN}cd server && python server.py{C_RESET}\n")


if __name__ == "__main__":
    main()
