"""
Main entry point for the Polymer Price Telegram Bot.

Run modes
---------
  bot            – Start the bot only (always-on, answers user queries).
  scraper-loop   – Start the scraper loop only (scrapes every N hours, cleans old data).
  continuous     – Run bot + scraper-loop together in one process.
  scrape         – One-time historical scrape, then exit.
  incremental    – One-time incremental scrape + cleanup, then exit.
  full           – Historical scrape followed by bot startup.

Examples
--------
  python main.py bot
  python main.py scraper-loop --interval 4
  python main.py continuous --interval 4
  python main.py scrape --days 14
"""
import asyncio
import argparse
import sys

from scraper import run_scraper, run_incremental_scraper, run_scraper_loop
from bot import run_bot
from database import PolymerDatabase
import config


async def run_continuous(interval_hours: int = None):
    """
    Run bot and scraper-loop together in one process.
    Both tasks run concurrently via asyncio.gather.
    If either crashes, the other is cancelled gracefully.
    """
    if interval_hours is None:
        interval_hours = config.SCRAPE_INTERVAL_HOURS

    print("=" * 60)
    print("POLYMER PRICE BOT – CONTINUOUS MODE")
    print("=" * 60)
    print(f"  Bot:     always on")
    print(f"  Scraper: every {interval_hours}h, keeping {config.DATA_RETENTION_DAYS}d of data")
    print("=" * 60)
    print()

    # Do a quick incremental scrape before starting
    try:
        print("Initial incremental scrape...")
        await run_incremental_scraper()
        print("Initial scrape complete.\n")
    except Exception as e:
        print(f"Warning during initial scrape: {e}")
        print("Continuing to system startup...\n")

    # Run both concurrently
    try:
        await asyncio.gather(
            run_bot(),
            run_scraper_loop(interval_hours=interval_hours),
        )
    except KeyboardInterrupt:
        print("\nContinuous system stopped by user.")


async def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Polymer Price Telegram Bot – Track and query polymer prices",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py bot                    Start bot only
  python main.py scraper-loop           Start scraper loop only (every 4h)
  python main.py continuous             Bot + scraper in one process
  python main.py scrape --days 14       One-time historical scrape
  python main.py incremental            One-time incremental scrape
"""
    )

    parser.add_argument(
        "mode",
        choices=["bot", "scraper-loop", "continuous", "scrape", "incremental", "full"],
        help="Run mode"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=config.DATA_RETENTION_DAYS,
        help=f"Days to scrape in historical mode (default: {config.DATA_RETENTION_DAYS})"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=config.SCRAPE_INTERVAL_HOURS,
        help=f"Hours between scrapes (default: {config.SCRAPE_INTERVAL_HOURS})"
    )

    args = parser.parse_args()

    # ---------------------------------------------------------------

    if args.mode == "bot":
        print("Starting bot (always-on)...")
        try:
            await run_bot()
        except KeyboardInterrupt:
            print("\nBot stopped by user.")

    elif args.mode == "scraper-loop":
        print(f"Starting scraper loop (every {args.interval}h)...")
        try:
            await run_scraper_loop(interval_hours=args.interval)
        except KeyboardInterrupt:
            print("\nScraper loop stopped by user.")

    elif args.mode == "continuous":
        await run_continuous(interval_hours=args.interval)

    elif args.mode == "scrape":
        print(f"One-time historical scrape ({args.days} days)...")
        try:
            await run_scraper(days=args.days)
            print("Scraping complete!")
        except Exception as e:
            print(f"Error during scraping: {e}")
            sys.exit(1)

    elif args.mode == "incremental":
        print("One-time incremental scrape + cleanup...")
        try:
            await run_incremental_scraper()
            print("Incremental scrape complete!")
        except Exception as e:
            print(f"Error during scraping: {e}")
            sys.exit(1)

    elif args.mode == "full":
        print("=" * 50)
        print("POLYMER PRICE BOT – FULL MODE")
        print("=" * 50)
        print(f"\nStep 1: Historical scrape ({args.days} days)...")
        try:
            await run_scraper(days=args.days)
            print("Historical scrape complete!\n")
        except Exception as e:
            print(f"Error during scraping: {e}")
            print("Continuing to bot startup...\n")

        print("Step 2: Starting bot...")
        try:
            await run_bot()
        except KeyboardInterrupt:
            print("\nBot stopped by user.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nApplication stopped by user.")
        sys.exit(0)
