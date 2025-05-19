import logging
import redis
import os
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    PicklePersistence, # Simple file-based persistence for easy start
    RedisPersistence, # Use this for Redis-backed persistence
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
    """Creates the persistence object (Redis preferred for Railway)."""
    try:
        # Read Railway's standard Redis environment variables
        redis_host = os.getenv("REDISHOST")
        redis_port_str = os.getenv("REDISPORT")
        redis_password = os.getenv("REDISPASSWORD", None)
        redis_db = int(os.getenv("REDISDB", config.REDIS_DB)) # Use REDISDB from env or fallback

        if not redis_host or not redis_port_str:
            logger.warning("REDISHOST or REDISPORT not found, falling back to PicklePersistence.")
            return PicklePersistence(filepath="bot_persistence.pkl") # Fallback

        redis_port = int(redis_port_str)

        logger.info(f"Attempting to connect to Railway Redis at {redis_host}:{redis_port}")
        redis_instance = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            db=redis_db,
            decode_responses=True
        )
        redis_instance.ping()
        logger.info(f"Successfully connected to Railway Redis.")
        return RedisPersistence(redis_instance=redis_instance)

    except (redis.exceptions.ConnectionError, ValueError, TypeError) as e:
        logger.error(f"Could not connect to Railway Redis: {e}. Falling back to PicklePersistence.")
        return PicklePersistence(filepath="bot_persistence.pkl")
    except Exception as e:
        logger.error(f"Unexpected error setting up persistence: {e}. Falling back to PicklePersistence.")
        return PicklePersistence(filepath="bot_persistence.pkl")


def main():
    logger.info("Starting CVBuilder Bot...")

    if not config.TELEGRAM_BOT_TOKEN or not config.GEMINI_API_KEY:
        logger.critical("Missing TELEGRAM_BOT_TOKEN or GEMINI_API_KEY. Exiting.")
        return

    persistence = create_persistence()
    telegram_timeout_config = {
        'connect_timeout': 55.0,  # Seconds to establish a connection
        'read_timeout': 55.0,     # Seconds to wait for a read response
        'write_timeout': 55.0,    # Seconds to wait for a write operation
    }

    get_updates_timeout_config = {
        'connect_timeout': telegram_timeout_config['connect_timeout'] + 5.0,
        'read_timeout': telegram_timeout_config['read_timeout'] + 20.0, # Long polling needs longer read
        'write_timeout': telegram_timeout_config['write_timeout'] + 5.0,
    }


    application = (
        ApplicationBuilder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .persistence(persistence)
        .connect_timeout(telegram_timeout_config['connect_timeout'])
        .read_timeout(telegram_timeout_config['read_timeout'])
        .write_timeout(telegram_timeout_config['write_timeout'])
        .get_updates_connect_timeout(get_updates_timeout_config['connect_timeout'])
        .get_updates_read_timeout(get_updates_timeout_config['read_timeout'])
        .get_updates_write_timeout(get_updates_timeout_config['write_timeout'])
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