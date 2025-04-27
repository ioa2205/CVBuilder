import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import ContextTypes
from PyPDF2 import PdfReader
from docx import Document
import io

from config import TEMPLATES

logger = logging.getLogger(__name__)

def create_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Creates the initial choice keyboard."""
    keyboard = [
        [InlineKeyboardButton("✨ Create New CV from Scratch", callback_data="create_scratch")],
        [InlineKeyboardButton("📄 Upload Existing CV (PDF/DOCX)", callback_data="create_upload")],
        # [InlineKeyboardButton("✏️ Edit Previous CV (Not Implemented)", callback_data="edit_cv")], # Future feature
    ]
    return InlineKeyboardMarkup(keyboard)

def create_confirmation_keyboard(callback_prefix: str) -> InlineKeyboardMarkup:
    """Creates a Yes/No confirmation keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, looks good!", callback_data=f"{callback_prefix}_yes"),
            InlineKeyboardButton("❌ No, let me restart", callback_data=f"{callback_prefix}_no"), # Simple restart for V1 minimalism
            # InlineKeyboardButton("✏️ Edit Section (Advanced)", callback_data=f"{callback_prefix}_edit"), # Future: Allow specific edits
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_template_selection_keyboard() -> InlineKeyboardMarkup:
    """Creates keyboard for selecting a CV template."""
    keyboard = [
        [InlineKeyboardButton(f"{idx+1}. {details['name']}", callback_data=f"select_template_{key}")]
        for idx, (key, details) in enumerate(TEMPLATES.items())
    ]
    # Add small image previews here if desired and feasible - requires hosting images
    # Example:
    # keyboard = [
    #     [InlineKeyboardButton(f"Template 1", callback_data=f"select_template_modern")],
    #     # Add image sending logic separately or use specific TG features if available
    # ]
    return InlineKeyboardMarkup(keyboard)


def extract_text_from_pdf(file_content: bytes) -> str:
    """Extracts text from PDF file content."""
    text = ""
    try:
        reader = PdfReader(io.BytesIO(file_content))
        for page in reader.pages:
            text += page.extract_text() or ""
    except Exception as e:
        logger.error(f"Error reading PDF: {e}", exc_info=True)
        return ""
    return text

def extract_text_from_docx(file_content: bytes) -> str:
    """Extracts text from DOCX file content."""
    text = ""
    try:
        document = Document(io.BytesIO(file_content))
        for para in document.paragraphs:
            text += para.text + "\n"
    except Exception as e:
        logger.error(f"Error reading DOCX: {e}", exc_info=True)
        return ""
    return text

async def cleanup_user_data(context: ContextTypes.DEFAULT_TYPE):
    """Clears user-specific data from context after completion or cancellation."""
    user_data = context.user_data
    keys_to_clear = ['state', 'cv_data', 'current_section_index', 'temp_file_id', 'temp_file_type']
    for key in keys_to_clear:
        if key in user_data:
            del user_data[key]
    logger.info(f"Cleaned up data for user {context._user_id}")


def format_data_for_review(cv_data: dict) -> str:
    """ Formats the extracted CV data into a readable string for user review. """
    review_text = "📄 *Please review the extracted information:*\n\n"

    if cv_data.get('contact_info'):
        review_text += "*Contact Info:*\n"
        ci = cv_data['contact_info']
        review_text += f"  Name: {ci.get('full_name', 'N/A')}\n"
        review_text += f"  Email: {ci.get('email', 'N/A')}\n"
        review_text += f"  Phone: {ci.get('phone', 'N/A')}\n"
        review_text += f"  LinkedIn: {ci.get('linkedin_url', 'N/A')}\n\n" # Add others if extracted

    if cv_data.get('summary'):
        review_text += f"*Summary:*\n{cv_data['summary']}\n\n"

    if cv_data.get('work_experience'):
        review_text += "*Work Experience:*\n"
        for i, job in enumerate(cv_data['work_experience']):
            review_text += f"  *{i+1}. {job.get('job_title', 'N/A')}* at {job.get('company', 'N/A')}\n"
            review_text += f"      ({job.get('start_date', 'N/A')} - {job.get('end_date', 'N/A')})\n"
            # Optionally add description points
        review_text += "\n"

    if cv_data.get('education'):
        review_text += "*Education:*\n"
        for i, edu in enumerate(cv_data['education']):
            review_text += f"  *{i+1}. {edu.get('degree', 'N/A')}* from {edu.get('institution', 'N/A')}\n"
            review_text += f"      (Graduated: {edu.get('graduation_date', 'N/A')})\n"
        review_text += "\n"

    if cv_data.get('skills'):
        review_text += "*Skills:*\n"
        # Simple list format example
        skills_flat = []
        for skill_cat in cv_data['skills']:
             if skill_cat.get('skills_list'):
                 skills_flat.extend(skill_cat['skills_list'])
        if skills_flat:
             review_text += f"  - {', '.join(skills_flat)}\n"
        else:
             # Fallback if structure is different or just a list of strings was extracted
             if isinstance(cv_data['skills'], list) and all(isinstance(s, str) for s in cv_data['skills']):
                  review_text += f"  - {', '.join(cv_data['skills'])}\n"

    # Truncate if too long for Telegram message limits
    max_len = 4000 # Slightly less than max 4096
    if len(review_text) > max_len:
        review_text = review_text[:max_len] + "\n\n... (output truncated)"

    return review_text