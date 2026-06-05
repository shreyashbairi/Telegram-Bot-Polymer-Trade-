# Polymer Price Telegram Bot

A comprehensive Telegram bot system that scrapes polymer price data from trading groups, parses unstructured messages using intelligent regex and AI, and provides a 24/7 query interface with historical price analysis, comparisons, and statistics.

## 🚀 Features

### Core Functionality
- **24/7 Continuous Operation**: Bot responds to queries while scraper runs on a schedule
- **Intelligent Message Scraping**: Fetches messages from Telegram groups using Telethon
- **Incremental Updates**: Tracks last scraped message to avoid reprocessing
- **Hybrid Parsing**: Combines fast regex patterns with OpenAI GPT-4o-mini fallback
- **Smart Data Cleaning**: Removes emojis/trailing periods, rejects non-polymer junk (machinery, adverts), and normalizes names
- **21-Day Data Retention**: Automatically maintains rolling window of historical data
- **SQLite Storage**: Local database with efficient indexing and duplicate handling
- **Auto-Reconnect**: Telethon and Telegram bot connections recover from transient network issues
- **Whitespace-Clean State**: State file keys are stripped of whitespace on load and write

### Bot Commands
- `/start` - Welcome message with quick-access polymer menu
- `/help` - Comprehensive command reference and usage examples
- `/list` - Browse all available polymers with pagination
- `/search <name>` - Search for specific polymers by name
- `/clear` - Clear chat history for a fresh start
- `/daily [date]` - Show all polymers with prices for a specific day
- `/compare <polymer1> [polymer2] [date]` - Compare polymers or show price stats
- Direct text queries - Simply type a polymer name to get instant price history

### Advanced Features
- **Parentheses Syntax**: Handle multi-word polymer names using `(polymer name)` format
- **Hyperlinked References**: Clean message formatting with 🔗 emoji links to source messages
- **Partial Data Display**: Show available data even when comparisons have incomplete overlap
- **Price Statistics**: Calculate highest, lowest, mean, difference, and latest prices per day
- **Smart Normalization**: One identity per polymer regardless of case, spacing, hyphens or vendor wording, plus a `polymer_aliases.txt` file for genuine synonyms
- **Private Chat Only**: Bot only responds in private messages for security
- **User Access Control**: Optional whitelist to restrict bot access to specific user IDs
- **Message Link Tracking**: Every price entry linked to its source Telegram message

## 📋 Table of Contents

1. [Architecture](#architecture)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Quick Start](#quick-start)
6. [Usage Guide](#usage-guide)
7. [Command Reference](#command-reference)
8. [Run Modes](#run-modes)
9. [How It Works](#how-it-works)
10. [Database Schema](#database-schema)
11. [Deployment](#deployment)
12. [Troubleshooting](#troubleshooting)
13. [Monitoring OpenAI Credits](#monitoring-openai-credits)
14. [API Costs](#api-costs)
15. [Project Structure](#project-structure)

## 🏗️ Architecture

The system consists of five main components working together:

### 1. **Scraper** (`scraper.py`)
- Uses Telethon to connect to Telegram and fetch messages
- Supports both historical scraping (N days back) and incremental scraping (new messages only)
- Tracks last scraped message ID in `scraper_state.json` (per-chat, with metadata)
- Calls `_ensure_connected()` at the start of every cycle and per chat — prevents the "Cannot send requests while disconnected" cascade that happens when the MTProto connection dies during the long sleep between cycles
- Runs on a schedule (default: every 4 hours) in continuous mode
- Handles rate limiting and connection errors gracefully
- Retries in 5 minutes after a cycle-level failure (not the full interval)

### 2. **Parser** (`parser.py`)
- **Phase 1**: Fast regex patterns for well-formatted messages
  - 7 different regex patterns covering common formats
  - Uses `[ \t]` instead of `\s` to prevent multi-line matching
  - Extracts polymer names, prices, and status indicators
- **Phase 2**: AI-powered parsing for complex messages
  - OpenAI GPT-4o-mini analyzes unstructured text (60x cheaper than GPT-4)
  - Handles mixed languages (Uzbek, Russian, English)
  - Rate limiting with exponential backoff
- **Data Cleaning**: Removes emojis, trailing periods, and normalizes formatting

### 3. **Database** (`database.py`)
- SQLite database with efficient schema design
- Stores both original and normalized polymer names
- Message links for source reference
- Unique constraints prevent duplicate entries
- Indexed on polymer name and date for fast queries
- 21-day rolling window maintenance (old records auto-deleted each cycle)

### 4. **Bot** (`bot.py`)
- Python-telegram-bot v21+ framework
- HTTPXRequest configured with 20s connect / 30s read timeouts — resilient to transient DNS or wifi blips on 24/7 laptops
- Global error handler swallows handler-level network errors so one failed reply can't crash the process
- Startup waits for internet before connecting (prevents instant crash when laptop boots before wifi)
- HTML formatting for rich message display
- Interactive inline keyboard menus
- Pagination for long polymer lists
- Smart query matching with fuzzy search
- Private chat restriction for security

### 5. **Main Controller** (`main.py`)
- Orchestrates all components with asyncio
- Six run modes: `bot`, `scraper-loop`, `continuous`, `scrape`, `incremental`, `full`
- Command-line interface with arguments
- Concurrent execution of bot and scraper via `asyncio.gather`
- Graceful shutdown handling

## 📦 Prerequisites

- **Python 3.8 or higher**
- **Telegram Account** with API credentials (get from https://my.telegram.org)
  - Your personal account must be a member of all groups you want to scrape
  - The scraper uses YOUR account credentials to read messages
- **Telegram Bot Token** (create bot via @BotFather)
  - The bot operates independently and only needs to respond to private messages
  - The bot does NOT need to be added to the trading groups
- **OpenAI API Key** with active billing (get from https://platform.openai.com)
- **Access to polymer trading groups** (your account must be a member of each group)

## 🔧 Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd Telegram-Bot-Polymer-Trade-
```

### 2. Set Up a Virtual Environment (Recommended)

**Windows**:
```powershell
python -m venv venv
venv\Scripts\activate
```

**Linux/macOS**:
```bash
python3 -m venv venv
source venv/bin/activate
```

Always verify your shell prompt shows `(venv)` before running anything — if it doesn't, you're using the global Python and your installed packages may differ.

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

If anything looks stale after pulling updates:
```bash
pip install --upgrade python-telegram-bot telethon httpx openai python-dotenv
```

### 4. Set Up Configuration
Create a `.env` file in the root directory:

```env
# Telegram API Credentials (from https://my.telegram.org)
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE=+1234567890
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_IDS=-1001234567890,-1002345678900

# Bot Access Control (optional - comma-separated list of user IDs)
# Leave empty to allow all users, or specify user IDs to restrict access
ALLOWED_USER_IDS=123456789,987654321

# OpenAI API Credentials
OPENAI_API_KEY=sk-proj-...
OPENAI_ORG_ID=org-...

# Database
DATABASE_PATH=polymer_prices.db
```

**Note on whitespace**: Spaces between comma-separated chat IDs are now stripped automatically in `config.py`, so both `-1001,-1002` and `-1001, -1002` work. Earlier versions treated them as different keys in the state file, causing silent data loss for chats whose IDs happened to be entered with leading spaces.

### 5. Security Note
The `.env` file is automatically ignored by git to protect your credentials. Never commit API keys to version control.

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `TELEGRAM_API_ID` | Telegram API ID | `12345678` |
| `TELEGRAM_API_HASH` | Telegram API hash | `abcdef123456...` |
| `TELEGRAM_PHONE` | Your phone number | `+971501234567` |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | `123456:ABC...` |
| `TELEGRAM_CHAT_IDS` | Group chat IDs (comma-separated) | `-1001234,-1002345` |
| `ALLOWED_USER_IDS` | User IDs who can use bot (optional, comma-separated) | `123456789,987654321` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-proj-...` |
| `OPENAI_ORG_ID` | OpenAI organization ID | `org-...` |
| `DATABASE_PATH` | SQLite database file path | `polymer_prices.db` |

### Scraping Configuration (in `config.py`)

| Constant | Default | Description |
|----------|---------|-------------|
| `DATA_RETENTION_DAYS` | `21` | Rolling window; records older than this are deleted each cycle |
| `SCRAPE_INTERVAL_HOURS` | `4` | How often the scheduled scraper runs in continuous mode |

### Getting Telegram Chat IDs

1. Add your account to the target group
2. Forward a message from the group to @userinfobot
3. The bot will show you the chat ID (starts with `-100`)

### Restricting Bot Access to Specific Users

By default, the bot responds to all users who message it privately. To restrict access to specific users only:

1. **Get User IDs**: Send a message from each authorized user to @userinfobot
2. **Update .env**: Add the user IDs (comma-separated) to `ALLOWED_USER_IDS`
   ```env
   ALLOWED_USER_IDS=123456789,987654321,555666777
   ```
3. **Leave Empty for No Restrictions**: If `ALLOWED_USER_IDS` is empty or not set, the bot will respond to all users
4. **Unauthorized User Experience**: Users not in the list will receive "Sorry, you are not authorized to use this bot." message

## 🚦 Quick Start

### First Time Setup

1. **Authenticate with Telegram**:
   ```bash
   python main.py scrape --days 21
   ```
   - Telethon will prompt for a verification code
   - Check your Telegram app for the code
   - Enter it in the terminal
   - A session file (`polymer_scraper_session.session`) is created — only needed once

2. **Run in Continuous Mode** (the normal 24/7 operation):
   ```bash
   python main.py continuous --interval 4
   ```
   - Performs initial incremental scrape
   - Starts the Telegram bot (responds 24/7)
   - Starts the scheduled scraper (runs every 4 hours)
   - Both services run concurrently until stopped with Ctrl+C

3. **Test the Bot**:
   - Open Telegram and search for your bot username
   - Start a private chat
   - Type `/start` to see the welcome message
   - Try queries like a polymer code (e.g. `0120`) or `/list`

### Fresh-Start Procedure

If your database looks incomplete, is corrupted, or you're switching to a new set of groups, a clean reset is:

```bash
# Stop any running instance first (Ctrl+C)
del polymer_prices.db          # or rm on Linux/macOS
del scraper_state.json         # forces scraper to re-pull the last 21 days

python main.py continuous --interval 4
```

**Do NOT delete** `polymer_scraper_session.session` — that's your Telethon authentication. Deleting it forces a fresh SMS-code re-authentication.

### What to Expect on First Run After a Fresh Start

1. Telethon connects using the existing session — no SMS prompt.
2. `Initial incremental scrape...` — since there's no `scraper_state.json`, every chat falls into the "no prior state" branch and pulls 21 days of history.
3. For each configured chat: `Scraping chat: -100... (no prior state — fetching last 21 days)` followed by `Scanned N, processed M text, found K entries...` progress lines every 10 text messages.
4. The initial scrape takes **significantly longer** than subsequent cycles — typically 10-30 minutes across a dozen active chats. All 21 days × N chats are being parsed in one pass.
5. When that completes: `Bot is running and ready to respond to user queries!`
6. The scraper then sleeps until the next 4-hour mark. Subsequent incremental scrapes are fast (seconds to a minute).
7. `scraper_state.json` is recreated cleanly with no whitespace in keys.

## 📖 Usage Guide

### For End Users (Telegram Bot)

#### Getting Started
1. Find the bot in Telegram using its username
2. Start a private chat (bot won't respond in groups)
3. Type `/start` to see the welcome message and polymer menu

#### Querying Prices

**Method 1: Direct Text Query**
```
0120
```
Response shows price history for the last 7 days.

**Method 2: Interactive Menu**
```
/list
```
Browse polymers and click to see prices.

**Method 3: Search**
```
/search 2119
```
Find all polymers matching "2119".

#### Viewing All Polymers for a Day
```
/daily
```
Shows all polymers with prices for the latest day with data.

```
/daily 23.04.26
```
Shows all polymers with prices for a specific date (DD.MM.YY).

#### Comparing Polymers

**Single polymer, 7-day high/low**:
```
/compare 0120
```

**Two polymers over 7 days**:
```
/compare 0120 0220
```

**Multi-word names** (use parentheses):
```
/compare (2119 Iran) (2119 Arya)
```

**Specific date**:
```
/compare 0120 23.04.26
/compare (2119 Iran) (2119 Arya) 23.04.26
```

**Partial data display**: Comparisons show data even when one polymer has missing days, explicitly noting "No data" for gaps.

### For Administrators (System Operation)

#### Run Modes

See [Run Modes](#run-modes) section for detailed information on each mode.

**Production (Recommended)**:
```bash
# Initial data collection (only needed if you want to skip waiting on the first cycle)
python main.py scrape --days 21

# Normal 24/7 operation
python main.py continuous --interval 4
```

**Development**:
```bash
# Test scraping only
python main.py scrape --days 7

# Test bot only (with existing data)
python main.py bot

# Run scraper on its own in a separate process
python main.py scraper-loop --interval 4
```

**One-time update**:
```bash
# Scrape only new messages since last run
python main.py incremental
```

## 🎯 Command Reference

### User Commands (In Bot Chat)

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Welcome message with polymer menu | `/start` |
| `/help` | Show all commands and usage examples | `/help` |
| `/list` | Browse all available polymers | `/list` |
| `/search <query>` | Search for polymers by name | `/search 2119` |
| `/clear` | Clear chat history | `/clear` |
| `/daily [date]` | All polymers with prices for a day | `/daily 23.04.26` |
| `/compare <p1> [p2] [date]` | Compare polymers or price stats | `/compare 0120 0220` |
| `<polymer name>` | Direct query for 7-day price history | `0120` |

### System Commands (Command Line)

| Command | Description |
|---------|-------------|
| `python main.py continuous --interval N` | Run bot + scheduled scraper together (every N hours) — **recommended** |
| `python main.py bot` | Start bot only (requires existing data) |
| `python main.py scraper-loop --interval N` | Start scraper loop only (no bot) |
| `python main.py scrape --days N` | One-time historical scrape of N days |
| `python main.py incremental` | One-time incremental scrape + cleanup |
| `python main.py full` | One-time 21-day scrape, then start bot |

## 🔄 Run Modes

### 1. Continuous Mode (Recommended for Production)
```bash
python main.py continuous --interval 4
```

**What it does**:
- Loads state from `scraper_state.json`
- Performs initial incremental scrape to catch up on new messages
- Starts the Telegram bot (responds to user queries 24/7)
- Starts the scheduled scraper (fetches new messages every N hours)
- Both services run concurrently using `asyncio.gather()`

**When to use**: Production deployment, 24/7 operation.

### 2. Scraper-Loop Mode (Scraper Only)
```bash
python main.py scraper-loop --interval 4
```

**What it does**:
- Starts only the scraper's scheduled loop (no bot)
- Useful when you want to run the bot in a separate process or on a different machine

**When to use**: Distributed deployments where scraping and bot handling are separate services.

### 3. Historical Scrape Mode
```bash
python main.py scrape --days 21
```

**What it does**:
- Scrapes N days of historical messages from Telegram groups
- Parses and stores all polymer prices in the database
- Updates `scraper_state.json`
- Exits after completion

**When to use**: Initial setup, backfilling data, testing scraper.

### 4. Bot Only Mode
```bash
python main.py bot
```

**What it does**:
- Starts only the Telegram bot
- Responds to user queries using existing database
- Does not scrape any new messages

**When to use**: Testing bot functionality, when scraping is handled separately.

### 5. Incremental Scrape Mode
```bash
python main.py incremental
```

**What it does**:
- Loads last scraped message ID from `scraper_state.json`
- Scrapes only messages newer than the last ID (per chat)
- Updates the tracking file with new last message IDs
- Runs 21-day cleanup
- Exits after completion

**When to use**: Manual updates, cron jobs, testing incremental logic.

### 6. Full Mode
```bash
python main.py full
```

**What it does**:
- Scrapes 21 days of historical data
- Immediately starts the bot after scraping completes
- Does NOT use scheduled scraping (one-time scrape only)

**When to use**: First-time setup in environments without continuous operation.

## 🔍 How It Works

### Message Scraping Process

1. **Connection**: Telethon connects to Telegram using your API credentials
2. **Authentication**: Session file stores authentication (persists across runs)
3. **Connection check**: Before each cycle and per chat, `_ensure_connected()` verifies the client socket is alive and reconnects if needed
4. **Message Fetching**:
   - Historical mode: Fetches messages from N days ago to present
   - Incremental mode: Fetches only messages with ID > `last_scraped_id` for that chat
5. **Tracking**: Saves the highest message ID per chat to `scraper_state.json` in a finally-block, so partial progress is preserved even if a cycle crashes
6. **Scheduling**: In continuous mode, repeats every N hours

### State File Format (`scraper_state.json`)

```json
{
  "chats": {
    "-1001234567890": {
      "last_message_id": 54321,
      "last_scrape_time": "2026-04-24T10:30:00"
    },
    "-1002345678900": {
      "last_message_id": 98765,
      "last_scrape_time": "2026-04-24T10:30:02"
    }
  },
  "last_cleanup_time": "2026-04-24T10:30:15",
  "data_retention_days": 14
}
```

On load, any chat-id keys containing whitespace are automatically cleaned and merged with the whitespace-free version. If a legacy `last_scraped_message.json` exists (flat `{chat_id: msg_id}` format), it's migrated to the new format on first run.

### Parsing Logic

#### Phase 1: Fast Regex Parsing

The parser tries 7 different regex patterns optimized for common formats:

```python
# Pattern examples (simplified):
"0120          14500"     # Polymer with price
"2119 Iran     BOR"       # Polymer with status
"J150 14.900"             # With decimal point
"0209 🔴 AKPC  17000"     # With emojis (removed)
```

**Key feature**: Uses `[ \t]` instead of `\s` in patterns to prevent matching across newlines.

#### Phase 2: AI-Powered Parsing

If regex fails to extract data, the system falls back to OpenAI GPT-4o-mini. Only ~2-5% of messages need AI parsing.

**If OpenAI credits run out, scraping and cleanup continue to work normally** — only the 2-5% of complex messages go unparsed. See [Monitoring OpenAI Credits](#monitoring-openai-credits).

#### Phase 3: Data Cleaning

Before storing in the database:

1. **Junk rejection**: Non-polymer listings are dropped — machinery (anything
   with a `kw`/`кв` power rating, extruders, granulators, shredders, moulds),
   free-text adverts, bare decimals like `0.4`, and vendor-only names like
   `Shurtan`. See `is_valid_polymer_name()` / `NON_POLYMER_TERMS` in `normalizer.py`.
2. **Emoji Removal**: `0209 🔴 AKPC` → `0209 AKPC`
3. **Period Removal**: `0120.` → `0120`
4. **Alias canonicalization**: Map known alternative spellings to one canonical
   "original name" via `polymer_aliases.txt` (e.g. `J-2200`, `Uz-Kor Gas J2200`
   → `2200`). See [Polymer Name Normalization](#polymer-name-normalization).
5. **Normalization**: A single separator-invariant key per polymer — lower-case,
   strip vendor words, and collapse spaces/hyphens so `Y-130`, `Y 130` and `Y130`
   are all one polymer.
6. **Deduplication**: Check unique constraint (normalized_name, date, message_link)

### Polymer Name Normalization

So the same polymer always resolves to one identity (extra rows differ only by
date/price, never by spelling), names are normalized two ways:

**1. Automatic (no configuration).** Case, surrounding spaces, hyphens, emojis,
trailing dots and vendor/origin words (`Uz-Kor Gas`, `Uzkor`, `Shurtan`, `Iran`)
are ignored — for both the identity key **and** the displayed name. This alone
merges `Y-130` / `Y 130` / `Y130` / `Uz-Kor Gas Y130`, and `Uz-Kor Gas J550` is
stored and shown simply as `J550`. No list needed, including future spellings.

**2. Alias file — grade folding (`polymer_aliases.txt`).** Declare a canonical
grade number and every spelling of that grade — any producer, type-prefix or
quality/tier wording — folds into it. Adding a grade is one line:

```
[Original Name]
2200
```

That makes `2200`, `J-2200`, `Uz-Kor Gas J-2200`, `2200 repack`,
`LLDPE 2200 Amir Kabir`, `2200 original` … all resolve to **`2200`** — the
number is matched wherever it appears as a whole number and the surrounding
words are dropped.

When the **same number is used by two different grade families** (e.g. `456`
exists as both `Py456` and `By456`, or `3` would also catch `SG3`/`30%`), the
bare number is unsafe. List the prefixed grade code under `[Alternative Names]`
— then only that family folds and the bare number is matched exactly, never on
its own:

```
[Original Name]
456

[Alternative Names]
Py456
```

`Py456` / `P-Y456` / `PY 456` → `456`, while `By456` stays separate. (Same for
`130`→`Y130`, `170`→`Fr170`, `150`→`J150`, `30`→`D30`, `3`→`BL3`.)

- `30% TiO2` and other percentages are never read as a grade number; leading
  zeros matter (`030` ≠ `30`).
- A price posted under any spelling is stored **and displayed** under the bare
  number.
- The file is **re-read automatically when it changes**, so new edits apply to
  newly scraped data without restarting the bot or scraper.
- To re-label data **already in the database** after editing the file, run:
  ```bash
  python apply_normalization.py
  ```
  This backs up the database first, then merges historical rows under the new
  canonical names. Only the name columns change — prices, dates and links are
  untouched.

## 💾 Database Schema

### Main Table: `polymer_prices`

```sql
CREATE TABLE polymer_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    polymer_name TEXT NOT NULL,           -- Original name from message
    normalized_name TEXT NOT NULL,        -- Lowercase, cleaned for matching
    price REAL,                           -- Price value (NULL if not available)
    status TEXT DEFAULT 'PRICED',         -- "PRICED", "AVAILABLE", "BOR", etc.
    date DATE NOT NULL,                   -- Message timestamp (date only)
    message_text TEXT,                    -- First 500 chars of source message
    message_link TEXT,                    -- Telegram message link (t.me/...)
    chat_id TEXT,                         -- Telegram group chat ID where message originated
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Prevent duplicate entries for same polymer on same day from same message
    UNIQUE(normalized_name, date, message_link)
);

-- Performance indexes
CREATE INDEX idx_polymer_name ON polymer_prices(normalized_name);
CREATE INDEX idx_date ON polymer_prices(date);
CREATE INDEX idx_polymer_date ON polymer_prices(normalized_name, date);
CREATE INDEX idx_chat_id ON polymer_prices(chat_id);
```

### Data Retention

The system automatically maintains a 21-day rolling window:
- Records older than `DATA_RETENTION_DAYS` are deleted at the end of each scrape cycle
- Incremental scraper stops going back further than the retention window even if the last-known message ID would allow it
- Database size remains manageable (low MBs for most chat volumes)

## 🚀 Deployment

### Option 1: Windows Task Scheduler (24/7 Laptop)

Your use case. Create a scheduled task that runs at logon:
- Program: `C:\Users\Hp\Desktop\Telegram-Bot-Polymer-Trade-\venv\Scripts\python.exe`
- Arguments: `main.py continuous --interval 4`
- Start in: `C:\Users\Hp\Desktop\Telegram-Bot-Polymer-Trade-`
- "Restart the task if it fails": Yes, every 1 minute

### Option 2: Screen Session (Linux/macOS)

```bash
screen -S polymer-bot
python main.py continuous --interval 4
# Detach: Ctrl+A, then D
# Reattach: screen -r polymer-bot
```

### Option 3: Systemd Service (Linux Production)

Create `/etc/systemd/system/polymer-bot.service`:

```ini
[Unit]
Description=Polymer Price Telegram Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/Telegram-Bot-Polymer-Trade-
ExecStart=/usr/bin/python3 main.py continuous --interval 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable polymer-bot
sudo systemctl start polymer-bot
sudo journalctl -u polymer-bot -f
```

### Option 4: Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "main.py", "continuous", "--interval", "4"]
```

```bash
docker build -t polymer-bot .
docker run -d --name polymer-bot --restart unless-stopped polymer-bot
docker logs -f polymer-bot
```

## 🔧 Troubleshooting

### Scraper Issues

#### "Cannot send requests while disconnected"

**Cause**: Telethon's MTProto connection died during the long sleep between cycles, and a request was attempted before reconnect.

**Solution**: Already handled in the current code. `_ensure_connected()` is called at the top of each cycle and per chat. If you still see this, check that you're running the updated `scraper.py`.

#### Only a handful of records in the database after days of running

**Cause**: This was a silent indentation bug in older versions of `scraper.py` — the message-processing block was one level too shallow, so only the last message of each chat got processed per cycle.

**Solution**: The current version has this fixed. If you're seeing an abnormally small DB, delete both `polymer_prices.db` and `scraper_state.json` and restart to re-pull the full 21-day window.

#### State file has chat-id keys with leading spaces

**Cause**: Older version split `TELEGRAM_CHAT_IDS` without stripping whitespace. Any spaces after commas in `.env` became leading whitespace on the keys, silently splitting state tracking between two near-identical keys.

**Solution**: `config.py` now strips every ID, and `_load_state()` in `scraper.py` one-time-migrates existing dirty keys on startup. Just run normally — you'll see a `Cleaned whitespace in state key: ...` log line if migration was needed.

#### "Could not connect to Telegram"

**Cause**: Network issues or invalid credentials.

**Solution**:
- Check internet connection
- Verify `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` in `.env`
- Ensure phone number format is correct (include country code: `+971...`)
- Delete session file and re-authenticate

#### Scraper stops with "FloodWaitError"

**Cause**: Telegram rate limiting (too many requests).

**Solution**:
- Telethon handles this with exponential backoff
- If persistent, reduce scraping frequency: `--interval 8`
- Wait 10-15 minutes before retrying

### Parser Issues

See [Monitoring OpenAI Credits](#monitoring-openai-credits) for OpenAI-specific error signatures.

### Bot Issues

#### "getaddrinfo failed" or `NetworkError: httpx.ConnectError`

**Cause**: Transient DNS resolution failure — the laptop's network briefly couldn't resolve `api.telegram.org`. Happens on 24/7 machines when wifi flaps or DNS hiccups.

**Solution**: Already handled. The current `bot.py` configures `HTTPXRequest` with 20s connect / 30s read timeouts, registers a global error handler that swallows handler-level network blips without crashing, and waits for internet on startup. If you still see crashes, check that you're running the updated `bot.py`.

#### "Bot not responding to commands"

**Cause**: Bot stopped or invalid token.

**Solution**:
- Check if bot is running: look for "Bot is running and ready to respond to user queries!" line
- Verify `TELEGRAM_BOT_TOKEN` in `.env`
- Ensure bot isn't stopped in @BotFather
- Bot only responds in private chats, never groups
- Restart: `python main.py bot`

#### "No data available for this polymer"

**Cause**: Database has no entries for the queried polymer.

**Solution**:
- Run scraper first: `python main.py scrape --days 7`
- Check if database file exists and has records: `sqlite3 polymer_prices.db "SELECT COUNT(*) FROM polymer_prices;"`
- Run `/list` in the bot to see what polymers are actually available

### Database Issues

#### "Database locked" error

**Cause**: Multiple processes accessing database simultaneously.

**Solution**:
- Only run one instance of `main.py continuous` at a time
- If running `bot` and `scraper-loop` separately, they still share the DB — SQLite's write lock is short-lived but concurrent writes during a cycle spike can briefly collide. Use `continuous` mode instead for single-laptop deployments.
- Check for zombie processes: Task Manager (Windows) or `ps aux | grep main.py` (Linux)

#### Database file corrupted

**Cause**: Unexpected shutdown or disk issues.

**Solution**:
- Backup current database: `copy polymer_prices.db polymer_prices.db.bak`
- Try recovery: `sqlite3 polymer_prices.db ".recover" > recovered.sql`
- Worst case: Delete database and re-scrape: `del polymer_prices.db` then `python main.py scrape --days 21`

#### Database growing too large

**Cause**: Unlikely with 21-day retention but possible over years.

**Solution**:
- Check size: `dir polymer_prices.db`
- Vacuum: `sqlite3 polymer_prices.db "VACUUM;"`

### Venv Issues

#### "ModuleNotFoundError" when running the script

**Cause**: Virtual environment not activated, or dependencies not installed in it.

**Solution**:
- Activate venv: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Linux/macOS)
- Verify the prompt shows `(venv)` before the path
- Reinstall deps: `pip install -r requirements.txt`

#### "unexpected keyword argument 'connection_pool_size'" from HTTPXRequest

**Cause**: `python-telegram-bot` is older than v20 and doesn't support the pool-size kwarg.

**Solution**: `pip install --upgrade python-telegram-bot` (need v21+).

## 💳 Monitoring OpenAI Credits

**Important**: The system is designed so that running out of OpenAI credits does NOT stop scraping or cleanup. Regex parses ~95% of messages. OpenAI is a fallback for the remaining ~5% of complex or multi-language messages. If OpenAI fails, those messages are silently skipped but everything else keeps working.

### How to Check Credit Balance

**Dashboard**: [platform.openai.com/usage](https://platform.openai.com/usage) — shows remaining credits, daily spend, and rate-limit headroom.

**Proactive Alerts**: Settings → Billing → Usage Limits:
- Set a **soft limit** (e.g., $2/month) to get a warning email
- Set a **hard limit** (e.g., $5/month) to auto-cut usage at the ceiling

### Error Signatures in the Console

When OpenAI credits are exhausted, the scraper's parse-error lines will contain one of these:

| Error message | Meaning |
|---|---|
| `insufficient_quota` | Paid credit balance exhausted |
| `Error code: 429 - You exceeded your current quota` | Same thing, different wording |
| `Error code: 401 - Invalid API key` | Key deactivated or wrong |
| `billing_hard_limit_reached` | Hard limit you configured was hit |

These appear inside `Error processing message {id}: ...` lines.

### Data-Level Symptoms

If scraping runs without obvious errors but new records slow down disproportionately to chat activity, parsing is degraded. Diagnostic query:

```bash
sqlite3 polymer_prices.db "SELECT date, COUNT(*) FROM polymer_prices GROUP BY date ORDER BY date DESC;"
```

If recent days show a sudden drop compared to a week ago without a matching drop in chat volume, check OpenAI credits.

### Restoring Service

- Top up credits at [platform.openai.com/billing](https://platform.openai.com/account/billing)
- No need to restart the bot — the next scrape cycle will automatically start using AI parsing again
- Messages that were skipped during the outage won't be retried (the scraper moves forward via `min_id`); they're just gone from the retention window

## 💰 API Costs

### Telegram API
- **Cost**: Free (unlimited)
- **Rate Limits**: Automatic handling with exponential backoff
- **Notes**: No costs for reading or sending messages

### OpenAI API (GPT-4o-mini)
- **Model**: gpt-4o-mini (2024-07-18)
- **Cost**: $0.150 per 1M input tokens, $0.600 per 1M output tokens
- **Average per message**: ~$0.0001 per message (regex handles 95%+)
- **Monthly estimate** (1000 messages/day, 5% need AI):
  - 30,000 messages/month
  - 1,500 AI-parsed messages
  - ~$0.15/month

### Cost Optimization

1. **Regex First**: 95%+ of messages parsed without AI
2. **Efficient Model**: GPT-4o-mini is 60x cheaper than GPT-4
3. **Minimal Context**: Only sends message text, not full conversation
4. **Caching**: Session and database reduce redundant API calls
5. **Rate Limiting**: Prevents runaway costs from errors

### Total Monthly Cost
- **Telegram**: $0
- **OpenAI**: ~$0.10 - $1.00 (depending on message volume)
- **Hosting**: Varies (VPS, cloud, local)

## 📁 Project Structure

```
Telegram-Bot-Polymer-Trade-/
├── .env                           # Environment variables (SECRET - not in git)
├── .gitignore                     # Git ignore rules (includes .env, sessions)
├── requirements.txt               # Python dependencies
│
├── config.py                      # Configuration loader from .env
├── database.py                    # Database operations & queries
├── normalizer.py                  # Loads polymer_aliases.txt, canonicalizes names
├── parser.py                      # Message parsing (regex + OpenAI)
├── scraper.py                     # Telegram message scraper (Telethon)
├── bot.py                         # Bot handlers & commands
├── main.py                        # Main entry point & orchestration
├── apply_normalization.py         # One-off: re-label existing DB rows from aliases
│
├── polymer_aliases.txt            # EDIT THIS: original ↔ alternative polymer names
├── README.md                      # This file
├── USAGE.md                       # Detailed usage and deployment guide
│
├── polymer_prices.db              # SQLite database (auto-created)
├── scraper_state.json             # Per-chat scraping state (auto-created)
└── polymer_scraper_session.session  # Telethon session file (auto-created after first auth)
```

### Key Files

- **config.py**: Loads environment variables, strips whitespace from chat IDs
- **database.py**: SQLite operations, normalization, queries, schema management
- **normalizer.py**: Loads `polymer_aliases.txt` and maps alternative spellings to a canonical name (auto-reloads on file change)
- **polymer_aliases.txt**: Human-editable list of original ↔ alternative polymer names
- **apply_normalization.py**: One-off script to re-label rows already in the database after editing the aliases
- **parser.py**: Hybrid parsing with 7 regex patterns + GPT-4o-mini fallback
- **scraper.py**: Telethon integration, message fetching, per-chat state tracking, 21-day cleanup, auto-reconnect
- **bot.py**: Telegram bot handlers, command processing, HTTPX hardening, error handler
- **main.py**: CLI interface, six run modes, asyncio orchestration

## 🔐 Security Notes

### Credentials Protection
- `.env` file contains sensitive API keys and tokens
- Already included in `.gitignore` to prevent accidental commits
- Session files are also ignored (contain authentication data)
- Never share your `.env` file or commit it to version control

### Bot Privacy & Access Control
- Bot only responds in private chats (ignores group messages)
- Optional user whitelist via `ALLOWED_USER_IDS` to restrict access to specific users
- When enabled, unauthorized users receive rejection message
- Leave `ALLOWED_USER_IDS` empty to allow all users

### Database Access
- SQLite database is local (no external access)
- No authentication required for local access
- Protect the host system to protect the data

### Recommendations
- Use strong API keys and rotate them periodically
- Run bot on a secure machine with current OS patches
- Monitor logs for unusual activity
- Keep dependencies updated: `pip install -U -r requirements.txt`

## 🆘 Support

### Getting Help

1. **Check this README**: Most questions answered here
2. **Review logs**: Console output shows detailed error messages
3. **Verify configuration**: Double-check `.env` file values
4. **Test components**: Run each mode separately to isolate issues
5. **Check dependencies**: Ensure all packages installed correctly

### Common Checks

```bash
# Verify Python version (need 3.8+)
python --version

# Check installed packages inside the venv
pip list

# Test database
sqlite3 polymer_prices.db "SELECT COUNT(*) FROM polymer_prices;"

# View state file
type scraper_state.json            # Windows
cat scraper_state.json             # Linux/macOS

# Monitor logs to a file while running
python main.py continuous --interval 4 2>&1 | tee bot.log
```

### Debug Mode

Enable verbose logging:
```python
# Add to top of main.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📄 License

This project is provided as-is for educational and commercial use.

## 🙏 Acknowledgments

- **Telethon**: Telegram client library
- **python-telegram-bot**: Bot framework
- **OpenAI**: AI-powered parsing
- **SQLite**: Reliable local database

---

**Built with ❤️ for polymer traders**

For questions or issues, check the troubleshooting section or review the console logs for detailed error messages.
