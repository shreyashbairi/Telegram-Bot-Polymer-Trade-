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
        """Handle /compare command with multiple modes, supporting quoted polymer names"""
        # Handle both message and callback query contexts
        if update.message:
            message_text = update.message.text
        elif update.callback_query:
            message_text = update.callback_query.message.text
        else:
            return

        if not message_text or len(message_text.strip()) <= 8:  # "/compare" is 8 chars
            reply_method = update.message.reply_text if update.message else update.callback_query.message.reply_text
            await reply_method(
                "Please provide polymer name(s) to compare.\n\n"
                "Usage:\n"
                "/compare <polymer> - Show high/low for 7 days\n"
                "/compare <polymer> <polymer> - Compare two polymers\n"
                "/compare <polymer> <date> - Show high/low for date\n"
                "/compare <polymer> <polymer> <date> - Compare two for date\n\n"
                "For names with spaces, use quotes:\n"
                "/compare '2119 Arya'\n"
                "/compare '2119 Arya' '2119 Iran'\n\n"
                "Example: /compare J150\n"
                "Example: /compare J150 Y130\n"
                "Example: /compare J150 23.01.26"
            )
            return

        # Parse arguments with quote support using the full message text
        import re
        try:
            # Extract everything after /compare command
            args_text = message_text.split(maxsplit=1)[1] if len(message_text.split(maxsplit=1)) > 1 else ""
            if not args_text:
                reply_method = update.message.reply_text if update.message else update.callback_query.message.reply_text
                await reply_method("Please provide polymer name(s) to compare.")
                return

            # Normalize ALL quote-like characters to straight single quotes
            # This handles Unicode quote variations
            quote_chars = [
                '"', '"',  # Smart double quotes U+201C, U+201D
                "'", "'",  # Smart single quotes U+2018, U+2019
                '‚', '„',  # Low quotes U+201A, U+201E
                '«', '»',  # Guillemets U+00AB, U+00BB
                '‹', '›',  # Single guillemets U+2039, U+203A
                '′', '″',  # Prime symbols U+2032, U+2033
                '`', '´',  # Grave and acute accents
            ]

            for char in quote_chars:
                args_text = args_text.replace(char, "'")

            # Also normalize straight double quotes to single quotes for consistency
            args_text = args_text.replace('"', "'")

            # Now parse with shlex using normalized quotes
            import shlex
            parsed_args = shlex.split(args_text)
        except ValueError as e:
            reply_method = update.message.reply_text if update.message else update.callback_query.message.reply_text
            await reply_method(
                f"Error parsing command: {e}\n\n"
                "Make sure to close all quotes properly."
            )
            return

        if not parsed_args:
            reply_method = update.message.reply_text if update.message else update.callback_query.message.reply_text
            await reply_method("Please provide polymer name(s) to compare.")
            return

        polymer1 = parsed_args[0]
        polymer2 = None
        target_date = None

        # Determine mode based on number of arguments
        if len(parsed_args) == 1:
            # Mode: /compare <polymer>
            await self.compare_single_polymer(update, polymer1, None)

        elif len(parsed_args) == 2:
            # Could be: /compare <polymer> <polymer> OR /compare <polymer> <date>
            # Try to parse second arg as date
            date_patterns = [('%d.%m.%y', parsed_args[1]), ('%d.%m.%Y', parsed_args[1])]
            is_date = False

            for pattern, date_input in date_patterns:
                try:
                    target_date = datetime.strptime(date_input, pattern)
                    is_date = True
                    break
                except ValueError:
                    continue

            if is_date:
                # Mode: /compare <polymer> <date>
                await self.compare_single_polymer(update, polymer1, target_date)
            else:
                # Mode: /compare <polymer> <polymer>
                polymer2 = parsed_args[1]
                await self.compare_two_polymers(update, polymer1, polymer2, None)

        elif len(parsed_args) >= 3:
            # Mode: /compare <polymer> <polymer> <date>
            polymer2 = parsed_args[1]
            date_str = parsed_args[2]

            # Parse date
            date_patterns = [('%d.%m.%y', date_str), ('%d.%m.%Y', date_str)]
            for pattern, date_input in date_patterns:
                try:
                    target_date = datetime.strptime(date_input, pattern)
                    break
                except ValueError:
                    continue

            if not target_date:
                # More helpful error message
                reply_method = update.message.reply_text if update.message else update.callback_query.message.reply_text
                await reply_method(
                    f"Invalid date format: '{date_str}'. Use DD.MM.YY\n\n"
                    f"Parsed {len(parsed_args)} arguments: {parsed_args}\n\n"
                    "If you're trying to compare polymers with spaces in their names, "
                    "make sure to use quotes:\n"
                    "/compare '2119 Iran' '2119 Arya'\n\n"
                    "Note: Any type of quotes work - they will be normalized automatically"
                )
                return

            await self.compare_two_polymers(update, polymer1, polymer2, target_date)

    async def compare_single_polymer(self, update: Update, polymer_name: str, target_date: datetime = None):
        """Show highest and lowest prices for a polymer"""
        # Get reply method for both message and callback query contexts
        reply_method = update.message.reply_text if update.message else update.callback_query.message.reply_text

        if target_date:
            # Show high/low for specific date
            price_stats = self.db.get_price_stats_for_date(polymer_name, target_date)

            if not price_stats:
                await reply_method(
                    f"No data found for {polymer_name} on {target_date.strftime('%d.%m.%Y')}"
                )
                return

            message = f"📊 Price Analysis for {polymer_name}\n"
            message += f"Date: {target_date.strftime('%d.%m.%Y')}\n"
            message += "=" * 40 + "\n\n"

            message += f"   {polymer_name}:\n"
            if price_stats['count'] > 1:
                message += f"\tHighest: {price_stats['highest']:.2f}"
                if price_stats.get('highest_link'):
                    message += f" ({price_stats['highest_link']})"
                message += "\n"

                message += f"\tLowest: {price_stats['lowest']:.2f}"
                if price_stats.get('lowest_link'):
                    message += f" ({price_stats['lowest_link']})"
                message += "\n"

                message += f"\tDiff: {price_stats['diff']:.2f}\n"
                message += f"\tMean Price: {price_stats['mean']:.2f}\n"

                if price_stats.get('latest_price'):
                    message += f"\tLatest Price: {price_stats['latest_price']:.2f}"
                    if price_stats.get('latest_link'):
                        message += f" ({price_stats['latest_link']})"
                    message += "\n"
            else:
                message += f"\tPrice: {price_stats['lowest']:.2f}"
                if price_stats.get('lowest_link'):
                    message += f" ({price_stats['lowest_link']})"
                message += "\n"
                message += "\n\t(Only one price entry for this day)"

        else:
            # Show high/low for last 7 days
            today = datetime.now()
            message = f"📊 7-Day Price Analysis:\n{polymer_name}\n"
            message += "=" * 40 + "\n\n"

            has_data = False
            for day in range(1, 8):
                target = today - timedelta(days=day)
                price_stats = self.db.get_price_stats_for_date(polymer_name, target)

                if price_stats:
                    has_data = True
                    message += f"📅 Day {day} ({target.strftime('%d.%m')}):\n"
                    message += f"   {polymer_name}:\n"

                    if price_stats['count'] > 1:
                        message += f"\tHighest: {price_stats['highest']:.2f}"
                        if price_stats.get('highest_link'):
                            message += f" ({price_stats['highest_link']})"
                        message += "\n"

                        message += f"\tLowest: {price_stats['lowest']:.2f}"
                        if price_stats.get('lowest_link'):
                            message += f" ({price_stats['lowest_link']})"
                        message += "\n"

                        message += f"\tDiff: {price_stats['diff']:.2f}\n"
                        message += f"\tMean Price: {price_stats['mean']:.2f}\n"

                        if price_stats.get('latest_price'):
                            message += f"\tLatest Price of Day {day}: {price_stats['latest_price']:.2f}"
                            if price_stats.get('latest_link'):
                                message += f" ({price_stats['latest_link']})"
                            message += "\n"
                    else:
                        message += f"\tPrice: {price_stats['lowest']:.2f}"
                        if price_stats.get('lowest_link'):
                            message += f" ({price_stats['lowest_link']})"
                        message += "\n"

                    message += "\n"
                else:
                    message += f"📅 Day {day} ({target.strftime('%d.%m')}): No data\n\n"

            if not has_data:
                await reply_method(
                    f"No data found for {polymer_name} in the last 7 days"
                )
                return

        await reply_method(message, disable_web_page_preview=True)

    async def compare_two_polymers(self, update: Update, polymer1: str, polymer2: str, target_date: datetime = None):
        """Compare two polymers showing high/low for each"""
        # Get reply method for both message and callback query contexts
        reply_method = update.message.reply_text if update.message else update.callback_query.message.reply_text

        if target_date:
            # Compare for specific date
            stats1 = self.db.get_price_stats_for_date(polymer1, target_date)
            stats2 = self.db.get_price_stats_for_date(polymer2, target_date)

            if not stats1 or not stats2:
                missing = []
                if not stats1:
                    missing.append(polymer1)
                if not stats2:
                    missing.append(polymer2)
                await reply_method(
                    f"No data found for {', '.join(missing)} on {target_date.strftime('%d.%m.%Y')}"
                )
                return

            message = f"⚖️ Comparison: {polymer1} vs {polymer2}\n"
            message += f"Date: {target_date.strftime('%d.%m.%Y')}\n"
            message += "=" * 40 + "\n\n"

            # Polymer 1
            message += f"   {polymer1}:\n"
            if stats1['count'] > 1:
                message += f"\tHighest: {stats1['highest']:.2f}"
                if stats1.get('highest_link'):
                    message += f" ({stats1['highest_link']})"
                message += "\n"

                message += f"\tLowest: {stats1['lowest']:.2f}"
                if stats1.get('lowest_link'):
                    message += f" ({stats1['lowest_link']})"
                message += "\n"

                message += f"\tDiff: {stats1['diff']:.2f}\n"
                message += f"\tMean Price: {stats1['mean']:.2f}\n"

                if stats1.get('latest_price'):
                    message += f"\tLatest Price: {stats1['latest_price']:.2f}"
                    if stats1.get('latest_link'):
                        message += f" ({stats1['latest_link']})"
                    message += "\n"
            else:
                message += f"\tPrice: {stats1['lowest']:.2f}"
                if stats1.get('lowest_link'):
                    message += f" ({stats1['lowest_link']})"
                message += "\n"

            message += "\n"

            # Polymer 2
            message += f"   {polymer2}:\n"
            if stats2['count'] > 1:
                message += f"\tHighest: {stats2['highest']:.2f}"
                if stats2.get('highest_link'):
                    message += f" ({stats2['highest_link']})"
                message += "\n"

                message += f"\tLowest: {stats2['lowest']:.2f}"
                if stats2.get('lowest_link'):
                    message += f" ({stats2['lowest_link']})"
                message += "\n"

                message += f"\tDiff: {stats2['diff']:.2f}\n"
                message += f"\tMean Price: {stats2['mean']:.2f}\n"

                if stats2.get('latest_price'):
                    message += f"\tLatest Price: {stats2['latest_price']:.2f}"
                    if stats2.get('latest_link'):
                        message += f" ({stats2['latest_link']})"
                    message += "\n"
            else:
                message += f"\tPrice: {stats2['lowest']:.2f}"
                if stats2.get('lowest_link'):
                    message += f" ({stats2['lowest_link']})"
                message += "\n"

        else:
            # Compare for last 7 days
            today = datetime.now()

            message = f"⚖️ 7-Day Comparison:\n"
            message += f"{polymer1} vs {polymer2}\n"
            message += "=" * 40 + "\n\n"

            has_data = False
            for day in range(1, 8):
                target = today - timedelta(days=day)
                stats1 = self.db.get_price_stats_for_date(polymer1, target)
                stats2 = self.db.get_price_stats_for_date(polymer2, target)

                if stats1 and stats2:
                    has_data = True
                    message += f"📅 Day {day} ({target.strftime('%d.%m')}):\n"

                    # Polymer 1
                    message += f"   {polymer1}:\n"
                    if stats1['count'] > 1:
                        message += f"\tHighest: {stats1['highest']:.2f}"
                        if stats1.get('highest_link'):
                            message += f" ({stats1['highest_link']})"
                        message += "\n"

                        message += f"\tLowest: {stats1['lowest']:.2f}"
                        if stats1.get('lowest_link'):
                            message += f" ({stats1['lowest_link']})"
                        message += "\n"

                        message += f"\tDiff: {stats1['diff']:.2f}\n"
                        message += f"\tMean Price: {stats1['mean']:.2f}\n"

                        if stats1.get('latest_price'):
                            message += f"\tLatest Price of Day {day}: {stats1['latest_price']:.2f}"
                            if stats1.get('latest_link'):
                                message += f" ({stats1['latest_link']})"
                            message += "\n"
                    else:
                        message += f"\tPrice: {stats1['lowest']:.2f}"
                        if stats1.get('lowest_link'):
                            message += f" ({stats1['lowest_link']})"
                        message += "\n"

                    message += "\n"

                    # Polymer 2
                    message += f"   {polymer2}:\n"
                    if stats2['count'] > 1:
                        message += f"\tHighest: {stats2['highest']:.2f}"
                        if stats2.get('highest_link'):
                            message += f" ({stats2['highest_link']})"
                        message += "\n"

                        message += f"\tLowest: {stats2['lowest']:.2f}"
                        if stats2.get('lowest_link'):
                            message += f" ({stats2['lowest_link']})"
                        message += "\n"

                        message += f"\tDiff: {stats2['diff']:.2f}\n"
                        message += f"\tMean Price: {stats2['mean']:.2f}\n"

                        if stats2.get('latest_price'):
                            message += f"\tLatest Price of Day {day}: {stats2['latest_price']:.2f}"
                            if stats2.get('latest_link'):
                                message += f" ({stats2['latest_link']})"
                            message += "\n"
                    else:
                        message += f"\tPrice: {stats2['lowest']:.2f}"
                        if stats2.get('lowest_link'):
                            message += f" ({stats2['lowest_link']})"
                        message += "\n"

                    message += "\n"

                elif stats1 or stats2:
                    message += f"📅 Day {day} ({target.strftime('%d.%m')}): Partial data\n\n"
                else:
                    message += f"📅 Day {day} ({target.strftime('%d.%m')}): No data\n\n"

            if not has_data:
                await reply_method(
                    f"No comparable data found for {polymer1} and {polymer2} in the last 7 days"
                )
                return

        await reply_method(message, disable_web_page_preview=True)

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
            try:
                await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)
            except Exception as e:
                # Handle case where message content hasn't changed
                if "Message is not modified" not in str(e):
                    raise

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
