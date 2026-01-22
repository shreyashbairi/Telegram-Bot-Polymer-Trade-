"""
Message scraper using Telethon to fetch historical messages from Telegram group
"""
import asyncio
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient, events
from telethon.tl.types import Message
import config
from database import PolymerDatabase
from parser import PolymerParser

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

                # Calculate the cutoff date (timezone-aware to match Telegram message dates)
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

                # Fetch messages
                message_count = 0
                processed_count = 0
                total_scanned = 0

                # Iterate through messages from most recent
                async for message in self.client.iter_messages(chat_id_int, limit=None):
                    total_scanned += 1

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
                            # Store each polymer price in the database
                            for polymer_data in polymers:
                                success = self.db.insert_price(
                                    polymer_name=polymer_data['polymer_name'],
                                    price=polymer_data.get('price'),
                                    status=polymer_data.get('status', 'AVAILABLE'),
                                    date=message.date,
                                    message_text=message.text[:500],  # Store first 500 chars
                                    message_id=message.id
                                )

                                if success:
                                    processed_count += 1

                            if message_count % 10 == 0:
                                print(f"Scanned {total_scanned} messages, processed {message_count} text messages, found {processed_count} polymer entries...")

                    except Exception as e:
                        print(f"Error processing message {message.id}: {e}")
                        continue

                print(f"Scraping complete for chat {chat_id_int}")
                print(f"Total messages scanned: {total_scanned}")
                print(f"Total text messages processed: {message_count}")
                print(f"Total polymer entries stored: {processed_count}")

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
                    for polymer_data in polymers:
                        self.db.insert_price(
                            polymer_name=polymer_data['polymer_name'],
                            price=polymer_data.get('price'),
                            status=polymer_data.get('status', 'AVAILABLE'),
                            date=event.message.date,
                            message_text=event.message.text[:500],
                            message_id=event.message.id
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


if __name__ == "__main__":
    # Run the scraper
    asyncio.run(run_scraper(days=config.DAYS_TO_SCRAPE))
