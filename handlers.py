import logging
from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

import utils
import flows
import config

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends the welcome message and main menu."""
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) started the bot.")
    # Clear any previous state just in case
    await utils.cleanup_user_data(context)
    context.user_data['state'] = config.STATE_AWAITING_CHOICE

    await update.message.reply_html(
        f"👋 Hello {user.mention_html()}!\n\n"
        "I'm <b>CVBuilder</b>, your assistant for creating professional, minimalist CVs.\n\n"
        "How would you like to start?",
        reply_markup=utils.create_main_menu_keyboard(),
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays help information."""
    await update.message.reply_text(
        "Use /start to begin creating a CV.\n"
        "You can either:\n"
        "1. Create a CV from scratch by answering questions.\n"
        "2. Upload an existing CV (PDF/DOCX) for me to parse and reformat.\n\n"
        "I'll guide you through the steps! Data is only stored temporarily during creation."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles regular text messages based on the current state."""
    user_state = context.user_data.get('state')
    user_id = update.effective_user.id
    text = update.message.text

    logger.debug(f"Received message from {user_id} in state {user_state}: {text}")

    if user_state == config.STATE_SCRATCH_AWAIT_DATA:
        await flows.handle_scratch_input(update, context)
    elif user_state == config.STATE_UPLOAD_AWAIT_FILE:
         await update.message.reply_text("Please upload a file using the attachment button, or choose an option using /start.")
    elif user_state in [config.STATE_AWAITING_CHOICE, config.STATE_REVIEWING_DATA, config.STATE_SELECTING_TEMPLATE]:
         # Usually expect button presses in these states
         await update.message.reply_text("Please use the buttons provided, or /start to begin again.")
    else:
        # Default handler or unexpected state
        logger.warning(f"Unhandled message from {user_id} in state {user_state}")
        await update.message.reply_text("I'm not sure what you mean. Use /start to create a CV.")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles uploaded documents."""
    user_state = context.user_data.get('state')
    user_id = update.effective_user.id
    logger.info(f"Received document from {user_id} in state {user_state}")

    if user_state == config.STATE_UPLOAD_AWAIT_FILE:
        await flows.handle_cv_upload(update, context)
    else:
        await update.message.reply_text("Please use /start and choose the 'Upload Existing CV' option before uploading a file.")


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles button presses (Callback Queries)."""
    query = update.callback_query
    await query.answer() # Answer callback query quickly to prevent timeout indication on client
    user_id = update.effective_user.id
    callback_data = query.data
    user_state = context.user_data.get('state')

    logger.info(f"Received callback query from {user_id} in state {user_state}: {callback_data}")

    # --- Main Menu Choices ---
    if callback_data == "create_scratch":
        if user_state == config.STATE_AWAITING_CHOICE:
             await query.edit_message_text("Okay, let's create your CV from scratch!")
             await flows.start_scratch_flow(update, context)
        else:
             await query.message.reply_text("Please finish your current process or use /start again.")
    elif callback_data == "create_upload":
        if user_state == config.STATE_AWAITING_CHOICE:
             await query.edit_message_text("Got it. Prepare your PDF or DOCX file.")
             await flows.request_upload(update, context)
        else:
             await query.message.reply_text("Please finish your current process or use /start again.")

    # --- Review Confirmation ---
    elif callback_data.startswith("review_"):
        if user_state == config.STATE_REVIEWING_DATA:
             confirmed = callback_data == "review_yes"
             await flows.handle_review_confirmation(update, context, confirmed)
        else:
             logger.warning("Received review callback in unexpected state.")
             # Don't edit message if state is wrong, could be confusing
             # await query.message.reply_text("Something went wrong with the state. Please use /start.")

    # --- Template Selection ---
    elif callback_data.startswith("select_template_"):
         if user_state == config.STATE_SELECTING_TEMPLATE:
              template_key = callback_data.replace("select_template_", "")
              await flows.handle_template_selection(update, context, template_key)
         else:
              logger.warning("Received template selection callback in unexpected state.")
              # await query.message.reply_text("Something went wrong with the state. Please use /start.")

    # --- Catch other unexpected callbacks ---
    else:
        logger.warning(f"Unhandled callback query data: {callback_data}")
        try:
             # Try to inform user without editing if state is weird
             await query.message.reply_text("Sorry, I didn't understand that button press in this context.")
        except Exception:
             # If message edit fails (e.g., message too old)
             pass


# Define handlers
start_handler = CommandHandler("start", start)
help_handler = CommandHandler("help", help_command)
message_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
document_handler = MessageHandler(filters.Document.ALL, handle_document)
callback_query_handler = CallbackQueryHandler(handle_callback_query)