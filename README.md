# LEAKCHECK

**Antipublic credential leak detection tool.**

LEAKCHECK allows you to verify large combo lists (email:password) against a centralized leak database to identify credentials that have already been exposed in public data breaches. Combos not found in the database are considered private and can be exported for further analysis.

---

## Downloads

| Platform | File | 
|----------|------|
| Windows  | [LeakCheck.exe](https://github.com/sinikiano/LEAKCHECK/releases/latest/download/LeakCheck.exe) |
| Android  | [LeakCheck-Android-v2.3.0.apk](https://github.com/sinikiano/LEAKCHECK/releases/latest/download/LeakCheck-Android-v2.3.0.apk) |

---

## Features

- **Bulk Combo Checking** -- Send up to 25,000 combos per batch against the server database
- **Email Search** -- Look up all leaked passwords associated with a given email address
- **Gzip Compression** -- Request payloads are compressed for faster transfers over slow connections
- **HWID-Locked Keys** -- API keys are bound per-platform (desktop / Android) to prevent sharing
- **Rate-Limit Retry** -- Automatic exponential backoff on 429 responses
- **Auto-Deduplication** -- Optionally strip duplicate lines before checking
- **Format Validation** -- Only valid `email:password` lines are sent to the server
- **Export Results** -- Save private (not-found) combos to a text file
- **Shared File Downloads** -- Access server-hosted combo files directly from the client
- **Subscription Plans** -- Purchase keys with USDT via Binance Pay
- **Referral System** -- Earn bonus subscription days by referring other users

---

## How It Works

1. Obtain an API key (purchase directly from the client app or contact the admin).
2. Load a combo list file (`email:password` format, one per line).
3. The client validates, deduplicates, and sends combos in compressed batches.
4. The server checks each combo against its leak database and returns the results.
5. Combos **not found** in the database are returned as private -- export them as needed.

---

## Pricing

API keys can be purchased directly from within the desktop or Android client using USDT (Tether) via Binance Pay. No external website or manual contact required -- the entire process is automated.

| Plan       | Duration | Price (USDT) |
|------------|----------|-------------:|
| 1 Month    | 30 days  |        10.00 |
| 3 Months   | 90 days  |        25.00 |
| 6 Months   | 180 days |        45.00 |
| 1 Year     | 365 days |        80.00 |
| Lifetime   | Unlimited|       150.00 |

**How to purchase:**

1. Open the client app and navigate to the **Buy Key** tab.
2. Enter a username and select a subscription plan.
3. A unique USDT payment address and amount will be generated.
4. Send the exact amount to the provided address on the specified network.
5. Once the payment is confirmed on-chain, your API key is issued automatically.
6. The key is displayed in the app and ready to use immediately.

Payments are monitored automatically. Referral bonuses are available -- refer other users to earn additional subscription days on your account.

---

## System Requirements

| Platform | Requirement |
|----------|-------------|
| Windows  | Windows 10 or later, x64 |
| Android  | Android 8.0 (API 26) or later |

No installation required. The Windows client is a standalone portable executable. The Android app is a standard APK.

---

## Version

Current release: **v2.3.0**

---

## Contact

Developer: **BionicSailor**
Telegram: [@BionicSailor](https://t.me/BionicSailor)