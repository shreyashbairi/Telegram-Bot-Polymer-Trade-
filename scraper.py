"""
Message scraper using Telethon to fetch historical messages from Telegram group
"""
import asyncio
import os
import json
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient, events, errors
from telethon.tl.types import Message
import config
from database import PolymerDatabase
from parser import PolymerParser

# File to store the last scraped message ID for each chat
LAST_MESSAGE_FILE = 'last_scraped_message.json'

# Reconnection settings
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_BASE_DELAY = 2  # seconds


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

    async def _ensure_connected(self):
        """Ensure the Telethon client is connected, reconnecting if necessary."""
        for attempt in range(1, MAX_RECONNECT_ATTEMPTS + 1):
            try:
                if self.client.is_connected():
                    # Verify the connection actually works with a lightweight call
                    try:
                        await self.client.get_me()
                        return True
                    except Exception:
                        print("Client reports connected but call failed, reconnecting...")
                        try:
                            await self.client.disconnect()
                        except Exception:
                            pass

                print(f"Client disconnected — attempting to reconnect (attempt {attempt}/{MAX_RECONNECT_ATTEMPTS})...")
                await self.client.connect()
                if not await self.client.is_user_authorized():
                    await self.client.start(phone=config.TELEGRAM_PHONE)
                print(f"Reconnected successfully on attempt {attempt}")
                return True

            except Exception as e:
                delay = RECONNECT_BASE_DELAY * (2 ** (attempt - 1))
                print(f"Reconnection attempt {attempt} failed: {e}")
                if attempt < MAX_RECONNECT_ATTEMPTS:
                    print(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)

        print("All reconnection attempts exhausted.")
        return False

    async def start(self):
        """Start the Telegram client"""
        await self.client.start(phone=config.TELEGRAM_PHONE)
        print("Scraper client started successfully")

    async def stop(self):
        """Stop the Telegram client"""
        try:
            if self.client.is_connected():
                await self.client.disconnect()
        except Exception:
            pass
        print("Scraper client stopped")

    async def _process_message(self, message, link_base: str, chat_id: str) -> int:
        """Process a single message. Returns the number of polymer entries stored."""
        if not message.text or len(message.text) < 20:
            return 0

        try:
            polymers = self.parser.parse_message(message.text)
            if not polymers:
                return 0

            message_link = f"{link_base}/{message.id}"
            stored = 0
            for polymer_data in polymers:
                success = self.db.insert_price(
                    polymer_name=polymer_data['polymer_name'],
                    price=polymer_data.get('price'),
                    status=polymer_data.get('status', 'PRICED'),
                    date=message.date,
                    message_text=message.text[:500],
                    message_link=message_link,
                    chat_id=chat_id
                )
                if success:
                    stored += 1
            return stored
        except Exception as e:
            print(f"Error processing message {message.id}: {e}")
            return 0

    async def _get_link_base(self, chat_id_int: int) -> str:
        """Get the message link base for a chat."""
        chat_entity = await self.client.get_entity(chat_id_int)
        if hasattr(chat_entity, 'username') and chat_entity.username:
            return f"https://t.me/{chat_entity.username}"
        else:
            chat_id_str = str(chat_id_int).replace('-100', '')
            return f"https://t.me/c/{chat_id_str}"

    async def scrape_historical_data(self, days: int = 30):
        """
        Scrape historical messages from the group with reconnection support
        """
        print(f"Starting to scrape {days} days of historical data...")

        for chat_id in config.TELEGRAM_CHAT_IDS:
            await self._scrape_chat_historical(chat_id, days)

    async def _scrape_chat_historical(self, chat_id: str, days: int, retry_count: int = 0):
        """Scrape a single chat historically with retry on disconnection."""
        max_retries = 3
        try:
            chat_id_int = int(chat_id)
            print(f"Scraping chat: {chat_id_int}")

            if not await self._ensure_connected():
                print(f"Cannot connect to scrape chat {chat_id}. Skipping.")
                return

            link_base = await self._get_link_base(chat_id_int)
            print(f"Message link base: {link_base}")

            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            message_count = 0
            processed_count = 0
            total_scanned = 0
            max_message_id = 0

            async for message in self.client.iter_messages(chat_id_int, limit=None):
                total_scanned += 1

                if message.id > max_message_id:
                    max_message_id = message.id

                if message.date < cutoff_date:
                    print(f"Reached messages older than {days} days, stopping...")
                    break

                if message.text:
                    message_count += 1

                stored = await self._process_message(message, link_base, chat_id)
                processed_count += stored

                if message_count > 0 and message_count % 10 == 0:
                    print(f"Scanned {total_scanned} messages, processed {message_count} text messages, found {processed_count} polymer entries...")

            if max_message_id > 0:
                self._save_last_message_id(chat_id, max_message_id)

            print(f"Scraping complete for chat {chat_id_int}")
            print(f"Total messages scanned: {total_scanned}")
            print(f"Total text messages processed: {message_count}")
            print(f"Total polymer entries stored: {processed_count}")

        except (ConnectionError, errors.RPCError, OSError, RuntimeError, AttributeError) as e:
            error_msg = str(e)
            print(f"Connection lost while scraping chat {chat_id}: {error_msg}")

            if retry_count < max_retries:
                print(f"Will attempt reconnection for chat {chat_id} (retry {retry_count + 1}/{max_retries})...")
                delay = RECONNECT_BASE_DELAY * (2 ** retry_count)
                await asyncio.sleep(delay)

                if await self._ensure_connected():
                    await self._scrape_chat_historical(chat_id, days, retry_count + 1)
                else:
                    print(f"Could not reconnect. Skipping chat {chat_id}.")
            else:
                print(f"Max retries reached for chat {chat_id}. Skipping.")

        except Exception as e:
            print(f"Error scraping chat {chat_id}: {e}")
            import traceback
            traceback.print_exc()

    async def scrape_new_messages(self):
        """
        Scrape only new messages since the last scrape with reconnection support
        """
        print("Starting incremental scrape...")

        last_message_ids = self._load_last_message_ids()

        for chat_id in config.TELEGRAM_CHAT_IDS:
            last_scraped_id = last_message_ids.get(str(chat_id), 0)
            await self._scrape_chat_incremental(chat_id, last_scraped_id)

    async def _scrape_chat_incremental(self, chat_id: str, last_scraped_id: int, retry_count: int = 0):
        """Scrape a single chat incrementally with retry on disconnection."""
        max_retries = 3
        try:
            chat_id_int = int(chat_id)
            print(f"Scraping chat: {chat_id_int}  (after message {last_scraped_id})")

            if not await self._ensure_connected():
                print(f"Cannot connect to scrape chat {chat_id}. Skipping.")
                return

            link_base = await self._get_link_base(chat_id_int)
            print(f"Message link base: {link_base}")

            message_count = 0
            processed_count = 0
            total_scanned = 0
            max_message_id = last_scraped_id

            async for message in self.client.iter_messages(
                chat_id_int,
                limit=None,
                min_id=last_scraped_id
            ):
                total_scanned += 1

                if message.id > max_message_id:
                    max_message_id = message.id

                if message.text:
                    message_count += 1

                stored = await self._process_message(message, link_base, chat_id)
                processed_count += stored

                if message_count > 0 and message_count % 10 == 0:
                    print(f"Scanned {total_scanned} messages, processed {message_count} text messages, found {processed_count} polymer entries...")

            if max_message_id > last_scraped_id:
                self._save_last_message_id(chat_id, max_message_id)

            print(f"Chat {chat_id_int} complete: scanned={total_scanned}, text={message_count}, entries={processed_count}, last_id={max_message_id}")

        except (ConnectionError, errors.RPCError, OSError, RuntimeError, AttributeError) as e:
            error_msg = str(e)
            print(f"Connection lost while scraping chat {chat_id}: {error_msg}")

            if retry_count < max_retries:
                print(f"Will attempt reconnection for chat {chat_id} (retry {retry_count + 1}/{max_retries})...")
                delay = RECONNECT_BASE_DELAY * (2 ** retry_count)
                await asyncio.sleep(delay)

                if await self._ensure_connected():
                    await self._scrape_chat_incremental(chat_id, last_scraped_id, retry_count + 1)
                else:
                    print(f"Could not reconnect. Skipping chat {chat_id}.")
            else:
                print(f"Max retries reached for chat {chat_id}. Skipping.")

        except Exception as e:
            print(f"Error scraping chat {chat_id}: {e}")
            import traceback
            traceback.print_exc()

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
                            message_link=message_link,
                            chat_id=str(event.chat_id)
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
    Scrapes new messages every N hours with reconnection support
    """
    scraper = PolymerScraper()

    try:
        await scraper.start()
        print(f"Scheduled scraper is running! Will scrape every {interval_hours} hours.")
        print()

        while True:
            try:
                print(f"\n{'='*60}")
                print(f"Starting scheduled scrape at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'='*60}\n")

                # Ensure connection is alive before scraping
                if not await scraper._ensure_connected():
                    print("Cannot connect for scheduled scrape. Will retry next interval.")
                else:
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
