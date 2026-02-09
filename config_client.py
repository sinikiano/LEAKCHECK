"""
LEAKCHECK Client — Configuration
Stores API key locally; server URL is obfuscated.
"""

import os
import json
import base64

# ── Hidden server URL (base64) ──────────────
_ENC = "aHR0cDovLzE4NS4yNDkuMTk3LjIzMTo1MDAw"
SERVER_URL = base64.b64decode(_ENC).decode()

# ── Local config file ───────────────────────
import sys as _sys
if getattr(_sys, 'frozen', False):
    _CFG_DIR = os.path.dirname(_sys.executable)
else:
    _CFG_DIR = os.path.dirname(os.path.abspath(__file__))
_CFG_PATH = os.path.join(_CFG_DIR, "client_config.json")

_DEFAULTS = {
    "api_key": "",
}


def load_config() -> dict:
    if os.path.exists(_CFG_PATH):
        try:
            with open(_CFG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return dict(_DEFAULTS)


def save_config(cfg: dict):
    with open(_CFG_PATH, "w") as f:
        json.dump(cfg, f, indent=4)


def get_api_key() -> str:
    return load_config().get("api_key", "")


def set_api_key(key: str):
    cfg = load_config()
    cfg["api_key"] = key
    save_config(cfg)


# ── Hardware ID (unique per machine) ────────
_cached_hwid: str | None = None


def get_hwid() -> str:
    """Generate a unique hardware fingerprint for this PC (cached).

    Uses BIOS UUID via PowerShell (primary) or wmic (legacy fallback).
    CREATE_NO_WINDOW prevents console flash in frozen .exe builds.
    """
    global _cached_hwid
    if _cached_hwid is not None:
        return _cached_hwid

    import hashlib
    import subprocess

    # Hide console window when running from a windowed .exe
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0
    cflags = 0x08000000  # CREATE_NO_WINDOW

    # Method 1: PowerShell (reliable on Windows 10/11, wmic deprecated)
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-NoLogo", "-Command",
             "(Get-CimInstance Win32_ComputerSystemProduct).UUID"],
            startupinfo=si, creationflags=cflags,
            stderr=subprocess.DEVNULL, timeout=10,
        ).decode().strip()
        if out and len(out) > 8 and out.upper() not in ("", "NONE", "N/A"):
            _cached_hwid = hashlib.sha256(out.encode()).hexdigest()[:32]
            return _cached_hwid
    except Exception:
        pass

    # Method 2: wmic (legacy, still works on older Windows)
    try:
        out = subprocess.check_output(
            "wmic csproduct get uuid", shell=True,
            startupinfo=si, creationflags=cflags,
            stderr=subprocess.DEVNULL, timeout=10,
        ).decode().strip()
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        uuid_val = lines[-1] if lines else ""
        if uuid_val and uuid_val.upper() != "UUID" and len(uuid_val) > 8:
            _cached_hwid = hashlib.sha256(uuid_val.encode()).hexdigest()[:32]
            return _cached_hwid
    except Exception:
        pass

    # Method 3: hostname + username (last resort)
    import platform
    import getpass
    raw = f"{platform.node()}-{getpass.getuser()}"
    _cached_hwid = hashlib.sha256(raw.encode()).hexdigest()[:32]
    return _cached_hwid


# Current client version  ── bump this when building new releases
CLIENT_VERSION = "2.3.0"
