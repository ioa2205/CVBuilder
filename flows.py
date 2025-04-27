import logging
from telegram import Update, InputFile
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
import io
from typing import Optional
import config
import utils
import gemini_service
import pdf_service
from schemas import CVData, ContactInfo, WorkExperienceItem, EducationItem, SkillItem # Import sub-models too


logger = logging.getLogger(__name__)

# --- Scratch Flow ---

async def start_scratch_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiates the CV creation from scratch."""
    await utils.cleanup_user_data(context) # Clear previous state first
    context.user_data['state'] = config.STATE_SCRATCH_START
    context.user_data['cv_data'] = {} # Initialize empty CV data dict
    context.user_data['current_section_index'] = 0
    context.user_data['scratch_data_buffer'] = {} # Temp buffer for complex sections like work/edu

    await ask_next_scratch_question(update, context)

async def ask_next_scratch_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asks the user for the next piece of information in the scratch flow."""
    idx = context.user_data.get('current_section_index', 0)

    if idx >= len(config.CV_SECTIONS):
        # All sections done, move to review
        await transition_to_review(update, context)
        return

    section_key = config.CV_SECTIONS[idx]
    section_readable = section_key.replace('_', ' ').replace('.', ' -> ').title()

    # Basic prompt - needs significant refinement for good UX & multi-entry sections
    prompt_text = f"📝 Please enter your *{section_readable}*."

    if section_key == "work_experience":
         prompt_text += "\n\n*Format for each job:*\n`Title` at `Company` (`Start Date` - `End Date`)\n- Responsibility 1\n- Responsibility 2\n\nType 'DONE' when finished adding jobs."
         context.user_data['scratch_data_buffer']['work_experience'] = [] # Initialize list
    elif section_key == "education":
         prompt_text += "\n\n*Format for each degree:*\n`Degree` from `Institution` (`Graduation Date`)\nOptional details on next line.\n\nType 'DONE' when finished adding degrees."
         context.user_data['scratch_data_buffer']['education'] = [] # Initialize list
    elif section_key == "skills":
         prompt_text += "\n\nEnter skills separated by commas (e.g., Python, Java, SQL). We'll categorize later if possible."
         # Simple comma separated for V1

    context.user_data['state'] = config.STATE_SCRATCH_AWAIT_DATA
    await update.effective_message.reply_text(prompt_text, parse_mode=ParseMode.MARKDOWN)


async def handle_scratch_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes user input during the scratch flow."""
    user_input = update.message.text
    idx = context.user_data.get('current_section_index', 0)

    if idx >= len(config.CV_SECTIONS):
        # Should be in review or later state, ignore stray messages
        logger.warning(f"Received unexpected text message in state: {context.user_data.get('state')}")
        return

    section_key = config.CV_SECTIONS[idx]
    cv_data = context.user_data.get('cv_data', {})
    buffer = context.user_data.get('scratch_data_buffer', {})

    # --- Handling complex sections (Work/Edu/Skills) - VERY SIMPLIFIED ---
    # This needs much more robust parsing logic for real-world use
    if section_key == "work_experience":
        if user_input.strip().upper() == 'DONE':
            cv_data['work_experience'] = buffer.get('work_experience', [])
            context.user_data['current_section_index'] += 1
            await ask_next_scratch_question(update, context)
        else:
            # Rudimentary parsing - assumes specific format user was told
            lines = user_input.split('\n')
            job_info = {}
            try:
                # Example: "Software Engineer at Tech Corp (2020-01 - Present)"
                first_line_parts = lines[0].split(' at ')
                job_info['job_title'] = first_line_parts[0].strip()
                company_date_parts = first_line_parts[1].split('(')
                job_info['company'] = company_date_parts[0].strip()
                date_parts = company_date_parts[1].replace(')', '').split(' - ')
                job_info['start_date'] = date_parts[0].strip()
                job_info['end_date'] = date_parts[1].strip()
                job_info['description'] = [line.strip().lstrip('- ') for line in lines[1:] if line.strip()]
                buffer.setdefault('work_experience', []).append(job_info)
                await update.effective_message.reply_text("Job added. Add another or type 'DONE'.")
            except Exception as e:
                logger.error(f"Failed to parse work experience input: {e}\nInput: {user_input}")
                await update.effective_message.reply_text("Sorry, I couldn't understand that format. Please try again or type 'DONE'.")
        return # Don't proceed to next question automatically for multi-entry

    elif section_key == "education":
         if user_input.strip().upper() == 'DONE':
            cv_data['education'] = buffer.get('education', [])
            context.user_data['current_section_index'] += 1
            await ask_next_scratch_question(update, context)
         else:
            # Rudimentary parsing
            lines = user_input.split('\n')
            edu_info = {}
            try:
                 # Example: "B.S. Computer Science from State University (May 2020)"
                 first_line_parts = lines[0].split(' from ')
                 edu_info['degree'] = first_line_parts[0].strip()
                 inst_date_parts = first_line_parts[1].split('(')
                 edu_info['institution'] = inst_date_parts[0].strip()
                 edu_info['graduation_date'] = inst_date_parts[1].replace(')', '').strip()
                 edu_info['details'] = "\n".join(lines[1:]).strip() if len(lines) > 1 else None
                 buffer.setdefault('education', []).append(edu_info)
                 await update.effective_message.reply_text("Education entry added. Add another or type 'DONE'.")
            except Exception as e:
                logger.error(f"Failed to parse education input: {e}\nInput: {user_input}")
                await update.effective_message.reply_text("Sorry, I couldn't understand that format. Please try again or type 'DONE'.")
         return # Don't proceed automatically

    elif section_key == "skills":
         # Simple comma-separated list for V1
         skill_list = [s.strip() for s in user_input.split(',') if s.strip()]
         # Store as a simple list or basic SkillItem structure
         cv_data['skills'] = [{"category": "General", "skills_list": skill_list}] # Example categorization
         context.user_data['current_section_index'] += 1

    # --- Handling simple sections (Contact Info, Summary) ---
    else:
        # Use dot notation to update nested Pydantic models later
        # Store flat for now, structure before validation/PDF gen
        # Example: section_key = "contact_info.full_name"
        keys = section_key.split('.')
        temp_data = cv_data
        for i, key in enumerate(keys):
            if i == len(keys) - 1:
                temp_data[key] = user_input.strip()
            else:
                temp_data = temp_data.setdefault(key, {})

        context.user_data['current_section_index'] += 1


    # Check if need to structure before next question or review
    if context.user_data['current_section_index'] < len(config.CV_SECTIONS):
        await ask_next_scratch_question(update, context)
    else:
         await transition_to_review(update, context)


# --- Upload Flow ---

async def request_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asks the user to upload their CV file."""
    await utils.cleanup_user_data(context)
    context.user_data['state'] = config.STATE_UPLOAD_AWAIT_FILE
    await update.effective_message.reply_text(
        "📄 Please upload your CV as a PDF or DOCX file."
    )

async def handle_cv_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the uploaded CV file, extracts text, and calls Gemini."""
    if not update.message.document:
        await update.effective_message.reply_text("Hmm, I didn't receive a document. Please try uploading again.")
        return

    doc = update.message.document
    if doc.mime_type not in ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
        await update.effective_message.reply_text("Sorry, I can only process PDF or DOCX files. Please upload a valid file.")
        return

    await update.effective_message.reply_text("⏳ Got it! Processing your CV... (This might take a moment)")
    context.user_data['state'] = config.STATE_UPLOAD_PARSING

    try:
        file = await context.bot.get_file(doc.file_id)
        file_bytes = await file.download_as_bytearray()
        file_content = bytes(file_bytes) # Convert bytearray to bytes

        text = ""
        if doc.mime_type == "application/pdf":
            text = utils.extract_text_from_pdf(file_content)
        elif doc.mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            text = utils.extract_text_from_docx(file_content)

        if not text or text.isspace():
            await update.effective_message.reply_text("😥 I couldn't extract any text from your document. Please check the file or try a different format.")
            await utils.cleanup_user_data(context)
            return

        # Call Gemini service
        parsed_data: Optional[CVData] = await gemini_service.parse_cv_text_with_gemini(text)

        if parsed_data:
            # Store the validated Pydantic model's dictionary representation
            context.user_data['cv_data'] = parsed_data.model_dump(mode='json', exclude_unset=True) # Store as dict
            await transition_to_review(update, context)
        else:
            await update.effective_message.reply_text("😥 Sorry, I had trouble understanding the structure of your CV. You could try the 'Create from Scratch' option instead.")
            await utils.cleanup_user_data(context)

    except Exception as e:
        logger.error(f"Error processing uploaded file: {e}", exc_info=True)
        await update.effective_message.reply_text("An error occurred while processing your file. Please try again later.")
        await utils.cleanup_user_data(context)


# --- Common Flow Steps ---

def structure_scratch_data(raw_data: dict) -> dict:
     """Converts the flat data collected during scratch flow into nested structure."""
     # This is where you'd map {"contact_info.full_name": "..."} to {"contact_info": {"full_name": "..."}}
     # And ensure work_experience/education/skills are lists of dicts/objects
     # For simplicity in this example, assume the structure is already somewhat nested,
     # but validation will happen later.
     # A more robust implementation would use the keys like "contact_info.full_name"
     # to build the nested dict properly.
     # Let's assume handle_scratch_input already created a basic nested structure.
     structured = {}
     if 'contact_info' in raw_data:
          structured['contact_info'] = raw_data['contact_info']
     if 'summary' in raw_data:
           structured['summary'] = raw_data['summary']
     if 'work_experience' in raw_data and isinstance(raw_data['work_experience'], list):
           structured['work_experience'] = raw_data['work_experience']
     if 'education' in raw_data and isinstance(raw_data['education'], list):
           structured['education'] = raw_data['education']
     if 'skills' in raw_data and isinstance(raw_data['skills'], list):
          structured['skills'] = raw_data['skills'] # Assumes simple structure was saved

     # logger.debug(f"Structured scratch data: {structured}")
     return structured

async def transition_to_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Formats data and asks the user to review."""
    if context.user_data.get('state') == config.STATE_SCRATCH_AWAIT_DATA:
         # If coming from scratch, structure the data first
         raw_cv_data = context.user_data.get('cv_data', {})
         cv_data_dict = structure_scratch_data(raw_cv_data)
         context.user_data['cv_data'] = cv_data_dict # Store structured dict
    else:
         # If coming from upload, data should already be a dict from Pydantic model
         cv_data_dict = context.user_data.get('cv_data', {})

    if not cv_data_dict:
        logger.error("No CV data found when transitioning to review.")
        await update.effective_message.reply_text("Something went wrong, no data to review. Please start over.")
        await utils.cleanup_user_data(context)
        return

    # Validate the dictionary using Pydantic before showing to user
    try:
         validated_data = CVData.model_validate(cv_data_dict)
         # Store the validated dict representation again
         context.user_data['cv_data'] = validated_data.model_dump(mode='json', exclude_unset=True)
    except Exception as e: # Catch Pydantic's ValidationError specifically if needed
         logger.error(f"Data validation failed before review: {e}\nData: {cv_data_dict}", exc_info=True)
         await update.effective_message.reply_text("There was an issue validating the collected data. Please try starting over.")
         await utils.cleanup_user_data(context)
         return

    context.user_data['state'] = config.STATE_REVIEWING_DATA
    review_text = utils.format_data_for_review(context.user_data['cv_data'])
    keyboard = utils.create_confirmation_keyboard("review")

    await update.effective_message.reply_text(
        review_text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_review_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, confirmed: bool):
    """Handles the user's confirmation after reviewing the data."""
    query = update.callback_query
    await query.answer() # Acknowledge callback

    if confirmed:
        await query.edit_message_text("Great! Now, let's choose a template.")
        await ask_template_selection(update, context)
    else:
        # Minimalist V1: Just restart
        await query.edit_message_text("Okay, let's start over. Use /start to begin.")
        await utils.cleanup_user_data(context)
        # Future: Implement editing specific sections

async def ask_template_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends the template selection keyboard."""
    context.user_data['state'] = config.STATE_SELECTING_TEMPLATE
    keyboard = utils.create_template_selection_keyboard()
    # Check if called from callback or message
    if update.callback_query:
         await update.callback_query.edit_message_text(
             "🎨 Choose a template style for your CV:",
             reply_markup=keyboard
         )
    elif update.effective_message:
         await update.effective_message.reply_text(
              "🎨 Choose a template style for your CV:",
              reply_markup=keyboard
         )

async def handle_template_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, template_key: str):
    """Generates the PDF using the selected template."""
    query = update.callback_query
    await query.answer()

    if template_key not in config.TEMPLATES:
        logger.warning(f"Invalid template key received: {template_key}")
        await query.edit_message_text("Invalid template selected. Please try again.")
        await ask_template_selection(update, context) # Ask again
        return

    cv_data_dict = context.user_data.get('cv_data')
    if not cv_data_dict:
        logger.error("No CV data found during template selection.")
        await query.edit_message_text("Something went wrong, I lost your data. Please start over with /start.")
        await utils.cleanup_user_data(context)
        return

    await query.edit_message_text(f"✨ Generating your '{config.TEMPLATES[template_key]['name']}' CV... Please wait.")
    context.user_data['state'] = config.STATE_GENERATING_PDF

    # Validate data again just before PDF generation (optional but safe)
    try:
        cv_data_model = CVData.model_validate(cv_data_dict)
    except Exception as e:
         logger.error(f"Data validation failed before PDF generation: {e}", exc_info=True)
         await query.message.reply_text("Error validating data before creating PDF. Please restart.")
         await utils.cleanup_user_data(context)
         return

    # Generate PDF
    pdf_bytes = await pdf_service.generate_cv_pdf(cv_data_model, template_key)

    if pdf_bytes:
        try:
            # Send the PDF
            pdf_file = InputFile(io.BytesIO(pdf_bytes), filename=f"CVBuilder_{cv_data_model.contact_info.full_name or 'cv'}.pdf")
            await query.message.reply_document(
                document=pdf_file,
                caption="✅ Here is your generated CV! ✨"
            )
            await query.edit_message_text("✅ PDF generated and sent!") # Edit the "Generating..." message
        except Exception as e:
             logger.error(f"Failed to send PDF document: {e}", exc_info=True)
             await query.message.reply_text("I generated the PDF, but there was an error sending it. Please try generating again later.")
             # Don't clean up data here, user might retry template selection
    else:
        await query.message.reply_text("😥 Sorry, there was an error creating the PDF for the selected template. You might try a different template or start over.")
        # Keep state for retrying template selection
        context.user_data['state'] = config.STATE_SELECTING_TEMPLATE
        await ask_template_selection(update, context) # Re-ask template selection

    # Clean up only after successful send (or maybe after explicit cancel/new start)
    # For V1, we clean up after attempting to send.
    await utils.cleanup_user_data(context)