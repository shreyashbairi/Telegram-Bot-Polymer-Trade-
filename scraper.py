"""
Message scraper using Telethon to fetch historical messages from Telegram group
"""
import asyncio
import os
import json
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient, events
from telethon.tl.types import Message
import config
from database import PolymerDatabase
from parser import PolymerParser

# File to store the last scraped message ID for each chat
LAST_MESSAGE_FILE = 'last_scraped_message.json'

class PolymerScraper:
    def __init__(self):
        """Initialize Telegram client"""
        self.client = TelegramClient(
            'polymer_scraper_session',
            config.TELEGRAM_API_ID,
            config.TELEGRAM_API_HASH
        )
        self.db = PolymerDatabase()
        self.parser = PolymerParser()

    def _load_last_message_ids(self) -> dict:
        """Load the last scraped message IDs from file"""
        if os.path.exists(LAST_MESSAGE_FILE):
            try:
                with open(LAST_MESSAGE_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading last message IDs: {e}")
                return {}
        return {}

    def _save_last_message_id(self, chat_id: str, message_id: int):
        """Save the last scraped message ID for a chat"""
        data = self._load_last_message_ids()
        data[str(chat_id)] = message_id
        try:
            with open(LAST_MESSAGE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"Saved last message ID {message_id} for chat {chat_id}")
        except Exception as e:
            print(f"Error saving last message ID: {e}")

    async def start(self):
        """Start the Telegram client"""
        await self.client.start(phone=config.TELEGRAM_PHONE)
        print("Scraper client started successfully")

    async def stop(self):
        """Stop the Telegram client"""
        await self.client.disconnect()
        print("Scraper client stopped")

    async def scrape_historical_data(self, days: int = 30):
        """
        Scrape historical messages from the group
        """
        print(f"Starting to scrape {days} days of historical data...")

        for chat_id in config.TELEGRAM_CHAT_IDS:
            try:
                chat_id_int = int(chat_id)
                print(f"Scraping chat: {chat_id_int}")

                # Get the chat entity to extract username for message links
                chat_entity = await self.client.get_entity(chat_id_int)

                # Determine the username/link base
                if hasattr(chat_entity, 'username') and chat_entity.username:
                    link_base = f"https://t.me/{chat_entity.username}"
                else:
                    # For private groups/channels without username, use chat ID
                    # Format: https://t.me/c/{chat_id_without_-100}/{message_id}
                    chat_id_str = str(chat_id_int).replace('-100', '')
                    link_base = f"https://t.me/c/{chat_id_str}"

                print(f"Message link base: {link_base}")

                # Calculate the cutoff date (timezone-aware to match Telegram message dates)
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

                # Fetch messages
                message_count = 0
                processed_count = 0
                total_scanned = 0
                max_message_id = 0  # Track the latest message ID

                # Iterate through messages from most recent
                async for message in self.client.iter_messages(chat_id_int, limit=None):
                    total_scanned += 1

                    # Track the highest message ID we've seen
                    if message.id > max_message_id:
                        max_message_id = message.id

                    # Stop if message is older than our cutoff date
                    if message.date < cutoff_date:
                        print(f"Reached messages older than {days} days, stopping...")
                        break

                    # Only process text messages
                    if not message.text:
                        continue

                    message_count += 1

                    # Skip very short messages (likely not price data)
                    if len(message.text) < 20:
                        continue

                    # Parse the message
                    try:
                        polymers = self.parser.parse_message(message.text)

                        if polymers:
                            # Construct message link
                            message_link = f"{link_base}/{message.id}"

                            # Store each polymer price in the database
                            for polymer_data in polymers:
                                success = self.db.insert_price(
                                    polymer_name=polymer_data['polymer_name'],
                                    price=polymer_data.get('price'),
                                    status=polymer_data.get('status', 'PRICED'),
                                    date=message.date,
                                    message_text=message.text[:500],  # Store first 500 chars
                                    message_link=message_link
                                )

                                if success:
                                    processed_count += 1

                            if message_count % 10 == 0:
                                print(f"Scanned {total_scanned} messages, processed {message_count} text messages, found {processed_count} polymer entries...")

                    except Exception as e:
                        print(f"Error processing message {message.id}: {e}")
                        continue

                # Save the latest message ID for future incremental scrapes
                if max_message_id > 0:
                    self._save_last_message_id(chat_id, max_message_id)

                print(f"Scraping complete for chat {chat_id_int}")
                print(f"Total messages scanned: {total_scanned}")
                print(f"Total text messages processed: {message_count}")
                print(f"Total polymer entries stored: {processed_count}")

            except Exception as e:
                print(f"Error scraping chat {chat_id}: {e}")
                import traceback
                traceback.print_exc()
                continue

    async def scrape_new_messages(self):
        """
        Scrape only new messages since the last scrape
        Uses saved message IDs to track progress
        """
        print("Starting incremental scrape for new messages...")

        last_message_ids = self._load_last_message_ids()

        for chat_id in config.TELEGRAM_CHAT_IDS:
            try:
                chat_id_int = int(chat_id)
                last_scraped_id = last_message_ids.get(str(chat_id), 0)

                print(f"Scraping chat: {chat_id_int}")
                print(f"Last scraped message ID: {last_scraped_id}")

                # Get the chat entity
                chat_entity = await self.client.get_entity(chat_id_int)

                # Determine the username/link base
                if hasattr(chat_entity, 'username') and chat_entity.username:
                    link_base = f"https://t.me/{chat_entity.username}"
                else:
                    chat_id_str = str(chat_id_int).replace('-100', '')
                    link_base = f"https://t.me/c/{chat_id_str}"

                print(f"Message link base: {link_base}")

                # Fetch messages newer than last scraped ID
                message_count = 0
                processed_count = 0
                total_scanned = 0
                max_message_id = last_scraped_id

                # Iterate through messages from most recent
                # Use min_id to only get messages newer than last scraped
                async for message in self.client.iter_messages(
                    chat_id_int,
                    limit=None,
                    min_id=last_scraped_id
                ):
                    total_scanned += 1

                    # Track the highest message ID we've seen
                    if message.id > max_message_id:
                        max_message_id = message.id

                    # Only process text messages
                    if not message.text:
                        continue

                    message_count += 1

                    # Skip very short messages
                    if len(message.text) < 20:
                        continue

                    # Parse the message
                    try:
                        polymers = self.parser.parse_message(message.text)

                        if polymers:
                            # Construct message link
                            message_link = f"{link_base}/{message.id}"

                            # Store each polymer price in the database
                            for polymer_data in polymers:
                                success = self.db.insert_price(
                                    polymer_name=polymer_data['polymer_name'],
                                    price=polymer_data.get('price'),
                                    status=polymer_data.get('status', 'PRICED'),
                                    date=message.date,
                                    message_text=message.text[:500],
                                    message_link=message_link
                                )

                                if success:
                                    processed_count += 1

                            if message_count % 10 == 0:
                                print(f"Scanned {total_scanned} messages, processed {message_count} text messages, found {processed_count} polymer entries...")

                    except Exception as e:
                        print(f"Error processing message {message.id}: {e}")
                        continue

                # Save the latest message ID for next scrape
                if max_message_id > last_scraped_id:
                    self._save_last_message_id(chat_id, max_message_id)

                print(f"Incremental scrape complete for chat {chat_id_int}")
                print(f"Total messages scanned: {total_scanned}")
                print(f"Total text messages processed: {message_count}")
                print(f"Total polymer entries stored: {processed_count}")
                print(f"Last message ID: {max_message_id}")

            except Exception as e:
                print(f"Error scraping chat {chat_id}: {e}")
                import traceback
                traceback.print_exc()
                continue

    async def monitor_new_messages(self):
        """
        Monitor and process new messages in real-time
        """
        print("Starting real-time message monitoring...")

        @self.client.on(events.NewMessage(chats=[int(chat_id) for chat_id in config.TELEGRAM_CHAT_IDS]))
        async def handle_new_message(event):
            if not event.message.text:
                return

            try:
                polymers = self.parser.parse_message(event.message.text)

                if polymers:
                    # Get chat entity to construct message link
                    chat = await event.get_chat()
                    if hasattr(chat, 'username') and chat.username:
                        message_link = f"https://t.me/{chat.username}/{event.message.id}"
                    else:
                        # For private groups/channels
                        chat_id_str = str(event.chat_id).replace('-100', '')
                        message_link = f"https://t.me/c/{chat_id_str}/{event.message.id}"

                    for polymer_data in polymers:
                        self.db.insert_price(
                            polymer_name=polymer_data['polymer_name'],
                            price=polymer_data.get('price'),
                            status=polymer_data.get('status', 'PRICED'),
                            date=event.message.date,
                            message_text=event.message.text[:500],
                            message_link=message_link
                        )
                    print(f"Processed {len(polymers)} new polymer entries")

            except Exception as e:
                print(f"Error processing new message: {e}")

        # Keep the client running
        await self.client.run_until_disconnected()


async def run_scraper(days: int = 30):
    """Run the scraper as a standalone process"""
    scraper = PolymerScraper()

    try:
        await scraper.start()
        await scraper.scrape_historical_data(days=days)
    finally:
        await scraper.stop()


async def run_incremental_scraper():
    """Run incremental scraper (only new messages)"""
    scraper = PolymerScraper()

    try:
        await scraper.start()
        await scraper.scrape_new_messages()
    finally:
        await scraper.stop()


async def run_scheduled_scraper(interval_hours: int = 4):
    """
    Run the scraper on a schedule
    Scrapes new messages every N hours
    """
    scraper = PolymerScraper()

    try:
        await scraper.start()
        print(f"✅ Scheduled scraper is running! Will scrape every {interval_hours} hours.")
        print()

        while True:
            try:
                print(f"\n{'='*60}")
                print(f"Starting scheduled scrape at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'='*60}\n")

                await scraper.scrape_new_messages()

                print(f"\n{'='*60}")
                print(f"Scrape complete. Next scrape in {interval_hours} hours.")
                print(f"Next run at: {(datetime.now() + timedelta(hours=interval_hours)).strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'='*60}\n")

                # Wait for the specified interval
                await asyncio.sleep(interval_hours * 3600)

            except Exception as e:
                print(f"Error during scheduled scrape: {e}")
                import traceback
                traceback.print_exc()
                print(f"Will retry in {interval_hours} hours...")
                await asyncio.sleep(interval_hours * 3600)

    except KeyboardInterrupt:
        print("\nScheduled scraper stopped by user.")
    finally:
        await scraper.stop()


if __name__ == "__main__":
    # Run the scraper
    asyncio.run(run_scraper(days=config.DAYS_TO_SCRAPE))
