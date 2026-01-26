"""
Main entry point for the Polymer Price Telegram Bot
"""
import asyncio
import argparse
import sys
from scraper import run_scraper, run_incremental_scraper, run_scheduled_scraper
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


async def run_continuous_system(scrape_interval_hours: int = 4):
    """
    Run bot and scheduled scraper together continuously (24/7)
    - Bot responds to user queries
    - Scraper runs every N hours to get new data
    """
    print("=" * 60)
    print("POLYMER PRICE TELEGRAM BOT - CONTINUOUS MODE")
    print("=" * 60)
    print()

    # Step 1: Do initial scraping if needed
    print("Step 1: Checking for initial data...")
    print()

    try:
        # Do a quick incremental scrape to get latest messages
        print("Performing initial incremental scrape...")
        await run_incremental_scraper()
        print()
        print("✅ Initial scrape complete!")
        print()
    except Exception as e:
        print(f"⚠️ Warning during initial scrape: {e}")
        print("Continuing to system startup...")
        print()

    # Step 2: Start both bot and scheduled scraper concurrently
    print("Step 2: Starting continuous operation...")
    print(f"Bot: Will respond to user queries 24/7")
    print(f"Scraper: Will fetch new messages every {scrape_interval_hours} hours")
    print()

    try:
        # Run bot and scheduled scraper in parallel
        await asyncio.gather(
            run_bot(),
            run_scheduled_scraper(interval_hours=scrape_interval_hours)
        )
    except KeyboardInterrupt:
        print("\n\nSystem stopped by user.")
    except Exception as e:
        print(f"❌ Error running system: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


async def main():
    """Main function with command-line argument parsing"""
    parser = argparse.ArgumentParser(
        description="Polymer Price Telegram Bot - Track and query polymer prices"
    )
    parser.add_argument(
        "mode",
        choices=["full", "scrape", "bot", "continuous", "incremental"],
        help="Run mode: 'full' (scrape then bot), 'scrape' (historical scrape only), "
             "'bot' (bot only), 'continuous' (bot + scheduled scraper 24/7), "
             "'incremental' (scrape only new messages)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=config.DAYS_TO_SCRAPE,
        help=f"Number of days to scrape (default: {config.DAYS_TO_SCRAPE})"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=4,
        help="Hours between scrapes in continuous mode (default: 4)"
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

    elif args.mode == "incremental":
        print("Scraping new messages since last scrape...")
        try:
            await run_incremental_scraper()
            print("✅ Incremental scrape complete!")
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

    elif args.mode == "continuous":
        print(f"Starting continuous mode (scraping every {args.interval} hours)...")
        try:
            await run_continuous_system(scrape_interval_hours=args.interval)
        except KeyboardInterrupt:
            print("\nContinuous system stopped by user.")
        except Exception as e:
            print(f"❌ Error running continuous system: {e}")
            sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nApplication stopped by user.")
        sys.exit(0)
