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
3. Click on a polymer name or type it directly
4. Get price history for the last 7 days

Commands:
/start - Start the bot and show menu
/list - Browse all polymers
/search <name> - Search for polymers (e.g., /search J150)
/help - Show this help message

Examples:
- Type "J150" to get J150 price history
- Use /search shurtan to find all Shurtan polymers
- Use /list to browse all available polymers

The bot shows:
✅ Daily prices for the last 7 days
✅ Message links for each price entry
✅ Latest available price if historical data is missing
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
