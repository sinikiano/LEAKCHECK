<p align="center">
  <img src="https://img.shields.io/badge/version-2.3.0-00e5ff?style=for-the-badge&labelColor=0d1117" />
  <img src="https://img.shields.io/badge/platforms-Windows%20%7C%20Android-00e5ff?style=for-the-badge&labelColor=0d1117" />
  <img src="https://img.shields.io/badge/status-Active-22c55e?style=for-the-badge&labelColor=0d1117" />
  <img src="https://img.shields.io/github/downloads/sinikiano/LEAKCHECK/total?style=for-the-badge&color=00e5ff&labelColor=0d1117" />
</p>

<h1 align="center">🔒 LEAKCHECK</h1>

<p align="center">
  <b>High-performance antipublic database checker with email search, subscription management, and cross-platform support.</b>
</p>

<p align="center">
  <a href="https://github.com/sinikiano/LEAKCHECK/releases/latest">⬇️ Download Latest Release</a> &nbsp;•&nbsp;
  <a href="https://t.me/BionicSailor">💬 Telegram Support</a>
</p>

---

## 📥 Downloads

| Platform | File | Description |
|----------|------|-------------|
| **Windows** | [`LeakCheck.exe`](https://github.com/sinikiano/LEAKCHECK/releases/latest/download/LeakCheck.exe) | Standalone desktop client (.exe) |
| **Android** | [`LeakCheck.apk`](https://github.com/sinikiano/LEAKCHECK/releases/latest/download/LeakCheck.apk) | Android app (APK) |

> No installation required — download, enter your API key, and start checking.

---

## ⚡ Features

### Core
- **Antipublic Checker** — Check combolists against a database of 23M+ known credentials
- **Email Search** — Look up leaked passwords by email address with instant results
- **Real-time Database Updates** — Uploaded combos are added to the database in real-time during checks
- **Cross-Platform** — Full-featured clients for Windows and Android with feature parity
- **Shared File Downloads** — Access shared resources directly from the app

### Performance
- **Batch Processing** — Files processed in optimized 10K-combo chunks with real-time progress
- **Optimized Database** — SQLite with WAL mode, memory-mapped I/O, 2GB mmap, and 64MB page cache
- **Smart Deduplication** — Auto-remove duplicate lines before checking to save quota and time
- **Accurate Table Sizes** — Database table sizes calculated precisely using `page_count` and `page_size` PRAGMA

### Security
- **HWID Lock** — Each API key is bound to your device on first use — one PC + one phone per key
- **Encrypted Communication** — All API calls authenticated with your personal key
- **Smart Rate Limiting** — Per-key, per-minute rate limiter (300 req/min) with automatic retry and backoff
- **Retry-After Support** — Client automatically retries on 429 responses using exponential backoff

### Subscriptions & Payments
- **Flexible Plans** — 1 Month, 3 Months, 6 Months, 1 Year, or Lifetime
- **Crypto Payments** — Pay with USDT (TRC20) directly in-app via Binance Pay
- **Auto-Fulfillment** — API key generated and delivered automatically once payment is confirmed
- **In-App Status** — Track your plan, remaining days, and daily search quota at a glance

### Referral System
- **Referral Codes** — Share your unique referral code with friends
- **Bonus Days** — Earn bonus subscription days when someone uses your referral code
- **In-App Tracking** — View your referral stats and earned bonuses directly in the app

### Admin Features
- **Web Dashboard** — Full admin panel accessible via browser at `/panel`
- **Activity Logging** — All client activity (searches, checks, downloads) logged with IP, duration, and timestamps
- **Server Log** — Real-time request logging in the admin GUI with client activity visibility
- **Telegram Notifications** — Admin alerts for key activations, HWID mismatches, and payments
- **Database Management** — Vacuum, optimize, rebuild indexes, repack with larger pages
- **Server Messages** — Broadcast messages/news to all connected clients

---

## 🖥️ Desktop Client (Windows)

| Tab | Description |
|-----|-------------|
| **Check** | Load a combolist (.txt), validate format, check against the database. Export private (not-found) combos. Real-time progress bar with hit rate stats. |
| **Search** | Search for leaked passwords by email. View results in a table. Copy or export all results. Daily quota tracking (30/day). |
| **Downloads** | Browse and download shared files from the server with progress tracking. |
| **Buy Key** | Purchase a subscription plan with USDT. Auto-poll payment status. Key delivered instantly on confirmation. |
| **Stats** | Personal usage statistics — total checks, searches, files downloaded, account age, referral stats. |
| **Referral** | View your referral code, share with friends, apply a friend's code, see referral stats. |
| **Log** | Advanced activity log viewer with level filtering (INFO/OK/ERR), text search, export, and clipboard copy. |
| **About** | App info, feature summary, and developer contact. |

**UI:** Dark theme with monospace font, red/cyan accents, real-time connection status indicator.

---

## 📱 Android App

| Tab | Description |
|-----|-------------|
| **Check** | Pick combo files via Android's file picker. Same batch processing as desktop. Export results to any location. |
| **Search** | Email search with quota display. Selectable & copyable results. |
| **Downloads** | Browse server files. Download to your chosen folder via Android's save dialog. |
| **Buy Key** | Full payment flow — select plan, pay in USDT, receive key automatically. |
| **About** | App details with Telegram deep link to developer. |

**UI:** Material 3 design with bottom navigation, dark theme matching desktop, monospace typography throughout.

---

## 🔑 Getting Started

1. **Download** the client for your platform from [Releases](https://github.com/sinikiano/LEAKCHECK/releases/latest)
2. **Get an API Key** — Purchase a plan in-app (Buy Key tab) or contact [@BionicSailor](https://t.me/BionicSailor) on Telegram
3. **Enter your key** in the API Key field and click **Save**
4. **Start checking** — Load a combolist or search by email

---

## 📋 Changelog

### v2.3.0 — Database, Logging & Rate Limit Fix
- ✅ Fixed real-time database updates — combos now saved to DB during checks
- ✅ Fixed table size display — accurate MB sizes using PRAGMA page_count/page_size
- ✅ Fixed `get_db_stats()` returning 0 total records — now reads `leak_data` count correctly
- ✅ Fixed server activity logs — all client actions (search, check, download) now visible in Server Log
- ✅ Added Flask `after_request` logging hook for full request visibility in admin GUI
- ✅ Fixed rate limiter default fallback (was 30, now correctly 300 req/min)
- ✅ Added `Retry-After` header to all 429 responses
- ✅ Client-side automatic retry with exponential backoff on rate limit (up to 3 retries)
- ✅ Added 150ms inter-batch delay to prevent rate limit spikes during bulk checks
- ✅ Updated build scripts — server build now includes `routes_admin_web`, `routes_referral`, `telegram_bot`, and templates
- ✅ Android app updated with retry interceptor and raw combo support
- ✅ All versions synced to 2.3.0 across desktop, server, and Android

### v2.2.1 — Stability & Security Update
- ✅ Android app release with full feature parity
- ✅ Per-platform HWID support (use same key on PC + phone)
- ✅ Improved error handling with meaningful server messages on Android
- ✅ Custom app icon for Android
- ✅ Fixed critical shutdown authentication bug
- ✅ Capped log entries to prevent memory leak in long sessions
- ✅ Error handling on all file exports
- ✅ Cleaned up redundant imports for faster load

### v2.2.0 — Major Feature Release
- ✅ Email search feature with daily quota (30/day)
- ✅ Binance USDT payment integration with auto-fulfillment
- ✅ Subscription plans (1M / 3M / 6M / 1Y / Lifetime)
- ✅ Auto-remove duplicate combos
- ✅ Email:password format validation
- ✅ HWID lock (PowerShell-based on Windows)
- ✅ Database optimization (BLOB WITHOUT ROWID)
- ✅ Advanced Log tab with search & filter
- ✅ Server messages broadcast system
- ✅ Shared file downloads

### v2.0.0 — Initial Public Release
- ✅ Antipublic checker with SHA-256 hashed storage
- ✅ Multi-key authentication with rate limiting
- ✅ Activity logging & admin dashboard
- ✅ Dark-themed desktop GUI
- ✅ Batch processing with progress tracking
- ✅ Export results to file

---

## ⚠️ Legal Disclaimer

This tool is provided for **educational and research purposes only**. Users are solely responsible for ensuring compliance with all applicable laws and regulations in their jurisdiction. The developer assumes no liability for misuse.

---

<p align="center">
  <b>Developed by BionicSailor</b><br>
  <a href="https://t.me/BionicSailor">Telegram: @BionicSailor</a>
</p>
