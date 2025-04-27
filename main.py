import logging
import redis
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    PicklePersistence, # Simple file-based persistence for easy start
    # RedisPersistence, # Use this for Redis-backed persistence
    BasePersistence,
)
from telegram.warnings import PTBUserWarning
import warnings
from telegram import Update

import config
import handlers

# Suppress warning about not using ConversationHandler for states (we handle manually)
warnings.filterwarnings("ignore", category=PTBUserWarning, message="State .* isn't part of any ConversationHandler")

# --- Logging Setup ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO # Change to logging.DEBUG for more verbose output
)
# Set higher logging level for httpx to avoid noisy INFO messages
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def create_persistence() -> BasePersistence:
    """Creates the persistence object (Redis or Pickle)."""
    try:
        # --- Redis Persistence (Recommended for production/statefulness) ---
        # Requires a running Redis server configured in .env
        redis_instance = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=config.REDIS_DB, decode_responses=True)
        redis_instance.ping() # Test connection
        logger.info(f"Successfully connected to Redis at {config.REDIS_HOST}:{config.REDIS_PORT}")
        # Note: RedisPersistence requires python-telegram-bot[persistence] extra or installing `redis` separately
        # If using PTB's built-in RedisPersistence (check PTB version docs for exact class name/usage):
        # from telegram.ext import RedisPersistence # Might be different import path
        # return RedisPersistence(redis_instance=redis_instance)

        # --- OR Simple Pickle Persistence (Easier for testing, not recommended for prod) ---
        # Stores data in a file named 'bot_persistence.pkl' (default)
        logger.warning("Using PicklePersistence. State will be lost if the bot restarts without the file. Use RedisPersistence for production.")
        return PicklePersistence(filepath="bot_persistence.pkl")

    except redis.exceptions.ConnectionError as e:
         logger.error(f"Could not connect to Redis at {config.REDIS_HOST}:{config.REDIS_PORT}. Error: {e}")
         logger.warning("Falling back to PicklePersistence. State will be lost on restart without the file.")
         return PicklePersistence(filepath="bot_persistence.pkl")
    except Exception as e:
         logger.error(f"Error setting up persistence: {e}", exc_info=True)
         logger.warning("Falling back to PicklePersistence.")
         return PicklePersistence(filepath="bot_persistence.pkl")

def main():
    """Starts the CVBuilder bot."""
    logger.info("Starting CVBuilder Bot...")

    if not config.TELEGRAM_BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN not found in environment variables. Exiting.")
        return
    if not config.GEMINI_API_KEY:
        logger.critical("GEMINI_API_KEY not found in environment variables. Exiting.")
        return

    # Choose and create persistence backend
    persistence = create_persistence()

    # Build the application
    application = (
        ApplicationBuilder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .persistence(persistence)
        .read_timeout(30)  # Increase if needed for long operations
        .write_timeout(30) # Increase if needed for sending large files
        .build()
    )

    # Register handlers from handlers.py
    application.add_handler(handlers.start_handler)
    application.add_handler(handlers.help_handler)
    application.add_handler(handlers.message_handler)
    application.add_handler(handlers.document_handler)
    application.add_handler(handlers.callback_query_handler)

    # Add error handler (optional but recommended)
    # async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    #    logger.error("Exception while handling an update:", exc_info=context.error)
    # application.add_error_handler(error_handler)

    logger.info("Bot application built. Starting polling...")
    # Start the Bot (using polling for simplicity, use run_webhook for production)
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    logger.info("Bot stopped.")


if __name__ == "__main__":
    main()