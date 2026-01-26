# Polymer Price Telegram Bot

A comprehensive Telegram bot system that scrapes polymer price data from trading groups, parses unstructured messages using intelligent regex and AI, and provides a 24/7 query interface with historical price analysis, comparisons, and statistics.

## 🚀 Features

### Core Functionality
- **24/7 Continuous Operation**: Bot responds to queries while scraper runs on a schedule
- **Intelligent Message Scraping**: Fetches messages from Telegram groups using Telethon
- **Incremental Updates**: Tracks last scraped message to avoid reprocessing
- **Hybrid Parsing**: Combines fast regex patterns with OpenAI GPT-4o-mini fallback
- **Smart Data Cleaning**: Removes emojis, trailing periods, and normalizes names
- **30-Day Data Retention**: Automatically maintains rolling window of historical data
- **SQLite Storage**: Local database with efficient indexing and duplicate handling

### Bot Commands
- `/start` - Welcome message with quick-access polymer menu
- `/help` - Comprehensive command reference and usage examples
- `/list` - Browse all available polymers with pagination
- `/search <name>` - Search for specific polymers by name
- `/clear` - Clear chat history for a fresh start
- `/daily <polymer> [days]` - Show daily price statistics with highest/lowest/mean/diff
- `/compare <polymer1> <polymer2> [days]` - Compare two polymers side-by-side
- Direct text queries - Simply type a polymer name to get instant price history

### Advanced Features
- **Parentheses Syntax**: Handle multi-word polymer names using `(polymer name)` format
- **Hyperlinked References**: Clean message formatting with 🔗 emoji links to source messages
- **Partial Data Display**: Show available data even when comparisons have incomplete overlap
- **Price Statistics**: Calculate highest, lowest, mean, difference, and latest prices per day
- **Smart Normalization**: Consistent polymer matching regardless of formatting variations
- **Private Chat Only**: Bot only responds in private messages for security
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
13. [API Costs](#api-costs)
14. [Project Structure](#project-structure)

## 🏗️ Architecture

The system consists of four main components working together:

### 1. **Scraper** (`scraper.py`)
- Uses Telethon to connect to Telegram and fetch messages
- Supports both historical scraping (N days back) and incremental scraping (new messages only)
- Tracks last scraped message ID in `last_scraped_message.json`
- Runs on a schedule (default: every 4 hours) in continuous mode
- Handles rate limiting and connection errors gracefully

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
- 30-day rolling window maintenance

### 4. **Bot** (`bot.py`)
- Python-telegram-bot v21.10 framework
- HTML formatting for rich message display
- Interactive inline keyboard menus
- Pagination for long polymer lists
- Smart query matching with fuzzy search
- Private chat restriction for security

### 5. **Main Controller** (`main.py`)
- Orchestrates all components with asyncio
- Five run modes: full, scrape, bot, continuous, incremental
- Command-line interface with arguments
- Concurrent execution of bot and scraper
- Graceful shutdown handling

## 📦 Prerequisites

- **Python 3.8 or higher**
- **Telegram Account** with API credentials (get from https://my.telegram.org)
- **Telegram Bot Token** (create bot via @BotFather)
- **OpenAI API Key** (get from https://platform.openai.com)
- **Access to polymer trading group** (must be a member)

## 🔧 Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd Telegram-Bot-Polymer-Trade-
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Set Up Configuration
Create a `.env` file in the root directory:

```env
# Telegram API Credentials (from https://my.telegram.org)
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE=+1234567890
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_IDS=-1001234567890

# OpenAI API Credentials
OPENAI_API_KEY=sk-proj-...
OPENAI_ORG_ID=org-...

# Database
DATABASE_PATH=polymer_prices.db
```

### 4. Security Note
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
| `OPENAI_API_KEY` | OpenAI API key | `sk-proj-...` |
| `OPENAI_ORG_ID` | OpenAI organization ID | `org-...` |
| `DATABASE_PATH` | SQLite database file path | `polymer_prices.db` |

### Getting Telegram Chat IDs

1. Add your bot to the target group
2. Forward a message from the group to @userinfobot
3. The bot will show you the chat ID (starts with `-100`)

## 🚦 Quick Start

### First Time Setup

1. **Authenticate with Telegram**:
   ```bash
   python main.py scrape --days 7
   ```
   - Telethon will prompt for a verification code
   - Check your Telegram app for the code
   - Enter it in the terminal
   - A session file is created (only needed once)

2. **Run in Continuous Mode**:
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
   - Try queries like "0120" or "/search AKPC"

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

#### Viewing Statistics
```
/daily 0120
```
Shows daily statistics for the last 7 days:
- Highest price with link 🔗
- Lowest price with link 🔗
- Mean (average) price
- Difference (highest - lowest)
- Latest recorded price with link 🔗

**Custom date range**:
```
/daily 0120 14
```
Shows statistics for the last 14 days.

#### Comparing Polymers

**Single-word names**:
```
/compare 0120 0220
```

**Multi-word names** (use parentheses):
```
/compare (2119 Iran) (2119 Arya)
```

**With custom date range**:
```
/compare (0209 AKPC) (0209 Amir Kabir) 10
```
Compares the two polymers over the last 10 days.

**Partial data display**: The comparison shows data even when one polymer has missing days, explicitly noting "No data" for gaps.

### For Administrators (System Operation)

#### Run Modes

See [Run Modes](#run-modes) section for detailed information on each mode.

**Production (Recommended)**:
```bash
# Initial data collection
python main.py scrape --days 30

# Start continuous operation
python main.py continuous --interval 4
```

**Development**:
```bash
# Test scraping only
python main.py scrape --days 7

# Test bot only (with existing data)
python main.py bot
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
| `/daily <polymer> [days]` | Show daily price statistics | `/daily 0120 7` |
| `/compare <p1> <p2> [days]` | Compare two polymers | `/compare 0120 0220 10` |
| `<polymer name>` | Direct query for price history | `0120` |

### System Commands (Command Line)

| Command | Description |
|---------|-------------|
| `python main.py full` | Scrape 30 days then start bot |
| `python main.py scrape --days N` | Scrape N days of historical data |
| `python main.py bot` | Start bot only (requires existing data) |
| `python main.py continuous --interval N` | Run bot + scheduled scraper (every N hours) |
| `python main.py incremental` | Scrape only new messages since last run |

## 🔄 Run Modes

### 1. Continuous Mode (Recommended for Production)
```bash
python main.py continuous --interval 4
```

**What it does**:
- Loads last scraped message ID from `last_scraped_message.json`
- Performs initial incremental scrape to catch up on new messages
- Starts the Telegram bot (responds to user queries 24/7)
- Starts the scheduled scraper (fetches new messages every N hours)
- Both services run concurrently using asyncio.gather()

**When to use**: Production deployment, 24/7 operation

**Output**:
```
✅ Bot is running and ready to respond to user queries!
✅ Scheduled scraper is running! Will scrape every 4 hours.
```

### 2. Historical Scrape Mode
```bash
python main.py scrape --days 30
```

**What it does**:
- Scrapes N days of historical messages from Telegram groups
- Parses and stores all polymer prices in the database
- Saves the last message ID to `last_scraped_message.json`
- Exits after completion

**When to use**: Initial setup, backfilling data, testing scraper

### 3. Bot Only Mode
```bash
python main.py bot
```

**What it does**:
- Starts only the Telegram bot
- Responds to user queries using existing database
- Does not scrape any new messages

**When to use**: Testing bot functionality, when scraping is handled separately

### 4. Incremental Scrape Mode
```bash
python main.py incremental
```

**What it does**:
- Loads last scraped message ID from tracking file
- Scrapes only messages newer than the last ID
- Updates the tracking file with new last message ID
- Exits after completion

**When to use**: Manual updates, cron jobs, testing incremental logic

### 5. Full Mode
```bash
python main.py full
```

**What it does**:
- Scrapes 30 days of historical data
- Immediately starts the bot after scraping completes
- Does NOT use scheduled scraping (one-time scrape only)

**When to use**: First-time setup in environments without continuous operation

## 🔍 How It Works

### Message Scraping Process

1. **Connection**: Telethon connects to Telegram using your API credentials
2. **Authentication**: Session file stores authentication (persists across runs)
3. **Message Fetching**:
   - Historical mode: Fetches messages from N days ago to present
   - Incremental mode: Fetches only messages with ID > last_scraped_message_id
4. **Tracking**: Saves the highest message ID to `last_scraped_message.json`
5. **Scheduling**: In continuous mode, repeats every N hours

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

**Key feature**: Uses `[ \t]` instead of `\s` in patterns to prevent matching across newlines, fixing multi-line parsing bugs.

#### Phase 2: AI-Powered Parsing

If regex fails to extract data, the system falls back to OpenAI:

```python
# Sent to GPT-4o-mini:
Parse this message and extract polymer names and prices:
"0120 18500
0220 18800
0120 analigi eron 17000"

# Returns structured JSON:
[
  {"polymer_name": "0120", "price": 18500},
  {"polymer_name": "0220", "price": 18800},
  {"polymer_name": "0120 analigi eron", "price": 17000}
]
```

**Cost optimization**: Only 2-5% of messages need AI parsing. GPT-4o-mini is 60x cheaper than GPT-4.

#### Phase 3: Data Cleaning

Before storing in the database:

1. **Emoji Removal**: `0209 🔴 AKPC` → `0209 AKPC`
2. **Period Removal**: `0120.` → `0120`
3. **Normalization**: Convert to lowercase, remove extra spaces
4. **Deduplication**: Check unique constraint (normalized_name, date, message_id)

### Query Processing

1. **User Input**: Receives command or text query
2. **Normalization**: Applies same cleaning rules as parsing
3. **Database Lookup**: Searches by normalized name
4. **Date Filtering**: Retrieves prices for requested date range
5. **Statistics**: Calculates highest, lowest, mean, diff if using /daily
6. **Formatting**: Generates HTML-formatted response with hyperlinked emojis
7. **Response**: Sends via Telegram with `parse_mode='HTML'`

### Comparison Logic

When comparing two polymers:

1. Retrieves data for both polymers over N days
2. Groups by day (1 = yesterday, 2 = 2 days ago, etc.)
3. Calculates statistics for each polymer on each day
4. Shows data side-by-side
5. Explicitly displays "No data" when one polymer has no entries for a day
6. Links to source messages with 🔗 emoji

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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Prevent duplicate entries for same polymer on same day from same message
    UNIQUE(normalized_name, date, message_link)
);

-- Performance indexes
CREATE INDEX idx_polymer_name ON polymer_prices(normalized_name);
CREATE INDEX idx_date ON polymer_prices(date);
CREATE INDEX idx_polymer_date ON polymer_prices(normalized_name, date);
```

### Tracking File: `last_scraped_message.json`

```json
{
  "-1001234567890": 54321,
  "-1009876543210": 98765
}
```

Maps chat IDs to the last message ID scraped from each chat. Used by incremental scraping to avoid reprocessing.

### Data Retention

The system automatically maintains a 30-day rolling window:
- Old entries (>30 days) are kept but may be excluded from queries
- Scraper only fetches messages from last 30 days in historical mode
- Database size remains manageable

## 🚀 Deployment

### Option 1: Screen Session (Quick & Simple)

```bash
# Start a screen session
screen -S polymer-bot

# Run continuous mode
python main.py continuous --interval 4

# Detach: Ctrl+A, then D
# Reattach: screen -r polymer-bot
```

### Option 2: Systemd Service (Production)

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

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable polymer-bot
sudo systemctl start polymer-bot
sudo systemctl status polymer-bot
```

View logs:
```bash
sudo journalctl -u polymer-bot -f
```

### Option 3: Docker (Isolated Environment)

Create `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py", "continuous", "--interval", "4"]
```

Build and run:
```bash
docker build -t polymer-bot .
docker run -d --name polymer-bot --restart unless-stopped polymer-bot
```

View logs:
```bash
docker logs -f polymer-bot
```

### Option 4: PM2 (Process Manager)

```bash
# Install PM2
npm install -g pm2

# Start bot
pm2 start "python main.py continuous --interval 4" --name polymer-bot

# Monitor
pm2 status
pm2 logs polymer-bot

# Auto-restart on reboot
pm2 startup
pm2 save
```

## 🔧 Troubleshooting

### Scraper Issues

#### "Last scraped message ID: 0" after historical scrape

**Cause**: You're using an older version before the tracking fix.

**Solution**: Update to the latest code. The historical scraper now saves the last message ID.

#### "Could not connect to Telegram"

**Cause**: Network issues or invalid credentials.

**Solution**:
- Check internet connection
- Verify `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` in `.env`
- Ensure phone number format is correct (include country code: `+971...`)
- Delete session file and re-authenticate

#### "No messages found" or "Total messages scanned: 0"

**Cause**: Chat ID is incorrect or bot lacks access.

**Solution**:
- Verify the chat ID starts with `-100` for supergroups
- Ensure you're a member of the group
- Check that the group has messages in the date range
- Try fetching a shorter period: `--days 1`

#### Scraper stops with "FloodWaitError"

**Cause**: Telegram rate limiting (too many requests).

**Solution**:
- The scraper automatically handles this with exponential backoff
- If persistent, reduce scraping frequency: `--interval 8`
- Wait 10-15 minutes before retrying

### Parser Issues

#### "OpenAI API error: 429 Too Many Requests"

**Cause**: Rate limit exceeded on OpenAI API.

**Solution**:
- The parser implements exponential backoff (retries after 2s, 4s, 8s, 16s)
- Upgrade your OpenAI plan for higher rate limits
- Most messages use regex parsing, so this is rare

#### "OpenAI API error: 401 Unauthorized"

**Cause**: Invalid API key.

**Solution**:
- Verify `OPENAI_API_KEY` in `.env`
- Check if the key is active on https://platform.openai.com
- Ensure sufficient credits in your OpenAI account

#### "Multiple polymers treated as one"

**Cause**: Older version with `\s` in regex patterns.

**Solution**: Update to latest code. Regex now uses `[ \t]` to prevent multi-line matching.

#### "No polymers extracted from message"

**Cause**: Message format doesn't match any patterns.

**Solution**:
- Check console output to see the message text
- Verify it contains price data (numbers after polymer names)
- OpenAI fallback should handle most cases
- Consider adding a new regex pattern for the format

### Bot Issues

#### "Bot not responding to commands"

**Cause**: Bot stopped or invalid token.

**Solution**:
- Check if bot is running: Look for "✅ Bot is running" message
- Verify `TELEGRAM_BOT_TOKEN` in `.env`
- Ensure bot isn't stopped in @BotFather
- Check bot only responds in private chats (not groups)
- Restart: `python main.py bot`

#### "No data available for this polymer"

**Cause**: Database has no entries for the queried polymer.

**Solution**:
- Run scraper first: `python main.py scrape --days 7`
- Check if database file exists: `ls -lh polymer_prices.db`
- Query a different polymer name that definitely exists
- Run `/list` to see available polymers

#### "Bot responds in continuous mode but doesn't scrape"

**Cause**: Scheduled scraper error (check logs).

**Solution**:
- Look for error messages in console output
- Verify Telethon session is valid
- Check disk space (database needs write access)
- Ensure both services started (look for both ✅ messages)

#### "/compare command not working with spaces"

**Cause**: Forgot to use parentheses for multi-word names.

**Solution**: Use `(polymer name)` syntax:
```
/compare (2119 Iran) (2119 Arya)
```

### Database Issues

#### "Database locked" error

**Cause**: Multiple processes accessing database simultaneously.

**Solution**:
- Only run one instance of the bot
- Check for zombie processes: `ps aux | grep main.py`
- Kill duplicates: `pkill -f "python main.py"`

#### Database file corrupted

**Cause**: Unexpected shutdown or disk issues.

**Solution**:
- Backup current database: `cp polymer_prices.db polymer_prices.db.bak`
- Try recovery: `sqlite3 polymer_prices.db ".recover" > recovered.sql`
- Worst case: Delete database and re-scrape: `rm polymer_prices.db && python main.py scrape --days 30`

#### Database growing too large

**Cause**: Accumulation of old data.

**Solution**:
- Check size: `ls -lh polymer_prices.db`
- Vacuum database: `sqlite3 polymer_prices.db "VACUUM;"`
- Delete old entries: `sqlite3 polymer_prices.db "DELETE FROM polymer_prices WHERE date < date('now', '-60 days');"`

### General Issues

#### High memory usage

**Cause**: Processing large number of messages.

**Solution**:
- Reduce scraping period: `--days 7` instead of `--days 30`
- Increase scraping interval: `--interval 6` instead of `--interval 4`
- Monitor with: `top -p $(pgrep -f "python main.py")`

#### Bot stops after some time

**Cause**: Unhandled exception or network issue.

**Solution**:
- Use a process manager (systemd, PM2, or screen)
- Check logs for error messages before crash
- Ensure `Restart=always` in systemd service
- Monitor with: `pm2 monit` (if using PM2)

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
├── parser.py                      # Message parsing (regex + OpenAI)
├── scraper.py                     # Telegram message scraper (Telethon)
├── bot.py                         # Bot handlers & commands
├── main.py                        # Main entry point & orchestration
│
├── README.md                      # This file
├── USAGE.md                       # Detailed usage and deployment guide
│
├── polymer_prices.db              # SQLite database (auto-created)
├── last_scraped_message.json      # Tracking file for incremental scraping
└── *.session                      # Telethon session files (auto-created)
```

### Key Files

- **config.py**: Loads environment variables, validates configuration
- **database.py**: SQLite operations, normalization, queries, schema management
- **parser.py**: Hybrid parsing with 7 regex patterns + GPT-4o-mini fallback
- **scraper.py**: Telethon integration, message fetching, tracking, scheduling
- **bot.py**: Telegram bot handlers, command processing, response formatting
- **main.py**: Command-line interface, mode selection, asyncio orchestration

## 🔐 Security Notes

### Credentials Protection
- `.env` file contains sensitive API keys and tokens
- Already included in `.gitignore` to prevent accidental commits
- Session files are also ignored (contain authentication data)
- Never share your `.env` file or commit it to version control

### Bot Privacy
- Bot only responds in private chats (ignores group messages)
- This prevents unauthorized users from accessing price data in public groups
- Only users who directly message the bot can query prices

### Database Access
- SQLite database is local (no external access)
- No authentication required for local access
- Protect the host system to protect the data

### Recommendations
- Use strong API keys and rotate them periodically
- Run bot on a secure server with firewall rules
- Monitor logs for unusual activity
- Keep dependencies updated: `pip install -U -r requirements.txt`

## 🎯 Extending the System

### Adding More Telegram Groups

Edit `.env` and add multiple chat IDs (comma-separated):
```env
TELEGRAM_CHAT_IDS=-1001234567890,-1002345678900,-1003456789000
```

The scraper will fetch messages from all groups and store them together.

### Customizing Scraping Schedule

Change the interval hours:
```bash
python main.py continuous --interval 6    # Every 6 hours
python main.py continuous --interval 2    # Every 2 hours
```

### Adding New Regex Patterns

Edit `parser.py` and add to the `patterns` list:
```python
patterns = [
    # Existing patterns...
    r'YOUR_NEW_PATTERN_HERE',
]
```

Use `[ \t]` for whitespace (not `\s`) to avoid multi-line matching.

### Custom Bot Commands

Add new handlers in `bot.py`:
```python
self.app.add_handler(CommandHandler("mycommand", self.my_command_handler))

async def my_command_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("My custom response")
```

### Export Functionality

Add a new command to export data:
```python
import csv

def export_to_csv(self, polymer_name: str, days: int = 30):
    prices = self.db.get_price_history(polymer_name, days)
    with open(f'{polymer_name}_export.csv', 'w') as f:
        writer = csv.writer(f)
        writer.writerow(['Date', 'Price', 'Status'])
        for entry in prices:
            writer.writerow([entry['date'], entry['price'], entry['status']])
```

### Price Alerts

Implement monitoring for price changes:
```python
def check_price_alerts(self):
    # Get current prices
    # Compare with threshold
    # Send notification if exceeded
    pass
```

### Analytics Dashboard

Create a web interface:
- Flask/FastAPI for backend
- Read from SQLite database
- Display charts with Chart.js or Plotly
- Show trends, averages, comparisons

## 📊 Advanced Features

### Fuzzy Search

The bot implements smart matching:
- "j150" matches "Uz-Kor Gas J 150"
- "2119 iran" matches "2119 Iran Petrochemical"
- Handles typos and variations

### Pagination

Large polymer lists are paginated:
- Shows 10 items per page
- "Next Page" and "Previous Page" buttons
- Improves performance and UX

### HTML Formatting

Messages use HTML for rich display:
```html
<b>Bold text</b>
<i>Italic text</i>
<a href='https://t.me/...'>🔗</a>
```

### Message Links

Every price entry includes source link:
- Public groups: `https://t.me/username/message_id`
- Private groups: `https://t.me/c/chat_id/message_id`
- Click 🔗 to view original message

### Rate Limiting

Built-in protection:
- Exponential backoff for Telegram API
- OpenAI rate limit handling
- Prevents API bans and overages

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

# Check installed packages
pip list

# Test database
sqlite3 polymer_prices.db "SELECT COUNT(*) FROM polymer_prices;"

# View tracking file
cat last_scraped_message.json

# Monitor logs in real-time
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
