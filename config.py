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
TELEGRAM_CHAT_IDS = os.getenv('TELEGRAM_CHAT_IDS').split(',')

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

# Scraping Configuration
DAYS_TO_SCRAPE = 30  # Scrape 1 month of data
