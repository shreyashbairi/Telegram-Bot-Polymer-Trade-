"""
Message scraper using Telethon to fetch historical messages from Telegram group.
Designed to run independently alongside the bot process.
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

# Scraper state file - tracks last message IDs and scrape metadata
SCRAPER_STATE_FILE = 'scraper_state.json'

# Legacy file name (migrated automatically)
LEGACY_STATE_FILE = 'last_scraped_message.json'


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

    # ------------------------------------------------------------------ #
    #  State persistence (replaces old last_scraped_message.json)
    # ------------------------------------------------------------------ #

    def _load_state(self) -> dict:
        """
        Load scraper state from file.
        Automatically migrates from the legacy format if needed.

        State format:
        {
            "chats": {
                "<chat_id>": {
                    "last_message_id": 12345,
                    "last_scrape_time": "2026-02-27T10:30:00"
                }
            },
            "last_cleanup_time": "2026-02-27T10:30:00",
            "data_retention_days": 14
        }
        """
        # Try new state file first
        if os.path.exists(SCRAPER_STATE_FILE):
            try:
                with open(SCRAPER_STATE_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading scraper state: {e}")
                return self._empty_state()

        # Migrate from legacy format
        if os.path.exists(LEGACY_STATE_FILE):
            try:
                with open(LEGACY_STATE_FILE, 'r') as f:
                    legacy = json.load(f)
                # Convert flat {chat_id: msg_id} to new format
                state = self._empty_state()
                for chat_id, msg_id in legacy.items():
                    state['chats'][str(chat_id)] = {
                        'last_message_id': msg_id,
                        'last_scrape_time': None
                    }
                self._save_state(state)
                print(f"Migrated legacy state file to {SCRAPER_STATE_FILE}")
                return state
            except Exception as e:
                print(f"Error migrating legacy state: {e}")

        return self._empty_state()

    def _empty_state(self) -> dict:
        return {
            'chats': {},
            'last_cleanup_time': None,
            'data_retention_days': config.DATA_RETENTION_DAYS
        }

    def _save_state(self, state: dict):
        """Save full scraper state to file"""
        try:
            with open(SCRAPER_STATE_FILE, 'w') as f:
                json.dump(state, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving scraper state: {e}")

    def _update_chat_state(self, chat_id: str, message_id: int):
        """Update the state for a single chat after scraping"""
        state = self._load_state()
        chat_key = str(chat_id)

        if chat_key not in state['chats']:
            state['chats'][chat_key] = {}

        old_id = state['chats'][chat_key].get('last_message_id', 0)
        if message_id > old_id:
            state['chats'][chat_key]['last_message_id'] = message_id

        state['chats'][chat_key]['last_scrape_time'] = datetime.now().isoformat()
        self._save_state(state)
        print(f"Saved state: chat {chat_id} -> message_id {message_id}")

    def _get_last_message_id(self, chat_id: str) -> int:
        """Get the last scraped message ID for a chat"""
        state = self._load_state()
        chat_data = state['chats'].get(str(chat_id), {})
        return chat_data.get('last_message_id', 0)

    def _record_cleanup(self):
        """Record that a cleanup was performed"""
        state = self._load_state()
        state['last_cleanup_time'] = datetime.now().isoformat()
        state['data_retention_days'] = config.DATA_RETENTION_DAYS
        self._save_state(state)

    # ------------------------------------------------------------------ #
    #  Telegram client lifecycle
    # ------------------------------------------------------------------ #

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

    # ------------------------------------------------------------------ #
    #  Message link helper
    # ------------------------------------------------------------------ #

    async def _get_link_base(self, chat_id_int: int) -> str:
        """Get the message link base URL for a chat"""
        chat_entity = await self.client.get_entity(chat_id_int)
        if hasattr(chat_entity, 'username') and chat_entity.username:
            return f"https://t.me/{chat_entity.username}"
        else:
            chat_id_str = str(chat_id_int).replace('-100', '')
            return f"https://t.me/c/{chat_id_str}"

    # ------------------------------------------------------------------ #
    #  Core scraping
    # ------------------------------------------------------------------ #

    async def scrape_historical_data(self, days: int = None):
        """
        Scrape historical messages from all configured groups.
        Used for initial data population.
        """
        if days is None:
            days = config.DATA_RETENTION_DAYS

        print(f"Starting historical scrape ({days} days)...")

        for chat_id in config.TELEGRAM_CHAT_IDS:
            chat_id_int = int(chat_id)
            max_message_id = 0
            message_count = 0
            processed_count = 0
            total_scanned = 0

            try:
                print(f"\nScraping chat: {chat_id_int}")

                link_base = await self._get_link_base(chat_id_int)
                print(f"Message link base: {link_base}")

                cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

                async for message in self.client.iter_messages(chat_id_int, limit=None):
                    total_scanned += 1

                    if message.id > max_message_id:
                        max_message_id = message.id

                    if message.date < cutoff_date:
                        print(f"Reached messages older than {days} days, stopping...")
                        break

                    if not message.text:
                        continue

                if message.text:
                    message_count += 1

                    if len(message.text) < 20:
                        continue

                    # Skip messages already in the DB (avoids re-parsing + OpenAI cost)
                    message_link = f"{link_base}/{message.id}"
                    if self.db.message_link_exists(message_link):
                        continue

                    try:
                        polymers = self.parser.parse_message(message.text)

                        if polymers:
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
                                    processed_count += 1

                            if message_count % 10 == 0:
                                print(f"  Scanned {total_scanned}, processed {message_count} text, found {processed_count} entries...")

                    except Exception as e:
                        print(f"  Error processing message {message.id}: {e}")
                        continue

            except Exception as e:
                print(f"Error scraping chat {chat_id} (partial): {e}")
                import traceback
                traceback.print_exc()
            finally:
                # Always save progress — even after Telethon security errors
                if max_message_id > 0:
                    self._update_chat_state(chat_id, max_message_id)
                print(f"Chat {chat_id_int} {'complete' if not max_message_id else 'saved'}: "
                      f"scanned={total_scanned}, text={message_count}, entries={processed_count}")

    async def scrape_new_messages(self):
        """
        Incremental scrape: only fetch messages newer than the last recorded ID.
        If no prior state exists for a chat, falls back to the retention window
        so it doesn't accidentally crawl the entire chat history.
        """
        print("Starting incremental scrape...")

        # Date guard: never go further back than the retention window
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=config.DATA_RETENTION_DAYS)

        for chat_id in config.TELEGRAM_CHAT_IDS:
            chat_id_int = int(chat_id)
            last_scraped_id = self._get_last_message_id(chat_id)
            max_message_id = last_scraped_id
            message_count = 0
            processed_count = 0
            total_scanned = 0

            try:
                if last_scraped_id == 0:
                    print(f"\nScraping chat: {chat_id_int}  (no prior state — fetching last {config.DATA_RETENTION_DAYS} days)")
                else:
                    print(f"\nScraping chat: {chat_id_int}  (after message {last_scraped_id})")

                link_base = await self._get_link_base(chat_id_int)

                async for message in self.client.iter_messages(
                    chat_id_int,
                    limit=None,
                    min_id=last_scraped_id
                ):
                    total_scanned += 1

                    # Safety net: stop if we've gone past the retention window
                    # (only matters when last_scraped_id == 0)
                    if message.date < cutoff_date:
                        print(f"  Reached retention boundary ({config.DATA_RETENTION_DAYS}d), stopping...")
                        break

                    if message.id > max_message_id:
                        max_message_id = message.id

                    if not message.text:
                        continue

                if message.text:
                    message_count += 1

                    if len(message.text) < 20:
                        continue

                    # Skip messages already in the DB (avoids re-parsing + OpenAI cost)
                    message_link = f"{link_base}/{message.id}"
                    if self.db.message_link_exists(message_link):
                        continue

                    try:
                        polymers = self.parser.parse_message(message.text)

                        if polymers:
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
                                    processed_count += 1

                            if message_count % 10 == 0:
                                print(f"  Scanned {total_scanned}, processed {message_count} text, found {processed_count} entries...")

                    except Exception as e:
                        print(f"  Error processing message {message.id}: {e}")
                        continue

            except Exception as e:
                print(f"Error scraping chat {chat_id} (partial): {e}")
                import traceback
                traceback.print_exc()
            finally:
                # Always save progress — even after Telethon security errors
                if max_message_id > last_scraped_id:
                    self._update_chat_state(chat_id, max_message_id)
                print(f"Chat {chat_id_int} {'complete' if not total_scanned else 'saved'}: "
                      f"scanned={total_scanned}, text={message_count}, entries={processed_count}, last_id={max_message_id}")

    def cleanup_old_data(self):
        """Delete database records older than the retention window"""
        retention = config.DATA_RETENTION_DAYS
        print(f"Cleaning up data older than {retention} days...")
        deleted = self.db.delete_old_data(retention_days=retention)
        self._record_cleanup()
        return deleted

    # ------------------------------------------------------------------ #
    #  Scheduled loop (runs independently or alongside the bot)
    # ------------------------------------------------------------------ #

    async def run_loop(self, interval_hours: int = None):
        """
        Run the scraper on a repeating schedule.
        Each cycle: incremental scrape + delete old data.
        Designed to run forever (until Ctrl-C or process kill).
        """
        if interval_hours is None:
            interval_hours = config.SCRAPE_INTERVAL_HOURS

        print(f"Scheduled scraper starting (every {interval_hours}h, retention {config.DATA_RETENTION_DAYS}d)")

        # Print current state
        state = self._load_state()
        for cid, cdata in state.get('chats', {}).items():
            print(f"  Chat {cid}: last_message_id={cdata.get('last_message_id', 0)}, "
                  f"last_scrape={cdata.get('last_scrape_time', 'never')}")
        print()

        while True:
            try:
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(f"\n{'='*60}")
                print(f"Scrape cycle starting at {now}")
                print(f"{'='*60}\n")

                # Step 1: Scrape new messages
                await self.scrape_new_messages()

                # Step 2: Delete data older than 2 weeks
                self.cleanup_old_data()

                # Step 3: Print DB status
                date_range = self.db.get_data_date_range()
                if date_range:
                    print(f"\nDB status: {date_range['total_records']} records, "
                          f"{date_range['oldest_date']} to {date_range['newest_date']}")

                next_run = (datetime.now() + timedelta(hours=interval_hours)).strftime('%Y-%m-%d %H:%M:%S')
                print(f"\nNext scrape at: {next_run}")
                print(f"{'='*60}\n")

                await asyncio.sleep(interval_hours * 3600)

            except asyncio.CancelledError:
                print("Scraper loop cancelled")
                break
            except Exception as e:
                print(f"Error during scrape cycle: {e}")
                import traceback
                traceback.print_exc()
                print(f"Will retry in {interval_hours} hours...")
                await asyncio.sleep(interval_hours * 3600)


# ------------------------------------------------------------------ #
#  Standalone entry points
# ------------------------------------------------------------------ #

async def run_scraper(days: int = None):
    """One-time historical scrape"""
    if days is None:
        days = config.DATA_RETENTION_DAYS
    scraper = PolymerScraper()
    try:
        await scraper.start()
        await scraper.scrape_historical_data(days=days)
        scraper.cleanup_old_data()
    finally:
        await scraper.stop()


async def run_incremental_scraper():
    """One-time incremental scrape + cleanup"""
    scraper = PolymerScraper()
    try:
        await scraper.start()
        await scraper.scrape_new_messages()
        scraper.cleanup_old_data()
    finally:
        await scraper.stop()


async def run_scraper_loop(interval_hours: int = None):
    """
    Standalone scraper loop process.
    Keeps the Telethon client alive and scrapes on schedule.
    Can be run in its own terminal / process alongside the bot.
    """
    if interval_hours is None:
        interval_hours = config.SCRAPE_INTERVAL_HOURS
    scraper = PolymerScraper()
    try:
        await scraper.start()
        await scraper.run_loop(interval_hours=interval_hours)
    except KeyboardInterrupt:
        print("\nScraper loop stopped by user.")
    finally:
        await scraper.stop()


if __name__ == "__main__":
    asyncio.run(run_scraper_loop())
