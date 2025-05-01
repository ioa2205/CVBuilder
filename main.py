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

warnings.filterwarnings("ignore", category=PTBUserWarning, message="State .* isn't part of any ConversationHandler")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO 
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def create_persistence() -> BasePersistence:
    """Creates the persistence object (Redis or Pickle)."""
    try:
        # Requires a running Redis server configured in .env
        redis_instance = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=config.REDIS_DB, decode_responses=True)
        redis_instance.ping() # Test connection
        logger.info(f"Successfully connected to Redis at {config.REDIS_HOST}:{config.REDIS_PORT}")

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

    persistence = create_persistence()

    application = (
        ApplicationBuilder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .persistence(persistence)
        .read_timeout(100)  
        .write_timeout(100) 
        .build()
    )

    application.add_handler(handlers.start_handler)
    application.add_handler(handlers.help_handler)
    application.add_handler(handlers.message_handler)
    application.add_handler(handlers.document_handler)
    application.add_handler(handlers.callback_query_handler)


    logger.info("Bot application built. Starting polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    logger.info("Bot stopped.")


if __name__ == "__main__":
    main()