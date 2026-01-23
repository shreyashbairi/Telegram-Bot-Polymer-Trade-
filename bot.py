"""
Telegram bot for handling user queries about polymer prices
"""
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
import config
from database import PolymerDatabase

class PolymerPriceBot:
    def __init__(self):
        """Initialize the bot"""
        self.db = PolymerDatabase()
        self.app = None

    def build_application(self):
        """Build the telegram bot application"""
        self.app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

        # Add handlers - only respond to private chats
        self.app.add_handler(CommandHandler("start", self.start_command, filters=filters.ChatType.PRIVATE))
        self.app.add_handler(CommandHandler("help", self.help_command, filters=filters.ChatType.PRIVATE))
        self.app.add_handler(CommandHandler("list", self.list_polymers_command, filters=filters.ChatType.PRIVATE))
        self.app.add_handler(CommandHandler("search", self.search_command, filters=filters.ChatType.PRIVATE))
        self.app.add_handler(CommandHandler("daily", self.daily_command, filters=filters.ChatType.PRIVATE))
        self.app.add_handler(CommandHandler("clear", self.clear_command, filters=filters.ChatType.PRIVATE))
        self.app.add_handler(CommandHandler("compare", self.compare_command, filters=filters.ChatType.PRIVATE))
        self.app.add_handler(CallbackQueryHandler(self.handle_polymer_selection))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, self.handle_text_query))

        return self.app

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_message = """
Welcome to the Polymer Price Bot! 🏭

I can help you check historical prices for various polymers.

Commands:
/list - Browse all available polymers
/search <name> - Search for specific polymers
/daily [date] - View all polymers for a specific day
/compare <polymer> [polymer] [date] - Compare polymer prices
/clear - Clear chat and restart
/help - Show detailed help

You can also just type the polymer name (e.g., "J150", "Y130") to get its 7-day price history with message links.
"""
        await update.message.reply_text(welcome_message)

        # Show polymer selection menu
        await self.show_polymer_menu(update, context)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_message = """
Polymer Price Bot Help 📊

How to use:
1. Use /list to see all available polymers
2. Use /search <name> to search for specific polymers
3. Use /daily [date] to view all polymers for a day
4. Use /compare to compare polymer prices
5. Click on a polymer name or type it directly
6. Get price history for the last 7 days

Commands:
/start - Start the bot and show menu
/list - Browse all polymers
/search <name> - Search for polymers (e.g., /search J150)
/daily [date] - View all polymers for a day (e.g., /daily 23.01.26)
/compare <polymer> [polymer] [date] - Compare prices
/clear - Clear chat and restart bot
/help - Show this help message

Compare Examples:
- /compare J150 - Compare J150 against its 7-day high/low
- /compare J150 Y130 - Compare J150 vs Y130 for 7 days
- /compare J150 23.01.26 - Compare J150 for specific date
- /compare J150 Y130 23.01.26 - Compare both on specific date

The bot shows:
✅ Daily prices for the last 7 days
✅ Message links for each price entry
✅ Price comparisons and trends
✅ All polymers with prices for a specific day
"""
        await update.message.reply_text(help_message)

    async def list_polymers_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /list command"""
        await self.show_polymer_menu(update, context)

    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search command"""
        if not context.args:
            await update.message.reply_text(
                "Please provide a search query.\n\n"
                "Usage: /search <polymer_name>\n"
                "Example: /search J150"
            )
            return

        search_query = " ".join(context.args)
        results = self.db.search_polymers(search_query)

        if not results:
            await update.message.reply_text(
                f"No polymers found matching '{search_query}'.\n\n"
                "Try a different search term or use /list to see all polymers."
            )
            return

        # Build keyboard with search results
        keyboard = []
        for polymer in results:
            button_text = f"{polymer['display_name']}"
            keyboard.append([InlineKeyboardButton(
                button_text,
                callback_data=f"polymer:{polymer['normalized_name']}"
            )])

        reply_markup = InlineKeyboardMarkup(keyboard)
        message_text = f"🔍 Search results for '{search_query}' ({len(results)} found):"

        await update.message.reply_text(message_text, reply_markup=reply_markup)

    async def daily_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /daily [date] command"""
        target_date = None

        # Parse date if provided
        if context.args:
            date_str = context.args[0]
            # Expected format: DD.MM.YY (e.g., 23.01.26)
            try:
                # Parse the date - try both DD.MM.YY and DD.MM.YYYY formats
                date_patterns = [
                    ('%d.%m.%y', date_str),
                    ('%d.%m.%Y', date_str)
                ]

                for pattern, date_input in date_patterns:
                    try:
                        target_date = datetime.strptime(date_input, pattern)
                        break
                    except ValueError:
                        continue

                if not target_date:
                    await update.message.reply_text(
                        "Invalid date format. Please use DD.MM.YY\n\n"
                        "Example: /daily 23.01.26"
                    )
                    return

            except Exception as e:
                await update.message.reply_text(
                    "Error parsing date. Please use DD.MM.YY\n\n"
                    "Example: /daily 23.01.26"
                )
                return
        else:
            # No date provided, use latest date with data
            latest_date_str = self.db.get_latest_date_with_data()
            if not latest_date_str:
                await update.message.reply_text("No polymer data available in the database.")
                return

            target_date = datetime.strptime(latest_date_str, '%Y-%m-%d')

        # Get all polymers for this date
        polymers = self.db.get_all_polymers_for_date(target_date)

        if not polymers:
            await update.message.reply_text(
                f"No polymer data found for {target_date.strftime('%d.%m.%Y')}."
            )
            return

        # Build the response message
        message = f"📅 Daily Polymer Prices - {target_date.strftime('%d.%m.%Y')}\n"
        message += f"Total Polymers: {len(polymers)}\n"
        message += "=" * 40 + "\n\n"

        # Group polymers to avoid message length issues
        # Telegram has a 4096 character limit per message
        messages_to_send = []
        current_message = message

        for idx, polymer in enumerate(polymers, 1):
            polymer_info = f"{idx}. {polymer['polymer_name']}\n"
            polymer_info += f"   💰 Price: {polymer['price']:.2f}\n"
            if polymer.get('message_link'):
                polymer_info += f"   🔗 {polymer['message_link']}\n"
            polymer_info += "\n"

            # Check if adding this polymer would exceed the limit
            if len(current_message) + len(polymer_info) > 4000:
                messages_to_send.append(current_message)
                current_message = f"📅 Daily Polymer Prices - {target_date.strftime('%d.%m.%Y')} (continued)\n\n"

            current_message += polymer_info

        # Add the last message
        if current_message:
            messages_to_send.append(current_message)

        # Send all messages
        for msg in messages_to_send:
            await update.message.reply_text(msg, disable_web_page_preview=True)

    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /clear command - simulates clearing chat and restarts"""
        # Send empty lines to simulate clearing
        clear_message = "\n" * 50 + "🔄 Chat cleared!\n"
        await update.message.reply_text(clear_message)

        # Execute start command
        await self.start_command(update, context)

    async def compare_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /compare command with multiple modes"""
        if not context.args:
            await update.message.reply_text(
                "Please provide polymer name(s) to compare.\n\n"
                "Usage:\n"
                "/compare <polymer> - Compare against 7-day high/low\n"
                "/compare <polymer> <polymer> - Compare two polymers\n"
                "/compare <polymer> <date> - Compare for specific date\n"
                "/compare <polymer> <polymer> <date> - Compare two for date\n\n"
                "Example: /compare J150\n"
                "Example: /compare J150 Y130\n"
                "Example: /compare J150 23.01.26"
            )
            return

        # Parse arguments
        args = context.args
        polymer1 = args[0]
        polymer2 = None
        target_date = None

        # Determine mode based on number of arguments
        if len(args) == 1:
            # Mode: /compare <polymer>
            # Compare polymer against its own 7-day high/low
            await self.compare_single_polymer(update, polymer1, None)

        elif len(args) == 2:
            # Could be: /compare <polymer> <polymer> OR /compare <polymer> <date>
            # Try to parse second arg as date
            try:
                date_patterns = [('%d.%m.%y', args[1]), ('%d.%m.%Y', args[1])]
                for pattern, date_input in date_patterns:
                    try:
                        target_date = datetime.strptime(date_input, pattern)
                        # Mode: /compare <polymer> <date>
                        await self.compare_single_polymer(update, polymer1, target_date)
                        return
                    except ValueError:
                        continue

                # If not a date, treat as second polymer
                # Mode: /compare <polymer> <polymer>
                polymer2 = args[1]
                await self.compare_two_polymers(update, polymer1, polymer2, None)

            except Exception as e:
                # Assume it's a second polymer name
                polymer2 = args[1]
                await self.compare_two_polymers(update, polymer1, polymer2, None)

        elif len(args) >= 3:
            # Mode: /compare <polymer> <polymer> <date>
            polymer2 = args[1]
            date_str = args[2]

            # Parse date
            try:
                date_patterns = [('%d.%m.%y', date_str), ('%d.%m.%Y', date_str)]
                for pattern, date_input in date_patterns:
                    try:
                        target_date = datetime.strptime(date_input, pattern)
                        break
                    except ValueError:
                        continue

                if not target_date:
                    await update.message.reply_text("Invalid date format. Use DD.MM.YY")
                    return

                await self.compare_two_polymers(update, polymer1, polymer2, target_date)

            except Exception as e:
                await update.message.reply_text(f"Error parsing date: {e}")

    async def compare_single_polymer(self, update: Update, polymer_name: str, target_date: datetime = None):
        """Compare single polymer against its high/low for 7 days or specific date"""

        if target_date:
            # Compare for specific date only
            price_data = self.db.get_price_on_date(polymer_name, target_date)
            price_stats = self.db.get_price_stats_for_date(polymer_name, target_date)

            if not price_data:
                await update.message.reply_text(
                    f"No data found for {polymer_name} on {target_date.strftime('%d.%m.%Y')}"
                )
                return

            message = f"📊 Comparison for {polymer_name}\n"
            message += f"Date: {target_date.strftime('%d.%m.%Y')}\n"
            message += "=" * 40 + "\n\n"

            if price_stats and price_stats['count'] > 1:
                price = price_data['price']
                lowest = price_stats['lowest']
                highest = price_stats['highest']

                message += f"💰 Your Price: {price:.2f}\n"
                message += f"📉 Day's Lowest: {lowest:.2f}\n"
                message += f"📈 Day's Highest: {highest:.2f}\n\n"

                if price == lowest:
                    message += "✅ This is the LOWEST price of the day!\n"
                elif price == highest:
                    message += "⚠️ This is the HIGHEST price of the day!\n"
                else:
                    pct_vs_low = ((price - lowest) / lowest) * 100
                    pct_vs_high = ((price - highest) / highest) * 100
                    message += f"📊 {pct_vs_low:+.1f}% vs lowest\n"
                    message += f"📊 {pct_vs_high:+.1f}% vs highest\n"
            else:
                message += f"💰 Price: {price_data['price']:.2f}\n"
                message += "\n(Only one price entry for this day)"

        else:
            # Compare for last 7 days
            price_range = self.db.get_price_range_for_polymer(polymer_name, 7)

            if not price_range:
                await update.message.reply_text(
                    f"No data found for {polymer_name} in the last 7 days"
                )
                return

            today = datetime.now()
            message = f"📊 7-Day Price Comparison for {polymer_name}\n"
            message += "=" * 40 + "\n\n"
            message += f"📉 7-Day Low: {price_range['lowest']:.2f}\n"
            message += f"📈 7-Day High: {price_range['highest']:.2f}\n"
            message += f"📊 Range: {price_range['highest'] - price_range['lowest']:.2f}\n\n"

            # Show each day's price vs the range
            for day in range(1, 8):
                target = today - timedelta(days=day)
                price_data = self.db.get_price_on_date(polymer_name, target)

                if price_data:
                    price = price_data['price']
                    pct_vs_low = ((price - price_range['lowest']) / price_range['lowest']) * 100
                    pct_vs_high = ((price - price_range['highest']) / price_range['highest']) * 100

                    indicator = ""
                    if price == price_range['lowest']:
                        indicator = " 📉 LOWEST"
                    elif price == price_range['highest']:
                        indicator = " 📈 HIGHEST"

                    message += f"Day {day} ({target.strftime('%d.%m')}): {price:.2f}{indicator}\n"
                    message += f"   {pct_vs_low:+.1f}% vs low | {pct_vs_high:+.1f}% vs high\n\n"
                else:
                    message += f"Day {day} ({target.strftime('%d.%m')}): No data\n\n"

        await update.message.reply_text(message, disable_web_page_preview=True)

    async def compare_two_polymers(self, update: Update, polymer1: str, polymer2: str, target_date: datetime = None):
        """Compare two polymers for 7 days or specific date"""

        if target_date:
            # Compare for specific date
            price1 = self.db.get_price_on_date(polymer1, target_date)
            price2 = self.db.get_price_on_date(polymer2, target_date)

            if not price1 or not price2:
                missing = []
                if not price1:
                    missing.append(polymer1)
                if not price2:
                    missing.append(polymer2)
                await update.message.reply_text(
                    f"No data found for {', '.join(missing)} on {target_date.strftime('%d.%m.%Y')}"
                )
                return

            message = f"⚖️ Comparison: {price1['polymer_name']} vs {price2['polymer_name']}\n"
            message += f"Date: {target_date.strftime('%d.%m.%Y')}\n"
            message += "=" * 40 + "\n\n"

            p1_price = price1['price']
            p2_price = price2['price']
            diff = p1_price - p2_price
            pct_diff = (diff / p2_price) * 100

            message += f"💰 {price1['polymer_name']}: {p1_price:.2f}\n"
            if price1.get('message_link'):
                message += f"   🔗 {price1['message_link']}\n"

            message += f"\n💰 {price2['polymer_name']}: {p2_price:.2f}\n"
            if price2.get('message_link'):
                message += f"   🔗 {price2['message_link']}\n"

            message += f"\n📊 Difference: {diff:+.2f} ({pct_diff:+.1f}%)\n"

            if diff > 0:
                message += f"✅ {price1['polymer_name']} is more expensive\n"
            elif diff < 0:
                message += f"✅ {price2['polymer_name']} is more expensive\n"
            else:
                message += "⚖️ Prices are equal\n"

        else:
            # Compare for last 7 days
            today = datetime.now()

            message = f"⚖️ 7-Day Comparison\n"
            message += f"{polymer1} vs {polymer2}\n"
            message += "=" * 40 + "\n\n"

            has_data = False
            for day in range(1, 8):
                target = today - timedelta(days=day)
                price1_data = self.db.get_price_on_date(polymer1, target)
                price2_data = self.db.get_price_on_date(polymer2, target)

                if price1_data and price2_data:
                    has_data = True
                    p1 = price1_data['price']
                    p2 = price2_data['price']
                    diff = p1 - p2
                    pct_diff = (diff / p2) * 100

                    winner = ""
                    if diff > 0:
                        winner = f" ({polymer1} higher)"
                    elif diff < 0:
                        winner = f" ({polymer2} higher)"

                    message += f"📅 Day {day} ({target.strftime('%d.%m')}):\n"
                    message += f"   {polymer1}: {p1:.2f}\n"
                    message += f"   {polymer2}: {p2:.2f}\n"
                    message += f"   Diff: {diff:+.2f} ({pct_diff:+.1f}%){winner}\n\n"
                elif price1_data or price2_data:
                    message += f"📅 Day {day} ({target.strftime('%d.%m')}): Partial data\n\n"
                else:
                    message += f"📅 Day {day} ({target.strftime('%d.%m')}): No data\n\n"

            if not has_data:
                await update.message.reply_text(
                    f"No comparable data found for {polymer1} and {polymer2} in the last 7 days"
                )
                return

        await update.message.reply_text(message, disable_web_page_preview=True)

    async def show_polymer_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
        """Show paginated menu of available polymers"""
        polymers = self.db.get_unique_polymers_with_latest_date()

        if not polymers:
            await update.message.reply_text(
                "No polymer data available yet. Please wait while the system collects data from the group."
            )
            return

        # Pagination settings
        items_per_page = 10
        total_pages = (len(polymers) - 1) // items_per_page + 1
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        page_polymers = polymers[start_idx:end_idx]

        # Build keyboard
        keyboard = []
        for polymer in page_polymers:
            button_text = f"{polymer['display_name']}"
            keyboard.append([InlineKeyboardButton(
                button_text,
                callback_data=f"polymer:{polymer['normalized_name']}"
            )])

        # Add navigation buttons
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"page:{page-1}"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"page:{page+1}"))

        if nav_buttons:
            keyboard.append(nav_buttons)

        reply_markup = InlineKeyboardMarkup(keyboard)

        message_text = f"Select a polymer (Page {page + 1}/{total_pages}):"

        if update.message:
            await update.message.reply_text(message_text, reply_markup=reply_markup)
        elif update.callback_query:
            await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)

    async def handle_polymer_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle polymer selection from inline keyboard"""
        query = update.callback_query
        await query.answer()

        callback_data = query.data

        if callback_data.startswith("page:"):
            # Handle pagination
            page = int(callback_data.split(":")[1])
            await self.show_polymer_menu(update, context, page=page)

        elif callback_data.startswith("polymer:"):
            # Handle polymer selection
            normalized_name = callback_data.split(":", 1)[1]
            await self.send_polymer_price_history(query, normalized_name)

    async def handle_text_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle direct text queries"""
        polymer_name = update.message.text.strip()

        # Try to find the polymer
        latest = self.db.get_latest_price(polymer_name)

        if not latest:
            await update.message.reply_text(
                f"Polymer '{polymer_name}' not found in the database.\n\n"
                "Use /list to see all available polymers."
            )
            return

        await self.send_polymer_price_history(update, polymer_name)

    async def send_polymer_price_history(self, update_or_query, polymer_name: str):
        """Send price history for a polymer (last 7 days)"""
        today = datetime.now()

        # Get latest price to display polymer name
        latest_price = self.db.get_latest_price(polymer_name)

        if not latest_price:
            message = f"❌ No data available for '{polymer_name}'"
            # Send the message
            if isinstance(update_or_query, Update):
                await update_or_query.message.reply_text(message)
            else:
                await update_or_query.message.reply_text(message)
            return

        # Build header
        message = f"📊 Price History for {latest_price['polymer_name']}\n"
        message += "=" * 40 + "\n\n"

        # Get prices for last 7 days
        has_data = False
        for day in range(1, 8):
            target_date = today - timedelta(days=day)
            price_data = self.db.get_price_on_date(polymer_name, target_date)

            if price_data:
                has_data = True
                price_str = f"{price_data['price']:.2f}" if price_data['price'] else price_data['status']
                message += f"📅 Day {day} ({target_date.strftime('%Y-%m-%d')}):\n"
                message += f"   💰 {price_str}\n"
                if price_data.get('message_link'):
                    message += f"   🔗 {price_data['message_link']}\n"
                message += "\n"
            else:
                message += f"📅 Day {day} ({target_date.strftime('%Y-%m-%d')}): No data\n\n"

        # Latest price section with statistics
        message += "=" * 40 + "\n"
        message += f"📈 Latest Day Statistics ({latest_price['date']}):\n\n"

        # Get price statistics for the latest date
        latest_date_obj = datetime.strptime(str(latest_price['date']), '%Y-%m-%d')
        price_stats = self.db.get_price_stats_for_date(polymer_name, latest_date_obj)

        if price_stats and price_stats['count'] > 1:
            # Multiple prices on this day, show statistics
            message += f"   📉 Lowest Price: {price_stats['lowest']:.2f}\n"
            if price_stats.get('lowest_link'):
                message += f"      🔗 {price_stats['lowest_link']}\n"

            message += f"\n   📊 Mean Price: {price_stats['mean']:.2f}\n"

            message += f"\n   📈 Highest Price: {price_stats['highest']:.2f}\n"
            if price_stats.get('highest_link'):
                message += f"      🔗 {price_stats['highest_link']}\n"

            message += f"\n   💼 Total Listings: {price_stats['count']}\n"

        else:
            # Only one price or no stats available
            latest_price_str = f"{latest_price['price']:.2f}" if latest_price['price'] else latest_price['status']
            message += f"   💰 Price: {latest_price_str}\n"
            if latest_price.get('message_link'):
                message += f"   🔗 {latest_price['message_link']}\n"

        # Warning if no historical data
        if not has_data:
            message += "\n⚠️ No historical data for the last 7 days. Showing latest data only."

        # Send the message
        if isinstance(update_or_query, Update):
            await update_or_query.message.reply_text(message, disable_web_page_preview=True)
        else:
            # It's a callback query
            await update_or_query.message.reply_text(message, disable_web_page_preview=True)

    async def run(self):
        """Run the bot"""
        print("Starting Polymer Price Bot...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        print("Bot is running. Press Ctrl+C to stop.")

        # Keep running
        try:
            await asyncio.Event().wait()
        finally:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()


async def run_bot():
    """Run the bot as a standalone process"""
    bot = PolymerPriceBot()
    bot.build_application()
    await bot.run()


if __name__ == "__main__":
    asyncio.run(run_bot())
