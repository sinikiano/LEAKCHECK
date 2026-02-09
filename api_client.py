"""
LEAKCHECK Client — API Communication
Handles all HTTP calls to the server.
"""

import time
import gzip
import json as _json
import requests
from config_client import SERVER_URL, get_api_key, get_hwid


class APIError(Exception):
    """Raised when the server returns a meaningful error (401/403/429)."""
    def __init__(self, message: str, code: str = "error"):
        self.code = code
        super().__init__(message)


def _headers() -> dict:
    return {"X-API-Key": get_api_key(), "X-HWID": get_hwid(), "X-Platform": "desktop",
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip"}


def _url(path: str) -> str:
    return f"{SERVER_URL}{path}"


# ── Retry / backoff settings ─────────────────
_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0  # seconds


def _check_error(r: requests.Response):
    """Raise APIError for 401/403/429 responses with server message."""
    if r.status_code in (401, 403):
        try:
            data = r.json()
            msg = data.get("message", data.get("error", "Access denied"))
            code = data.get("error", "error")
        except Exception:
            msg = f"HTTP {r.status_code}"
            code = "error"
        raise APIError(msg, code=code)
    # 429 is handled by retry logic; only raise if retries are exhausted
    if r.status_code == 429:
        try:
            data = r.json()
            msg = data.get("message", "Rate limit exceeded")
            code = data.get("error", "rate_limit")
        except Exception:
            msg = f"HTTP 429 — Rate limit exceeded"
            code = "rate_limit"
        raise APIError(msg, code=code)


def _request_with_retry(method: str, url: str, **kwargs) -> requests.Response:
    """Make an HTTP request with automatic retry on 429 (rate limit).
    Uses exponential backoff with Retry-After header support.
    """
    last_resp = None
    for attempt in range(_MAX_RETRIES):
        r = method(url, **kwargs) if callable(method) else requests.request(method, url, **kwargs)
        if r.status_code != 429:
            return r
        last_resp = r
        # Respect Retry-After header if present
        retry_after = r.headers.get("Retry-After")
        if retry_after:
            try:
                wait = min(float(retry_after), 30.0)
            except ValueError:
                wait = _BACKOFF_BASE * (2 ** attempt)
        else:
            wait = _BACKOFF_BASE * (2 ** attempt)
        time.sleep(wait)
    # All retries exhausted — return last 429 response
    return last_resp


# ── Public endpoints ─────────────────────────

def ping() -> dict | None:
    """Returns server info or None on failure."""
    try:
        r = requests.get(_url("/api/ping"), timeout=5)
        return r.json()
    except Exception:
        return None


def get_messages() -> list[dict]:
    """Fetch server news/messages for display in client. Returns list of message dicts."""
    try:
        r = requests.get(_url("/api/messages"), timeout=5)
        if r.status_code == 200:
            return r.json().get("messages", [])
    except Exception:
        pass
    return []


def get_version() -> dict | None:
    """Returns { version, filename, sha256, changelog, date } or None."""
    try:
        r = requests.get(_url("/api/version"), timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def download_update(save_path: str) -> bool:
    """Download the latest update binary to save_path. Returns True on success."""
    try:
        r = requests.get(_url("/api/download"), timeout=120, stream=True)
        if r.status_code == 200:
            with open(save_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return True
    except Exception:
        pass
    return False


# ── Authenticated endpoints ──────────────────

def get_status() -> dict | None:
    try:
        r = _request_with_retry(requests.get, _url("/api/status"), headers=_headers(), timeout=10)
        _check_error(r)
        return r.json()
    except APIError:
        raise
    except Exception:
        return None


def get_key_info() -> dict | None:
    """Return key subscription info: plan, days_remaining, expires_at, etc."""
    try:
        r = _request_with_retry(requests.get, _url("/api/keyinfo"), headers=_headers(), timeout=10)
        _check_error(r)
        if r.status_code == 200:
            return r.json()
    except APIError:
        raise
    except Exception:
        pass
    return None


def check_combos(combo_lines: list[str], batch_size: int = 25000,
                 progress_cb=None) -> tuple[list[str], int, float]:
    """
    Send raw email:password combos to server in batches.
    Returns (not_found_combos, total_checked, elapsed_ms).
    progress_cb(checked_so_far, total) is called after each batch.
    """
    # Filter empty lines
    combos = [l.strip() for l in combo_lines if l.strip()]
    total = len(combos)
    if total == 0:
        return [], 0, 0.0

    not_found_combos: list[str] = []
    total_elapsed = 0.0
    checked = 0

    for i in range(0, total, batch_size):
        batch = combos[i : i + batch_size]
        try:
            # Gzip-compress the payload for faster transfer
            payload = _json.dumps({"combos": batch}).encode("utf-8")
            compressed = gzip.compress(payload, compresslevel=1)
            hdrs = _headers()
            hdrs["Content-Encoding"] = "gzip"

            r = _request_with_retry(
                requests.post,
                _url("/api/check"),
                headers=hdrs,
                data=compressed,
                timeout=180,
            )
            _check_error(r)  # raises APIError for 401/403 (429 handled by retry)
            if r.status_code == 200:
                data = r.json()
                not_found_combos.extend(data.get("not_found", []))
                total_elapsed += data.get("elapsed_ms", 0)
            else:
                # On error, treat entire batch as not-found
                not_found_combos.extend(batch)
        except APIError:
            raise  # let HWID / auth / rate-limit errors propagate
        except Exception:
            not_found_combos.extend(batch)

        checked += len(batch)
        if progress_cb:
            progress_cb(checked, total)

        # Small delay between batches to avoid hitting per-minute rate limit
        if i + batch_size < total:
            time.sleep(0.05)

    return not_found_combos, total, total_elapsed


# ── File download (private combos) ───────────

def list_files() -> list[dict] | None:
    """Return list of shared files from server, or None on error."""
    try:
        r = _request_with_retry(requests.get, _url("/api/files"), headers=_headers(), timeout=15)
        _check_error(r)
        if r.status_code == 200:
            return r.json().get("files", [])
    except APIError:
        raise
    except Exception:
        pass
    return None


def download_file(filename: str, save_path: str, progress_cb=None) -> bool:
    """
    Download a shared file from the server.
    progress_cb(downloaded_bytes, total_bytes) is called during download.
    Returns True on success.
    """
    try:
        r = requests.get(
            _url(f"/api/files/download/{filename}"),
            headers={"X-API-Key": get_api_key(), "X-HWID": get_hwid(), "X-Platform": "desktop"},
            timeout=300,
            stream=True,
        )
        if r.status_code != 200:
            return False

        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        with open(save_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
                downloaded += len(chunk)
                if progress_cb and total > 0:
                    progress_cb(downloaded, total)

        return True
    except Exception:
        return False


# ── Payment / Subscription purchase ──────────

def get_plans() -> list[dict] | None:
    """Fetch available subscription plans with prices from server."""
    try:
        r = requests.get(_url("/api/plans"), timeout=10)
        if r.status_code == 200:
            return r.json().get("plans", [])
    except Exception:
        pass
    return None


def create_order(plan: str, username: str = "") -> dict | None:
    """Create a new payment order. Returns order details or None."""
    try:
        r = requests.post(
            _url("/api/create-order"),
            json={"plan": plan, "username": username},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def check_order_status(order_id: str) -> dict | None:
    """Poll order payment status. Returns order info or None."""
    try:
        r = requests.get(_url(f"/api/order-status/{order_id}"), timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


# ── Email search ─────────────────────────────

def search_email(email: str) -> dict:
    """
    Search for leaked credentials by email address.
    Returns dict with: results (list), count, searches_used, searches_remaining, daily_limit.
    Raises APIError on rate-limit or auth errors.
    """
    try:
        r = _request_with_retry(
            requests.post,
            _url("/api/search"),
            headers=_headers(),
            json={"email": email.strip()},
            timeout=30,
        )
        _check_error(r)
        if r.status_code == 200:
            return r.json()
        return {"status": "error", "message": f"HTTP {r.status_code}", "results": [], "count": 0}
    except APIError:
        raise
    except Exception as e:
        return {"status": "error", "message": f"Connection error: {e}", "results": [], "count": 0}


def get_search_quota() -> dict | None:
    """Return current search quota: used, remaining, limit."""
    try:
        r = _request_with_retry(requests.get, _url("/api/search/quota"), headers=_headers(), timeout=10)
        _check_error(r)
        if r.status_code == 200:
            return r.json()
    except APIError:
        raise
    except Exception:
        pass
    return None


# ── Usage Stats ──────────────────────────────

def get_user_stats() -> dict | None:
    """Return personal usage statistics for the current user."""
    try:
        r = _request_with_retry(requests.get, _url("/api/user/stats"), headers=_headers(), timeout=10)
        _check_error(r)
        if r.status_code == 200:
            return r.json()
    except APIError:
        raise
    except Exception:
        pass
    return None


# ── Referral System ──────────────────────────

def get_referral_code() -> dict | None:
    """Get the user's referral code."""
    try:
        r = _request_with_retry(requests.get, _url("/api/referral/code"), headers=_headers(), timeout=10)
        _check_error(r)
        if r.status_code == 200:
            return r.json()
    except APIError:
        raise
    except Exception:
        pass
    return None


def apply_referral_code(code: str) -> dict | None:
    """Apply a referral code to the current user's key."""
    try:
        r = _request_with_retry(
            requests.post,
            _url("/api/referral/apply"),
            headers=_headers(),
            json={"referral_code": code},
            timeout=10,
        )
        _check_error(r)
        if r.status_code == 200:
            return r.json()
        return r.json() if r.status_code < 500 else None
    except APIError:
        raise
    except Exception:
        pass
    return None


def get_referral_stats() -> dict | None:
    """Get referral stats for the current user."""
    try:
        r = _request_with_retry(requests.get, _url("/api/referral/stats"), headers=_headers(), timeout=10)
        _check_error(r)
        if r.status_code == 200:
            return r.json()
    except APIError:
        raise
    except Exception:
        pass
    return None
