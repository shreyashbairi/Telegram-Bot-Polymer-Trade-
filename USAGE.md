# Telegram Polymer Price Bot - Usage Guide

## Overview
This bot scrapes polymer price data from Telegram groups and provides an interactive bot for querying prices.

## Running Modes

### 1. Continuous Mode (Recommended for 24/7 Operation)
Runs both the bot and scheduled scraper together. The bot responds to user queries while the scraper fetches new messages every 4 hours.

```bash
python main.py continuous
```

**Options:**
- `--interval N`: Set scraping interval in hours (default: 4)
  ```bash
  python main.py continuous --interval 2  # Scrape every 2 hours
  ```

**What it does:**
- ✅ Performs initial incremental scrape to get latest messages
- ✅ Starts the Telegram bot (responds to user queries 24/7)
- ✅ Runs scheduled scraper every N hours to fetch new messages
- ✅ Tracks last scraped message ID to avoid duplicates
- ✅ Runs indefinitely until stopped with Ctrl+C

**Use this when:**
- You want the system to run 24/7
- You want automatic data updates without manual intervention
- You're deploying to a server

---

### 2. Full Mode (One-time Setup)
Scrapes historical data first, then starts the bot.

```bash
python main.py full
```

**Options:**
- `--days N`: Number of days of historical data to scrape (default: 30)
  ```bash
  python main.py full --days 7  # Scrape last 7 days
  ```

**What it does:**
- ✅ Scrapes N days of historical messages
- ✅ Starts the bot
- ❌ Does NOT continue scraping new messages

**Use this when:**
- Initial setup
- You want to manually control when to scrape

---

### 3. Scrape Mode (Historical Scraping Only)
Scrapes historical data and exits.

```bash
python main.py scrape
```

**Options:**
- `--days N`: Number of days to scrape (default: 30)
  ```bash
  python main.py scrape --days 60  # Scrape last 60 days
  ```

**What it does:**
- ✅ Scrapes N days of historical messages
- ✅ Exits after scraping completes

**Use this when:**
- Initial database population
- Backfilling historical data
- Testing the scraper

---

### 4. Incremental Scrape Mode
Scrapes only new messages since the last scrape.

```bash
python main.py incremental
```

**What it does:**
- ✅ Reads last scraped message ID from `last_scraped_message.json`
- ✅ Scrapes only messages newer than last ID
- ✅ Updates last message ID file
- ✅ Exits after scraping

**Use this when:**
- Manually updating the database with new messages
- Testing incremental scraping
- Running scraper as a cron job

---

### 5. Bot Mode (Bot Only)
Starts only the bot, no scraping.

```bash
python main.py bot
```

**What it does:**
- ✅ Starts the Telegram bot
- ❌ Does NOT scrape any messages

**Use this when:**
- Database already has data
- You want to run scraper separately

---

## Message Tracking

The system uses `last_scraped_message.json` to track the last scraped message ID for each chat.

**Example:**
```json
{
  "-1001234567890": 12345,
  "-1009876543210": 67890
}
```

**Benefits:**
- ✅ Avoids re-processing old messages
- ✅ Efficient incremental scraping
- ✅ No duplicate entries in database
- ✅ Persists across restarts

**Location:** `last_scraped_message.json` (auto-created in project root)

---

## Deployment for 24/7 Operation

### Option 1: Using screen/tmux (Linux/macOS)

```bash
# Start a screen session
screen -S polymer-bot

# Run continuous mode
python main.py continuous

# Detach: Press Ctrl+A, then D
# Reattach later: screen -r polymer-bot
```

### Option 2: Using systemd (Linux)

Create `/etc/systemd/system/polymer-bot.service`:

```ini
[Unit]
Description=Polymer Price Telegram Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/Telegram-Bot-Polymer-Trade-
ExecStart=/usr/bin/python3 main.py continuous
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable polymer-bot
sudo systemctl start polymer-bot
sudo systemctl status polymer-bot
```

### Option 3: Using Docker

```bash
# Build
docker build -t polymer-bot .

# Run
docker run -d --name polymer-bot \
  --restart unless-stopped \
  -v $(pwd):/app \
  polymer-bot python main.py continuous
```

---

## Logs and Monitoring

The system prints detailed logs:

```
==============================================================
Starting scheduled scrape at 2026-01-26 14:30:00
==============================================================

Scraping chat: -1001234567890
Last scraped message ID: 12345
Message link base: https://t.me/c/1234567890
Scanned 50 messages, processed 45 text messages, found 120 polymer entries...
Saved last message ID 12395 for chat -1001234567890

==============================================================
Scrape complete. Next scrape in 4 hours.
Next run at: 2026-01-26 18:30:00
==============================================================
```

**Monitor in real-time:**
```bash
tail -f scraper.log  # If using output redirection
```

---

## Bot Commands

Once running, users can interact with the bot:

- `/start` - Start the bot
- `/help` - Show help message
- `/list` - List available polymers
- `/search <name>` - Search for a polymer
- `/daily <date>` - View all polymers for a date
- `/compare <polymer>` - Compare polymer prices
- `/compare (polymer 1) (polymer 2)` - Compare two polymers
- `/clear` - Clear chat

---

## Configuration

Edit `config.py` or `.env` file:

```python
# Scraping configuration
DAYS_TO_SCRAPE = 30  # Default days for historical scrape

# Telegram configuration
TELEGRAM_CHAT_IDS = ["-1001234567890"]  # Groups to scrape
```

---

## Troubleshooting

### "No new messages found"
- Normal if no new messages since last scrape
- Check `last_scraped_message.json` for last ID

### "Rate limit exceeded"
- OpenAI rate limit hit
- Scraper retries with exponential backoff
- Consider increasing scrape interval

### "Connection lost"
- Network interruption
- System automatically retries
- Check internet connection

### Database locked
- Multiple processes accessing database
- Stop duplicate processes
- Use continuous mode instead of running bot + scraper separately

---

## Recommended Setup

1. **Initial Setup:**
   ```bash
   python main.py scrape --days 30
   ```

   This will:
   - Scrape 30 days of historical messages
   - Create/update `last_scraped_message.json` with the latest message ID
   - Exit after scraping completes

2. **Production (24/7):**
   ```bash
   python main.py continuous --interval 4
   ```

   This will:
   - Do an initial incremental scrape from the last message ID
   - Start the Telegram bot (responds to queries 24/7)
   - Start the scheduled scraper (runs every 4 hours)
   - Both services run concurrently until you stop with Ctrl+C

3. **Manual Updates (if needed):**
   ```bash
   python main.py incremental
   ```

---

## Files Created

- `last_scraped_message.json` - Tracks last scraped message IDs
- `polymer_prices.db` - SQLite database with price data
- `polymer_scraper_session.session` - Telethon session file

**Do NOT delete these files** - they contain important state and data.
