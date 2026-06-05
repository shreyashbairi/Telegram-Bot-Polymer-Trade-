"""
Message scraper using Telethon to fetch historical messages from Telegram group.
Designed to run independently alongside the bot process.
"""
import asyncio
import os
import json
import socket
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
RECONNECT_BASE_DELAY = 2           # seconds
ERROR_RETRY_DELAY = 5 * 60         # 5-minute retry when a whole cycle fails
                                    # (previously it slept the full scrape interval)
CHAT_SCRAPE_RETRIES = 3            # per-chat reconnect-and-retry attempts when the
                                    # socket drops mid-scrape (e.g. WinError 64),
                                    # instead of waiting for the next cycle


def _has_internet(host="8.8.8.8", port=53, timeout=5):
    """Lightweight TCP check so we don't spin on a disconnected wifi."""
    try:
        socket.setdefaulttimeout(timeout)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False


class PolymerScraper:
    def __init__(self):
        """Initialize Telegram client"""
        # Resilience options matter on a 24/7 laptop: the MTProto socket gets
        # reset by wifi blips / idle timeouts (Windows surfaces this as
        # "[WinError 64] The specified network name is no longer available").
        # auto_reconnect + generous retries let Telethon transparently rebuild
        # the connection instead of bubbling the error up into a scrape cycle.
        self.client = TelegramClient(
            'polymer_scraper_session',
            config.TELEGRAM_API_ID,
            config.TELEGRAM_API_HASH,
            auto_reconnect=True,
            connection_retries=10,
            retry_delay=2,
            request_retries=10,
            timeout=30,
        )
        self.db = PolymerDatabase()
        self.parser = PolymerParser()

    # ------------------------------------------------------------------ #
    #  State persistence
    # ------------------------------------------------------------------ #

    def _load_state(self) -> dict:
        """
        Load scraper state from file.
        Automatically migrates from the legacy format if needed.
        Also cleans whitespace from existing chat_id keys (one-time migration
        for state files corrupted by spaces in the TELEGRAM_CHAT_IDS env var).

        State format:
        {
            "chats": {
                "<chat_id>": {
                    "last_message_id": 12345,
                    "last_scrape_time": "2026-02-27T10:30:00"
                }
            },
            "last_cleanup_time": "2026-02-27T10:30:00",
            "data_retention_days": 21
        }
        """
        # Try new state file first
        if os.path.exists(SCRAPER_STATE_FILE):
            try:
                with open(SCRAPER_STATE_FILE, 'r') as f:
                    state = json.load(f)
                # Clean any chat keys that contain whitespace (merging with
                # the clean version if it already exists)
                cleaned = self._clean_whitespace_keys(state)
                if cleaned:
                    self._save_state(state)
                return state
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
                    state['chats'][str(chat_id).strip()] = {
                        'last_message_id': msg_id,
                        'last_scrape_time': None
                    }
                self._save_state(state)
                print(f"Migrated legacy state file to {SCRAPER_STATE_FILE}")
                return state
            except Exception as e:
                print(f"Error migrating legacy state: {e}")

        return self._empty_state()

    def _clean_whitespace_keys(self, state: dict) -> bool:
        """Remove whitespace from chat_id keys. Returns True if anything changed."""
        chats = state.get('chats', {})
        dirty_keys = [k for k in chats.keys() if k != k.strip()]
        if not dirty_keys:
            return False

        for dirty in dirty_keys:
            clean = dirty.strip()
            if clean in chats:
                # Merge: keep the entry with the newer last_message_id
                existing = chats[clean].get('last_message_id', 0)
                migrated = chats[dirty].get('last_message_id', 0)
                if migrated > existing:
                    chats[clean] = chats[dirty]
            else:
                chats[clean] = chats[dirty]
            del chats[dirty]
            print(f"Cleaned whitespace in state key: '{dirty}' -> '{clean}'")

        state['chats'] = chats
        return True

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
        chat_key = str(chat_id).strip()   # defensive strip

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
        chat_data = state['chats'].get(str(chat_id).strip(), {})
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

    async def _ensure_connected(self) -> bool:
        """Ensure the Telethon client is connected, reconnecting if necessary.
        Returns True if the client is usable, False if all attempts failed."""
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

                # Don't even try if wifi is dead — saves 30s of timeouts
                if not _has_internet():
                    print("No internet detected, will retry shortly...")
                    await asyncio.sleep(RECONNECT_BASE_DELAY * (2 ** (attempt - 1)))
                    continue

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

        # Make sure we're connected before doing anything
        if not await self._ensure_connected():
            print("Could not establish connection — aborting historical scrape.")
            return

        for chat_id in config.TELEGRAM_CHAT_IDS:
            chat_id_int = int(chat_id)
            max_message_id = 0
            message_count = 0
            processed_count = 0
            total_scanned = 0
            success = False

            try:
                # Re-check connection per chat — large history iteration can
                # be long enough for the socket to die mid-loop
                if not await self._ensure_connected():
                    print(f"Lost connection before chat {chat_id_int}, skipping this chat.")
                    continue

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

                    # ---- BUG FIX ----
                    # Everything below used to live OUTSIDE this `async for`
                    # loop (indented one level less), which meant only ONE
                    # message per chat ever got processed. Correctly indented
                    # now, so every text message is parsed.
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
                                ok = self.db.insert_price(
                                    polymer_name=polymer_data['polymer_name'],
                                    price=polymer_data.get('price'),
                                    status=polymer_data.get('status', 'PRICED'),
                                    date=message.date,
                                    message_text=message.text[:500],
                                    message_link=message_link,
                                    chat_id=chat_id
                                )

                                if ok:
                                    processed_count += 1

                            if message_count % 10 == 0:
                                print(f"  Scanned {total_scanned}, processed {message_count} text, found {processed_count} entries...")

                    except Exception as e:
                        print(f"  Error processing message {message.id}: {e}")
                        continue

                success = True

            except OSError as e:
                # Covers ConnectionError and the Windows "[WinError 64] network
                # name no longer available" socket reset.
                print(f"Connection lost while scraping chat {chat_id}: {e}")
            except Exception as e:
                print(f"Error scraping chat {chat_id} (partial): {e}")
                import traceback
                traceback.print_exc()
            finally:
                # Always save progress — even after Telethon security errors
                if max_message_id > 0:
                    self._update_chat_state(chat_id, max_message_id)
                status_str = "complete" if success else "partial"
                print(f"Chat {chat_id_int} {status_str}: "
                      f"scanned={total_scanned}, text={message_count}, entries={processed_count}")

    async def scrape_new_messages(self):
        """
        Incremental scrape: only fetch messages newer than the last recorded ID.
        If no prior state exists for a chat, falls back to the retention window
        so it doesn't accidentally crawl the entire chat history.
        """
        print("Starting incremental scrape...")

        # Make sure we're connected before doing anything
        if not await self._ensure_connected():
            print("Could not establish connection — aborting this cycle.")
            return

        # Date guard: never go further back than the retention window
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=config.DATA_RETENTION_DAYS)

        for chat_id in config.TELEGRAM_CHAT_IDS:
            chat_id_int = int(chat_id)

            # Retry a chat a few times if the socket drops mid-scrape (WinError
            # 64 etc.). Each attempt re-reads the saved last_message_id, so a
            # retry resumes from the progress the partial attempt already saved
            # instead of waiting for the next 4-hour cycle.
            for attempt in range(1, CHAT_SCRAPE_RETRIES + 1):
                last_scraped_id = self._get_last_message_id(chat_id)
                max_message_id = last_scraped_id
                message_count = 0
                processed_count = 0
                total_scanned = 0
                success = False
                connection_dropped = False

                try:
                    # Re-check connection per chat — a cycle iterating a large
                    # chat can be long enough for the socket to drop mid-loop.
                    if not await self._ensure_connected():
                        print(f"Lost connection before chat {chat_id_int}, skipping this chat.")
                        break

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
                                    ok = self.db.insert_price(
                                        polymer_name=polymer_data['polymer_name'],
                                        price=polymer_data.get('price'),
                                        status=polymer_data.get('status', 'PRICED'),
                                        date=message.date,
                                        message_text=message.text[:500],
                                        message_link=message_link,
                                        chat_id=chat_id
                                    )

                                    if ok:
                                        processed_count += 1

                                if message_count % 10 == 0:
                                    print(f"  Scanned {total_scanned}, processed {message_count} text, found {processed_count} entries...")

                        except Exception as e:
                            print(f"  Error processing message {message.id}: {e}")
                            continue

                    success = True

                except OSError as e:
                    # Transient socket reset (ConnectionError/ConnectionReset and
                    # the Windows "[WinError 64] network name no longer available"
                    # are all OSError). Reconnect and retry this chat below.
                    connection_dropped = True
                    print(f"Connection lost while scraping chat {chat_id_int} "
                          f"(attempt {attempt}/{CHAT_SCRAPE_RETRIES}): {e}")
                except Exception as e:
                    print(f"Error scraping chat {chat_id} (partial): {e}")
                    import traceback
                    traceback.print_exc()
                finally:
                    # Always save progress — even after a partial/failed attempt
                    if max_message_id > last_scraped_id:
                        self._update_chat_state(chat_id, max_message_id)
                    status_str = "complete" if success else "partial"
                    print(f"Chat {chat_id_int} {status_str}: "
                          f"scanned={total_scanned}, text={message_count}, entries={processed_count}, last_id={max_message_id}")

                # Done with this chat unless the socket dropped — then retry.
                if success or not connection_dropped:
                    break
                if attempt < CHAT_SCRAPE_RETRIES:
                    delay = RECONNECT_BASE_DELAY * attempt
                    print(f"  Reconnecting and retrying chat {chat_id_int} in {delay}s...")
                    await asyncio.sleep(delay)

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

                # Proactively check the connection at the top of each cycle.
                # The Telethon client tends to silently die during the long
                # asyncio.sleep between cycles — catching it here avoids the
                # "Cannot send requests while disconnected" cascade.
                await self._ensure_connected()

                # Step 1: Scrape new messages
                await self.scrape_new_messages()

                # Step 2: Delete data older than the retention window (3 weeks)
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
                # Retry in 5 minutes instead of waiting the full interval.
                # A full 4-hour wait after a transient failure means losing
                # half a day of data for nothing.
                print(f"Will retry in {ERROR_RETRY_DELAY // 60} minutes...")
                await asyncio.sleep(ERROR_RETRY_DELAY)


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