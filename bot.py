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

        # Add handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("list", self.list_polymers_command))
        self.app.add_handler(CallbackQueryHandler(self.handle_polymer_selection))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_query))

        return self.app

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_message = """
Welcome to the Polymer Price Bot! 🏭

I can help you check historical prices for various polymers.

Commands:
/list - Show list of available polymers
/help - Show this help message

You can also just type the polymer name (e.g., "J150", "Y130") to get its price history.
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
2. Click on a polymer name or type it directly
3. Get price history: yesterday, 3 days ago, 1 week ago

Examples:
- Type "J150" to get J150 price history
- Type "Y130" to get Y130 price history
- Use /list to browse all available polymers

The bot shows:
✅ Price yesterday
✅ Price 3 days ago
✅ Price 1 week ago
✅ Latest available price if historical data is missing
"""
        await update.message.reply_text(help_message)

    async def list_polymers_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /list command"""
        await self.show_polymer_menu(update, context)

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
        """Send price history for a polymer"""
        today = datetime.now()

        # Get prices for specific dates
        yesterday = today - timedelta(days=1)
        three_days_ago = today - timedelta(days=3)
        one_week_ago = today - timedelta(days=7)

        price_yesterday = self.db.get_price_on_date(polymer_name, yesterday)
        price_3days = self.db.get_price_on_date(polymer_name, three_days_ago)
        price_1week = self.db.get_price_on_date(polymer_name, one_week_ago)

        # Get latest price as fallback
        latest_price = self.db.get_latest_price(polymer_name)

        # Build response message
        if not latest_price:
            message = f"❌ No data available for '{polymer_name}'"
        else:
            message = f"📊 Price History for {latest_price['polymer_name']}\n"
            message += "=" * 40 + "\n\n"

            # Yesterday's price
            if price_yesterday:
                price_str = f"{price_yesterday['price']:.2f}" if price_yesterday['price'] else price_yesterday['status']
                message += f"📅 Yesterday ({yesterday.strftime('%Y-%m-%d')}):\n"
                message += f"   💰 {price_str}\n\n"
            else:
                message += f"📅 Yesterday: No data\n\n"

            # 3 days ago
            if price_3days:
                price_str = f"{price_3days['price']:.2f}" if price_3days['price'] else price_3days['status']
                message += f"📅 3 days ago ({three_days_ago.strftime('%Y-%m-%d')}):\n"
                message += f"   💰 {price_str}\n\n"
            else:
                message += f"📅 3 days ago: No data\n\n"

            # 1 week ago
            if price_1week:
                price_str = f"{price_1week['price']:.2f}" if price_1week['price'] else price_1week['status']
                message += f"📅 1 week ago ({one_week_ago.strftime('%Y-%m-%d')}):\n"
                message += f"   💰 {price_str}\n\n"
            else:
                message += f"📅 1 week ago: No data\n\n"

            # Latest price
            message += "=" * 40 + "\n"
            latest_price_str = f"{latest_price['price']:.2f}" if latest_price['price'] else latest_price['status']
            message += f"🔄 Latest Price ({latest_price['date']}):\n"
            message += f"   💰 {latest_price_str}\n"

            # Check if no historical data but have latest
            if not price_yesterday and not price_3days and not price_1week:
                message += "\n⚠️ Historical data not available. Showing latest data only."

        # Send the message
        if isinstance(update_or_query, Update):
            await update_or_query.message.reply_text(message)
        else:
            # It's a callback query
            await update_or_query.message.reply_text(message)

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
