# 🚀 Super Telegram Forwarder Bot

An asynchronous, high-performance Telegram Forwarder Bot built with **Python 3.10+**, **aiogram 3.x**, and **SQLite**. 

Forward messages effortlessly across any chat combination with full content filtering, clean clone / native forward options, automatic text transformations, media-group (album) batching, and an interactive inline UI.

---

## 🌟 Core Features

- 🔄 **Universal Forwarding Matrix**:
  - **Channel ➔ Channel**
  - **Group ➔ Channel**
  - **Channel ➔ Group**
  - **Group ➔ Group**
  - Full support for **Forum Topics / Thread IDs**.

- 🧼 **Dual Forwarding Modes**:
  - **Clean Copy (Clone):** Strips the *"Forwarded from"* tag so messages look 100% native.
  - **Native Forward:** Preserves original sender/channel header credits.

- 🖼️ **Media Group (Album) Batching**:
  - Automatically batches multi-photo and multi-video album posts so they are forwarded together without splitting or duplicating.

- 🎯 **Advanced Content & Media Filtering**:
  - Toggle specific media types per route: *Text, Photos, Videos, Documents, Audio, Voice notes, GIFs/Animations, Stickers, Polls*.
  - **Keyword Whitelist:** Forward only messages containing specific keywords or phrases.
  - **Keyword Blacklist:** Automatically block and skip spam, scam links, or unwanted phrases.

- ✨ **Smart Text Transformation & Branding**:
  - **Header & Footer:** Inject custom channel links, branding, watermarks, or promotion text.
  - **Word & Link Replacement:** Find and replace old referral links, text patterns, or usernames (supports Regex!).
  - **Auto-Strip Options:** One-click removal of external URLs and `@usernames`.

- 🛡️ **Anti-Flood & Resilience**:
  - SQLite persistent database (`aiosqlite`) — all routes, settings, and stats survive restarts.
  - Automatic backoff and retry queue handling Telegram API `FloodWait` (Rate limit) errors.
  - Optional Admin-Only restriction to protect bot from unauthorized usage.

---

## 📋 Bot Commands

| Command | Description |
|---|---|
| `/start` | Open the interactive dashboard with bot status & quick action buttons |
| `/newroute` or `/add` | Start the step-by-step interactive wizard to create a forwarding route |
| `/routes` or `/list` | View, manage, pause/resume, configure filters, or delete routes |
| `/stats` | View live forwarding metrics (total forwarded, filtered, errors, active routes) |
| `/ping` | Check bot health and Telegram API response latency |
| `/help` | Detailed guide with permissions and chat ID setup instructions |

---

## 🛠️ Quickstart Installation & Setup

### 1. Clone & Install Dependencies

Ensure you have **Python 3.10+** installed:

```bash
# Install required Python packages
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` with your values:

```ini
# Bot Token obtained from @BotFather
BOT_TOKEN=123456789:ABCDefGhIJKlmNoPQRsTUVwxyZ

# Telegram User IDs of administrators allowed to configure the bot (comma-separated)
ADMIN_IDS=123456789,987654321

# Database file location
DB_PATH=data/forwarder.db

# Restrict bot management to ADMIN_IDS (true/false)
ADMINS_ONLY=true

# Default forward mode ("copy" or "forward")
DEFAULT_FORWARD_MODE=copy
```

> **💡 How to find your Telegram User ID:** Send `/start` to `@userinfobot` or `@JsonDumpBot` on Telegram.

---

## 📢 Telegram Permissions Guide

For the bot to forward messages, configure the following permissions:

### 1. Source Chat (Where messages originate):
- **Channel:** Add the bot as an **Administrator** with at least *Read / View Messages* permission.
- **Group / Supergroup:** 
  - Add the bot to the group.
  - Either promote the bot to **Administrator**, OR disable **Group Privacy** in `@BotFather` (`/mybots` ➔ Select your bot ➔ `Bot Settings` ➔ `Group Privacy` ➔ `Turn off`).

### 2. Destination Chat (Where messages are sent):
- **Channel:** Add the bot as an **Administrator** with **Post Messages / Send Messages** permission.
- **Group / Supergroup:** Add the bot as an **Administrator** or regular member with **Send Messages** permission.

---

## 🧭 4-Step Route Creation Wizard (For Any User)

Creating a forward route is simple and seamless:

1. Send `/newroute` or click **`➕ Add New Route`** from `/start`.
2. **Step 1:** Enter a friendly name for your route (e.g. `Crypto Signals to VIP`).
3. **Step 2:** Provide the **Source** chat:
   - Public Channel/Group username (e.g. `@cryptosignals` or `https://t.me/cryptosignals`), OR
   - Private invite link (e.g. `https://t.me/+join_hash`), OR
   - Numeric Chat ID (e.g. `-1001234567890`), OR
   - Forward a message directly from the source chat.
   - *Behind the scenes:* The system automatically auto-joins and connects to the source!
4. **Step 3:** Provide your **Destination** chat (where your bot is Admin with *Post Messages* permission).
5. **Step 4:** Choose **Clean Copy (Clone)** or **Native Forward**.
6. **Done!** The route is live immediately.

---

## 👤 Centralized Host Userbot (Bot Owner Setup)

Only the **bot owner** needs to configure the background Telegram account once. Regular users never need to log in or supply API keys.

1. Put your `API_ID` and `API_HASH` from [my.telegram.org](https://my.telegram.org) into `.env`:
   ```ini
   BOT_TOKEN=123456789:ABCDefGhIJKlmNoPQRsTUVwxyZ
   ADMIN_IDS=6367495275
   API_ID=12345678
   API_HASH=abcdef0123456789abcdef0123456789
   ```
2. Start the bot:
   ```bash
   python main.py
   ```
3. In Telegram, send `/userbot` and click **'🔑 Connect Host Telegram Account'**.
4. Enter your phone number and OTP code directly in the chat to complete host login.
5. All users can now forward from ANY public channel or private invite link without permission!

---

## ⚙️ Advanced Customization & Settings

Navigate to `/routes` ➔ Select your route:

- **🎯 Media & Content Filters:**
  - Enable / disable specific media formats (e.g. allow only Photos and Videos, ignore Voice notes and Stickers).
  - Enable **Strip Links** to clean out external URLs.
  - Enable **Strip Usernames** to remove `@mentions`.

- **✨ Customization & Branding:**
  - **Header:** Custom text automatically added above message text/captions.
  - **Footer:** Custom text automatically added below message text/captions.
  - **Find & Replace:** Add rules to swap affiliate tags, keywords, or sponsors (e.g. replace `https://old-link.com` with `https://my-affiliate-link.com`).
  - **Keyword Whitelist / Blacklist:** Filter posts based on trigger words.

---

## 🚀 Running the Bot

### Normal Run:
```bash
python main.py
```

### Running in Background (Linux / macOS):
```bash
nohup python main.py > bot.log 2>&1 &
```

### Running as a Systemd Service (Linux):
Create `/etc/systemd/system/telegram-forwarder.service`:
```ini
[Unit]
Description=Super Telegram Forwarder Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/Telegram Forwarder Bot
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-forwarder
sudo systemctl start telegram-forwarder
```

---

## 🧪 Running Automated Tests

Run the test suite to verify database operations, transformations, filters, and routing:

```bash
python test_bot_core.py
```

---

## 📁 Project Structure

```
Telegram Forwarder Bot/
│
├── .env.example                # Configuration variables template
├── requirements.txt            # Python dependencies
├── README.md                   # Full bot documentation & guides
├── test_bot_core.py            # Comprehensive unit & integration tests
│
├── bot/
│   ├── __init__.py             # Bot package
│   ├── config.py               # Settings loader & environment parser
│   ├── main.py                 # Bot entrypoint & polling orchestrator
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── db.py               # Async SQLite connection & schema migrations
│   │   └── models.py           # CRUD models for routes, filters, & stats
│   │
│   ├── handlers/
│   │   ├── __init__.py         # Router aggregation
│   │   ├── common.py           # /start, /help, /stats, /ping handlers
│   │   ├── routes_manager.py   # /routes, /newroute FSM wizard & route control
│   │   ├── settings_handler.py # Filters, Header/Footer, & Replacements UI
│   │   └── forwarder.py        # Core forwarding listener (posts & messages)
│   │
│   ├── middlewares/
│   │   ├── __init__.py
│   │   ├── auth.py             # Admin access control middleware
│   │   └── album.py            # Media group (album) batching middleware
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── transformer.py      # Keyword filter & text transformation engine
│   │   └── sender.py           # Message dispatcher with FloodWait retry queue
│   │
│   └── keyboards/
│       ├── __init__.py
│       └── inline.py           # Inline keyboards for interactive Telegram UI
```
