# Polymer Price Telegram Bot

A Telegram bot that scrapes polymer price data from trading groups and provides historical price queries to users.

## Features

- Scrapes historical messages (up to 30 days) from Telegram groups
- Parses unstructured polymer price data using OpenAI
- Stores price history in a local SQLite database
- Provides user-friendly bot interface for price queries
- Shows historical prices: yesterday, 3 days ago, 1 week ago
- Handles duplicate entries and inconsistent formatting
- Interactive polymer selection menu

## Architecture

The system consists of three main components:

1. **Scraper** (`scraper.py`): Uses Telethon to fetch messages from Telegram groups
2. **Parser** (`parser.py`): Extracts polymer names and prices using regex and OpenAI
3. **Bot** (`bot.py`): Handles user interactions and price queries

## Prerequisites

- Python 3.8 or higher
- Telegram account with API credentials
- Telegram Bot Token (from @BotFather)
- OpenAI API key
- Access to the polymer trading group

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Telegram-Bot-Polymer-Trade-
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
   - The `.env` file is already configured with your credentials
   - Verify all values are correct before running

## Configuration

All configuration is stored in `.env`:

```env
# Telegram API Credentials
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE=your_phone_number
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_IDS=group_chat_id

# OpenAI API Credentials
OPENAI_API_KEY=your_openai_key
OPENAI_ORG_ID=your_openai_org_id

# Database
DATABASE_PATH=polymer_prices.db
```

## Usage

### Option 1: Run Complete System (Recommended for First Time)

This will scrape historical data and then start the bot:

```bash
python main.py full
```

### Option 2: Scrape Data Only

To only collect historical data without starting the bot:

```bash
python main.py scrape --days 30
```

### Option 3: Run Bot Only

If you already have data and just want to run the bot:

```bash
python main.py bot
```

## First Time Setup

When running for the first time:

1. **Authentication**: Telethon will ask you to authenticate your phone number:
   - You'll receive a code via Telegram
   - Enter the code when prompted
   - This creates a session file (only needed once)

2. **Data Collection**: The scraper will fetch 30 days of messages:
   - This may take 5-15 minutes depending on message volume
   - Progress updates are shown in the console

3. **Bot Activation**: After scraping, the bot starts automatically:
   - Users can now interact with it via Telegram
   - Search for your bot using its username in Telegram

## Using the Bot

Users can interact with the bot in several ways:

### Commands

- `/start` - Welcome message and polymer menu
- `/list` - Show all available polymers
- `/help` - Display help information

### Query Methods

1. **Interactive Menu**: Click on polymer names from the list
2. **Direct Query**: Type polymer name directly (e.g., "J150", "Y130")

### Response Format

The bot responds with:
- Price yesterday
- Price 3 days ago
- Price 1 week ago
- Latest available price
- Availability status if no price is listed

Example response:
```
📊 Price History for Uz-Kor Gas J 150
========================================

📅 Yesterday (2026-01-21):
   💰 14,900

📅 3 days ago (2026-01-19):
   💰 14,850

📅 1 week ago (2026-01-15):
   💰 15,000

========================================
🔄 Latest Price (2026-01-21):
   💰 14,900
```

## How It Works

### 1. Message Scraping

The scraper:
- Connects to Telegram using your credentials
- Fetches messages from the specified group
- Processes messages in chronological order
- Handles rate limiting automatically

### 2. Data Parsing

The parser uses two methods:

**Simple Parsing** (fast, for well-formatted messages):
- Regex patterns to extract polymer names and prices
- Handles common formats: "J150 14.900", "Y130 BOR", etc.

**AI Parsing** (for complex messages):
- OpenAI GPT-3.5-turbo analyzes unstructured text
- Extracts polymer names even with inconsistent formatting
- Handles mixed languages (Uzbek, Russian, English)

### 3. Data Storage

- SQLite database stores all price entries
- Handles duplicates using unique constraints
- Normalizes polymer names for consistent matching
- Indexes on polymer name and date for fast queries

### 4. User Queries

- Bot matches user queries to normalized names
- Retrieves prices for specific dates
- Falls back to latest price if historical data unavailable
- Provides clear feedback when data is missing

## Database Schema

```sql
CREATE TABLE polymer_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    polymer_name TEXT NOT NULL,           -- Original name from message
    normalized_name TEXT NOT NULL,        -- Normalized for matching
    price REAL,                           -- Price value (can be NULL)
    status TEXT,                          -- "AVAILABLE", "BOR", etc.
    date DATE NOT NULL,                   -- Date from message
    message_text TEXT,                    -- Source message excerpt
    message_id INTEGER,                   -- Telegram message ID
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(normalized_name, date, message_id)
);
```

## Troubleshooting

### Scraper Issues

**"Could not connect to Telegram"**
- Check your internet connection
- Verify API credentials in `.env`
- Ensure phone number format is correct (+971...)

**"No messages found"**
- Verify the chat ID is correct
- Ensure you're a member of the group
- Check that the group has messages in the date range

### Parser Issues

**"OpenAI API error"**
- Verify your OpenAI API key is valid
- Check if you have sufficient credits
- The system will fall back to regex parsing

**"No polymers extracted"**
- Messages may not contain price data
- Check message format matches examples
- Verify OpenAI API is responding

### Bot Issues

**"Bot not responding"**
- Check if bot token is correct
- Verify bot is not stopped in @BotFather
- Restart the bot using `python main.py bot`

**"No data available"**
- Run the scraper first: `python main.py scrape`
- Check database file exists: `polymer_prices.db`
- Verify data was actually collected

## Project Structure

```
Telegram-Bot-Polymer-Trade-/
├── .env                    # Environment variables (configured)
├── .gitignore             # Git ignore rules
├── requirements.txt       # Python dependencies
├── config.py             # Configuration loader
├── database.py           # Database operations
├── parser.py             # Message parsing logic
├── scraper.py            # Telegram message scraper
├── bot.py                # Bot interaction handlers
├── main.py               # Main entry point
├── README.md             # This file
└── polymer_prices.db     # SQLite database (created on first run)
```

## API Costs

- **Telegram API**: Free (no costs)
- **OpenAI API**: Approximately $0.002 per message parsed
  - For 1000 messages: ~$2
  - Simple regex parsing is used first to minimize costs

## Security Notes

- `.env` file contains sensitive credentials
- Added to `.gitignore` to prevent committing
- Session files are also ignored
- Never share your API keys or bot token

## Extending the System

### Adding More Groups

Edit `.env` and add more chat IDs (comma-separated):
```env
TELEGRAM_CHAT_IDS=-1001634518795,-1002345678900
```

### Customizing Scraping Period

Change in `config.py` or use command line:
```bash
python main.py scrape --days 60
```

### Adding New Features

- **Price alerts**: Monitor price changes and notify users
- **Export data**: Add CSV/Excel export functionality
- **Charts**: Generate price trend charts
- **Statistics**: Calculate average prices, trends, etc.

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review console logs for error messages
3. Verify all credentials are correct
4. Ensure dependencies are installed

## License

This project is provided as-is for educational and commercial use.
