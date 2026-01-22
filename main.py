"""
Main entry point for the Polymer Price Telegram Bot
"""
import asyncio
import argparse
import sys
from scraper import run_scraper
from bot import run_bot
import config


async def run_full_system():
    """
    Run both scraper and bot together
    First scrapes historical data, then starts the bot
    """
    print("=" * 50)
    print("POLYMER PRICE TELEGRAM BOT")
    print("=" * 50)
    print()

    # Step 1: Run scraper to collect historical data
    print("Step 1: Collecting historical data...")
    print(f"Scraping {config.DAYS_TO_SCRAPE} days of messages from group...")
    print()

    try:
        await run_scraper(days=config.DAYS_TO_SCRAPE)
        print()
        print("✅ Historical data collection complete!")
        print()
    except Exception as e:
        print(f"❌ Error during scraping: {e}")
        print("Continuing to bot startup...")
        print()

    # Step 2: Start the bot
    print("Step 2: Starting the bot...")
    print("The bot will now respond to user queries.")
    print()

    try:
        await run_bot()
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
    except Exception as e:
        print(f"❌ Error running bot: {e}")
        sys.exit(1)


async def main():
    """Main function with command-line argument parsing"""
    parser = argparse.ArgumentParser(
        description="Polymer Price Telegram Bot - Track and query polymer prices"
    )
    parser.add_argument(
        "mode",
        choices=["full", "scrape", "bot"],
        help="Run mode: 'full' (scrape then bot), 'scrape' (scrape only), 'bot' (bot only)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=config.DAYS_TO_SCRAPE,
        help=f"Number of days to scrape (default: {config.DAYS_TO_SCRAPE})"
    )

    args = parser.parse_args()

    if args.mode == "full":
        await run_full_system()

    elif args.mode == "scrape":
        print(f"Scraping {args.days} days of historical data...")
        try:
            await run_scraper(days=args.days)
            print("✅ Scraping complete!")
        except Exception as e:
            print(f"❌ Error during scraping: {e}")
            sys.exit(1)

    elif args.mode == "bot":
        print("Starting bot...")
        try:
            await run_bot()
        except KeyboardInterrupt:
            print("\nBot stopped by user.")
        except Exception as e:
            print(f"❌ Error running bot: {e}")
            sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nApplication stopped by user.")
        sys.exit(0)
