import logging
from telegram import Update, InputFile
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
import io
from typing import Optional, List, Dict, Any # Added Dict, Any, List
import config
import utils
import gemini_service
import pdf_service
# Import all schemas explicitly for clarity
from schemas import CVData, ContactInfo, WorkExperienceItem, EducationItem, SkillItem, ProjectItem, LanguageItem, CertificationItem, AwardItem
logger = logging.getLogger(__name__)

# --- Scratch Flow ---

async def start_scratch_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiates the CV creation from scratch."""
    await utils.cleanup_user_data(context) # Clear previous state first
    context.user_data['state'] = config.STATE_SCRATCH_START
    # Initialize with structure expected by Pydantic later (using nested dicts)
    context.user_data['cv_data'] = {
        "contact_info": {},
        "summary": None,
        "work_experience": [],
        "education": [],
        "skills": [],
        "projects": [],
        "languages": [],
        "certifications": [],
        "awards": []
    }
    context.user_data['current_section_index'] = 0
    # No longer need scratch_data_buffer if we add directly to cv_data lists
    # context.user_data['scratch_data_buffer'] = {}

    await ask_next_scratch_question(update, context)

def _get_current_section_details(context: ContextTypes.DEFAULT_TYPE) -> tuple[Optional[str], Optional[str], Optional[int]]:
    """Helper to get current section key, readable name, and index."""
    idx = context.user_data.get('current_section_index', 0)
    if idx >= len(config.CV_SECTIONS):
        return None, None, idx

    section_key = config.CV_SECTIONS[idx]
    section_readable = section_key.replace('_', ' ').replace('.', ' -> ').title()
    return section_key, section_readable, idx

async def ask_next_scratch_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asks the user for the next piece of information in the scratch flow."""
    section_key, section_readable, idx = _get_current_section_details(context)

    if section_key is None:
        # All sections done, move to review
        await transition_to_review(update, context)
        return

    prompt_text = f"📝 Please provide information for: *{section_readable}*"

    # --- Add detailed prompts for new sections ---
    if section_key == "work_experience":
        prompt_text += "\n\n*Format for each job:*\n`Title` at `Company` (`Start Date` - `End Date`)\nOptional: Location on next line\n- Responsibility 1\n- Responsibility 2\n\nType 'DONE' when finished adding jobs."
        # Initialize list if not present (safety check)
        context.user_data['cv_data'].setdefault('work_experience', [])
    elif section_key == "education":
        prompt_text += "\n\n*Format for each degree:*\n`Degree` from `Institution` (`Graduation Date`)\nOptional: Location on next line\nOptional details on next line.\n\nType 'DONE' when finished adding degrees."
        context.user_data['cv_data'].setdefault('education', [])
    elif section_key == "skills":
        prompt_text += "\n\nEnter skills separated by commas (e.g., Python, Java, SQL). You can optionally group them like: `Category: Skill1, Skill2` (e.g., `Languages: Python, Go`)"
        context.user_data['cv_data'].setdefault('skills', [])
    elif section_key == "projects":
        prompt_text += "\n\n*Format for each project:*\nProject Name: `Name`\nDescription: `Brief description...`\nTechnologies: `Tech1, Tech2`\nURL: `(Optional URL)`\nDuration: `(Optional duration)`\n\nType 'DONE' when finished adding projects."
        context.user_data['cv_data'].setdefault('projects', [])
    elif section_key == "languages":
        prompt_text += "\n\n*Format for each language:*\n`Language Name` - `Proficiency` (e.g., Spanish - Fluent, German - Conversational)\n\nType 'DONE' when finished adding languages."
        context.user_data['cv_data'].setdefault('languages', [])
    elif section_key == "certifications":
        prompt_text += "\n\n*Format for each certification:*\nCertification Name: `Name`\nIssuing Org: `Organization`\nDate: `(Issue Date)`\nID: `(Optional ID)`\nURL: `(Optional URL)`\n\nType 'DONE' when finished adding certifications."
        context.user_data['cv_data'].setdefault('certifications', [])
    elif section_key == "awards":
        prompt_text += "\n\n*Format for each award:*\nAward Name: `Name`\nOrganization: `Granting Org`\nDate: `(Date Received)`\nDescription: `(Optional Context)`\n\nType 'DONE' when finished adding awards."
        context.user_data['cv_data'].setdefault('awards', [])
    elif section_key == "summary":
         prompt_text += "\n\nEnter your professional summary or objective statement."
    elif section_key.startswith("contact_info."):
        field_name = section_key.split('.')[-1].replace('_', ' ').title()
        prompt_text = f"📝 Please enter your *{field_name}*:"
        if "Url" in field_name:
            prompt_text += " (Please provide the full URL, e.g., https://...)"


    context.user_data['state'] = config.STATE_SCRATCH_AWAIT_DATA
    # Use effective_message for potential edits later if needed
    if update.effective_message:
        await update.effective_message.reply_text(prompt_text, parse_mode=ParseMode.MARKDOWN)
    elif update.callback_query and update.callback_query.message:
         # If called after a button press (like skipping a section in future)
         await update.callback_query.message.reply_text(prompt_text, parse_mode=ParseMode.MARKDOWN)

async def handle_scratch_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes user input during the scratch flow."""
    if not update.message or not update.message.text:
        logger.warning("Received non-text message or empty message in handle_scratch_input")
        # Maybe prompt again? Or ignore? Let's prompt again gently.
        await update.effective_message.reply_text("Please provide the requested information as text.")
        await ask_next_scratch_question(update, context) # Re-ask current question
        return

    user_input = update.message.text
    section_key, section_readable, idx = _get_current_section_details(context)

    if section_key is None:
        logger.warning(f"Received unexpected text message in state: {context.user_data.get('state')} after sections finished.")
        return

    cv_data = context.user_data.get('cv_data', {}) # Should be initialized in start_scratch_flow

    # --- Refactored Handling for Multi-Entry Sections ---
    async def process_multi_entry(section_list_key: str, parse_function: callable):
        nonlocal user_input, cv_data, context
        if user_input.strip().upper() == 'DONE':
            context.user_data['current_section_index'] += 1
            await ask_next_scratch_question(update, context)
        else:
            try:
                item_data = parse_function(user_input)
                if item_data: # Ensure parser returned something
                     cv_data.setdefault(section_list_key, []).append(item_data)
                     await update.effective_message.reply_text(f"{section_readable.split(' -> ')[-1]} item added. Add another or type 'DONE'.")
                else:
                     # Parser indicated invalid format or empty input
                     await update.effective_message.reply_text("Sorry, I couldn't understand that format or the input was empty. Please try again using the specified format, or type 'DONE'.")
            except Exception as e:
                logger.error(f"Failed to parse {section_list_key} input: {e}\nInput: {user_input}", exc_info=True)
                await update.effective_message.reply_text("Sorry, there was an error processing that input. Please check the format and try again, or type 'DONE'.")
        # For multi-entry, always return to wait for next entry or 'DONE'
        return True # Indicates flow should pause for next input

    # --- Define Simple Parsers for Multi-Entry (Example Implementation) ---
    # These need to be robust or replaced with asking field-by-field later

    def parse_work_experience(text: str) -> Optional[Dict[str, Any]]:
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if not lines: return None
        item = WorkExperienceItem().model_dump() # Get default dict
        try:
            # "Title at Company (Start - End)"
            first_line_parts = lines[0].split(' at ')
            item['job_title'] = first_line_parts[0].strip()
            company_date_parts = first_line_parts[1].split('(')
            item['company'] = company_date_parts[0].strip()
            date_str = company_date_parts[1].replace(')', '').strip()
            if ' - ' in date_str:
                start_date, end_date = [d.strip() for d in date_str.split(' - ', 1)]
                item['start_date'] = start_date
                item['end_date'] = end_date
            else: # Handle single date case if needed, or assume start date if only one provided
                 item['start_date'] = date_str # Or handle error

            desc_lines = []
            loc_line = 1 # Check line 2 for location first
            if len(lines) > 1 and not lines[loc_line].startswith('-'):
                 item['location'] = lines[loc_line]
                 desc_lines = lines[loc_line+1:]
            else:
                 desc_lines = lines[1:] # If no location, desc starts from line 2

            item['description'] = [line.lstrip('- ') for line in desc_lines if line.startswith('-')]
            # Add non-bullet points as description too? Depends on desired strictness
            # item['description'] = [line.lstrip('- ') for line in desc_lines]

            return item
        except IndexError: # Handle cases where split fails
             logger.warning(f"IndexError parsing work experience: {text}")
             return None
        except Exception as e:
            logger.error(f"Generic error parsing work experience: {e} for text {text}")
            return None # Or re-raise specific errors

    def parse_education(text: str) -> Optional[Dict[str, Any]]:
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if not lines: return None
        item = EducationItem().model_dump()
        try:
            # "Degree from Institution (Grad Date)"
            first_line_parts = lines[0].split(' from ')
            item['degree'] = first_line_parts[0].strip()
            inst_date_parts = first_line_parts[1].split('(')
            item['institution'] = inst_date_parts[0].strip()
            item['graduation_date'] = inst_date_parts[1].replace(')', '').strip()

            detail_lines = []
            loc_line = 1
            if len(lines) > 1 and '(' not in lines[loc_line] and 'from' not in lines[loc_line]: # Heuristic for location vs details
                 item['location'] = lines[loc_line]
                 detail_lines = lines[loc_line+1:]
            else:
                 detail_lines = lines[1:]

            item['details'] = "\n".join(detail_lines).strip() if detail_lines else None
            return item
        except IndexError:
            logger.warning(f"IndexError parsing education: {text}")
            return None
        except Exception as e:
            logger.error(f"Generic error parsing education: {e} for text {text}")
            return None

    def parse_project(text: str) -> Optional[Dict[str, Any]]:
         # Parses based on the "Key: Value" format provided in the prompt
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if not lines: return None
        item = ProjectItem().model_dump()
        data_map = {}
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                data_map[key.strip().lower()] = value.strip()

        item['project_name'] = data_map.get('project name')
        item['description'] = data_map.get('description')
        item['technologies'] = [t.strip() for t in data_map.get('technologies', '').split(',') if t.strip()]
        item['project_url'] = data_map.get('url')
        item['duration'] = data_map.get('duration')

        if not item['project_name']: # Require at least a name
            return None
        return item

    def parse_language(text: str) -> Optional[Dict[str, Any]]:
         # "Language - Proficiency"
         parts = [p.strip() for p in text.split('-', 1)]
         if len(parts) == 2:
             item = LanguageItem().model_dump()
             item['language'] = parts[0]
             item['proficiency'] = parts[1]
             return item
         return None

    def parse_certification(text: str) -> Optional[Dict[str, Any]]:
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if not lines: return None
        item = CertificationItem().model_dump()
        data_map = {}
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                data_map[key.strip().lower().replace('issuing org', 'issuing_organization')] = value.strip() # Normalize key

        item['name'] = data_map.get('certification name')
        item['issuing_organization'] = data_map.get('issuing_organization')
        item['issue_date'] = data_map.get('date')
        item['credential_id'] = data_map.get('id')
        item['credential_url'] = data_map.get('url')

        if not item['name']: # Require name
            return None
        return item

    def parse_award(text: str) -> Optional[Dict[str, Any]]:
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if not lines: return None
        item = AwardItem().model_dump()
        data_map = {}
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                data_map[key.strip().lower()] = value.strip()

        item['name'] = data_map.get('award name')
        item['organization'] = data_map.get('organization')
        item['date'] = data_map.get('date')
        item['description'] = data_map.get('description')

        if not item['name']: # Require name
            return None
        return item

    # --- Main Input Handling Logic ---
    should_pause = False
    if section_key == "work_experience":
        should_pause = await process_multi_entry('work_experience', parse_work_experience)
    elif section_key == "education":
        should_pause = await process_multi_entry('education', parse_education)
    elif section_key == "projects":
        should_pause = await process_multi_entry('projects', parse_project)
    elif section_key == "languages":
        should_pause = await process_multi_entry('languages', parse_language)
    elif section_key == "certifications":
        should_pause = await process_multi_entry('certifications', parse_certification)
    elif section_key == "awards":
        should_pause = await process_multi_entry('awards', parse_award)

    elif section_key == "skills":
        # Handle potentially categorized input: "Category: Skill1, Skill2" or just "Skill1, Skill2"
        lines = [line.strip() for line in user_input.split('\n') if line.strip()]
        parsed_skills = []
        for line in lines:
             if ':' in line:
                  category, skills_part = line.split(':', 1)
                  skills_list = [s.strip() for s in skills_part.split(',') if s.strip()]
                  if skills_list:
                       parsed_skills.append(SkillItem(category=category.strip(), skills_list=skills_list).model_dump())
             else:
                  # Assume general category if no colon
                  skills_list = [s.strip() for s in line.split(',') if s.strip()]
                  if skills_list:
                       # Check if a 'General' category already exists to append
                       found_general = False
                       for item in parsed_skills:
                            if item.get('category', '').lower() == 'general':
                                 item.setdefault('skills_list', []).extend(skills_list)
                                 item['skills_list'] = list(set(item['skills_list'])) # Avoid duplicates
                                 found_general = True
                                 break
                       if not found_general:
                            parsed_skills.append(SkillItem(category="General", skills_list=skills_list).model_dump())

        if parsed_skills:
             cv_data['skills'] = parsed_skills # Replace previous simple list/structure
             context.user_data['current_section_index'] += 1
        else:
             # Handle case where input was provided but couldn't be parsed into skills
             await update.effective_message.reply_text("Couldn't parse any skills from your input. Please use comma-separated format, optionally with 'Category: Skill1, Skill2'.")
             # Don't advance index, re-ask the question implicitly next time

    # --- Handling simple sections (Contact Info, Summary) ---
    elif section_key == "summary":
        cv_data['summary'] = user_input.strip()
        context.user_data['current_section_index'] += 1
    elif section_key.startswith("contact_info."):
        # Already initialized as dict in start_scratch_flow
        field_key = section_key.split('.')[-1]
        cv_data.setdefault('contact_info', {})[field_key] = user_input.strip()
        context.user_data['current_section_index'] += 1
    else:
        # Fallback for any potentially missed simple section key
        logger.warning(f"Unhandled simple section key in handle_scratch_input: {section_key}")
        # Store it flatly for now, might cause validation issues later
        cv_data[section_key] = user_input.strip()
        context.user_data['current_section_index'] += 1


    # --- Advance to next question or review ---
    if not should_pause: # Only advance if not waiting for more multi-entry items
        next_section_key, _, next_idx = _get_current_section_details(context) # Check state *after* potential index increment
        if next_section_key is None:
             await transition_to_review(update, context)
        else:
             await ask_next_scratch_question(update, context)

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

# def structure_scratch_data(raw_data: dict) -> dict:
#      """Converts the flat data collected during scratch flow into nested structure."""
#      # This is where you'd map {"contact_info.full_name": "..."} to {"contact_info": {"full_name": "..."}}
#      # And ensure work_experience/education/skills are lists of dicts/objects
#      # For simplicity in this example, assume the structure is already somewhat nested,
#      # but validation will happen later.
#      # A more robust implementation would use the keys like "contact_info.full_name"
#      # to build the nested dict properly.
#      # Let's assume handle_scratch_input already created a basic nested structure.
#      structured = {}
#      if 'contact_info' in raw_data:
#           structured['contact_info'] = raw_data['contact_info']
#      if 'summary' in raw_data:
#            structured['summary'] = raw_data['summary']
#      if 'work_experience' in raw_data and isinstance(raw_data['work_experience'], list):
#            structured['work_experience'] = raw_data['work_experience']
#      if 'education' in raw_data and isinstance(raw_data['education'], list):
#            structured['education'] = raw_data['education']
#      if 'skills' in raw_data and isinstance(raw_data['skills'], list):
#           structured['skills'] = raw_data['skills'] # Assumes simple structure was saved

#      # logger.debug(f"Structured scratch data: {structured}")
#      return structured

async def transition_to_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Formats data and asks the user to review."""
    # Data should already be structured correctly in context.user_data['cv_data']
    # from both scratch and upload flows.
    cv_data_dict = context.user_data.get('cv_data', {})

    if not cv_data_dict:
        logger.error("No CV data found when transitioning to review.")
        await update.effective_message.reply_text("Something went wrong, no data to review. Please start over with /start.")
        await utils.cleanup_user_data(context)
        return

    # Validate the dictionary using Pydantic before showing to user
    try:
         logger.debug(f"Data before validation in transition_to_review: {cv_data_dict}")
         # Ensure default values are handled correctly if keys are missing
         validated_data = CVData.model_validate(cv_data_dict)
         # Store the validated dict representation again (includes defaults from Pydantic model)
         context.user_data['cv_data'] = validated_data.model_dump(mode='json', exclude_unset=True)
         logger.debug(f"Data after validation and dump: {context.user_data['cv_data']}")
    except Exception as e: # Catch Pydantic's ValidationError specifically if needed
         logger.error(f"Data validation failed before review: {e}\nData: {cv_data_dict}", exc_info=True)
         await update.effective_message.reply_text(f"There was an issue validating the collected data. Please try starting over.\nError details (for debugging): {e}")
         await utils.cleanup_user_data(context)
         return

    context.user_data['state'] = config.STATE_REVIEWING_DATA
    review_text = utils.format_data_for_review(context.user_data['cv_data']) # Pass the validated data
    keyboard = utils.create_confirmation_keyboard("review")

    # Use effective_message to handle both callback query edits and direct messages
    message_func = None
    if update.callback_query:
        message_func = update.callback_query.edit_message_text
    elif update.effective_message:
        # Send as new message if coming from direct text input
        message_func = update.effective_message.reply_text

    if message_func:
        await message_func(
            review_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
         logger.error("Could not find method to send review message.")
         # Fallback if somehow neither callback nor message is available
         await context.bot.send_message(chat_id=update.effective_chat.id, text="Please review the data:", reply_markup=keyboard)
         await context.bot.send_message(chat_id=update.effective_chat.id, text=review_text, parse_mode=ParseMode.MARKDOWN)

async def handle_review_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, confirmed: bool):
    """Handles the user's confirmation after reviewing the data."""
    query = update.callback_query
    await query.answer() # Acknowledge callback

    if confirmed:
        await query.edit_message_text("Great! Now, let's choose a template.")
        # Ensure we pass update object correctly if ask_template_selection expects it
        await ask_template_selection(update, context) # Pass update here
    else:
        # V1: Just restart. Future: Implement editing.
        await query.edit_message_text("Okay, let's start over. Use /start to begin.")
        await utils.cleanup_user_data(context)

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