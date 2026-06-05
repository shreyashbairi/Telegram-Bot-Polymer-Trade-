"""
Configuration module for loading environment variables
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram Configuration
TELEGRAM_API_ID = int(os.getenv('TELEGRAM_API_ID'))
TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH')
TELEGRAM_PHONE = os.getenv('TELEGRAM_PHONE')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Chat IDs — strip whitespace and drop empty entries.
# Without .strip() a .env line like "TELEGRAM_CHAT_IDS=-1001,  -1002" produces
# [" -1001", "  -1002"] and those leading spaces end up as keys in
# scraper_state.json, causing silent state corruption.
_raw_chat_ids = os.getenv('TELEGRAM_CHAT_IDS', '')
TELEGRAM_CHAT_IDS = [cid.strip() for cid in _raw_chat_ids.split(',') if cid.strip()]

# Allowed User IDs (comma-separated list of Telegram user IDs who can use the bot)
# If empty or not set, bot will respond to all users
ALLOWED_USER_IDS = os.getenv('ALLOWED_USER_IDS', '').strip()
if ALLOWED_USER_IDS:
    ALLOWED_USER_IDS = [int(uid.strip()) for uid in ALLOWED_USER_IDS.split(',') if uid.strip()]
else:
    ALLOWED_USER_IDS = []

# OpenAI Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_ORG_ID = os.getenv('OPENAI_ORG_ID')

# Database Configuration
DATABASE_PATH = os.getenv('DATABASE_PATH', 'polymer_prices.db')

# Polymer name normalization (alias) file.
# Maps alternative spellings of a polymer to a single canonical "original name"
# so that e.g. "J2210", "j-2210" and "Uz-Kor Gas J-2210" are all treated as
# "J-2210". Edit it by hand; see the file header for the format. It is reloaded
# automatically when it changes on disk.
POLYMER_ALIASES_FILE = os.getenv('POLYMER_ALIASES_FILE', 'polymer_aliases.txt')

# Scraping Configuration
DATA_RETENTION_DAYS = 21  # Keep 3 weeks of data
DAYS_TO_SCRAPE = DATA_RETENTION_DAYS  # Initial scrape matches retention window
SCRAPE_INTERVAL_HOURS = 4  # Scrape every 4 hours