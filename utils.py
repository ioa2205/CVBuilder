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
    ]
    return InlineKeyboardMarkup(keyboard)

def create_confirmation_keyboard(callback_prefix: str) -> InlineKeyboardMarkup:
    """Creates a Yes/No confirmation keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, looks good!", callback_data=f"{callback_prefix}_yes"),
            InlineKeyboardButton("❌ No, let me restart", callback_data=f"{callback_prefix}_no"), # Simple restart for V1 minimalism
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_template_selection_keyboard() -> InlineKeyboardMarkup:
    """Creates keyboard for selecting a CV template."""
    keyboard = [
        [InlineKeyboardButton(f"{idx+1}. {details['name']}", callback_data=f"select_template_{key}")]
        for idx, (key, details) in enumerate(TEMPLATES.items())
    ]
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
    if 'scratch_data_buffer' in keys_to_clear:
        keys_to_clear.remove('scratch_data_buffer')
    user_id = "N/A"
    try:
        user_id = context._user_id # Attempt to get user ID for logging
    except AttributeError:
         pass # May not always be available depending on context source

    # Create a copy of keys to avoid modifying dict during iteration
    for key in list(user_data.keys()):
        if key in keys_to_clear:
            del user_data[key]
    logger.info(f"Cleaned up data for user {user_id}")



def format_data_for_review(cv_data: dict) -> str:
    """ Formats the extracted CV data into a readable string for user review. """
    review_text = "📄 *Please review the collected information:*\n\n"

    # Use .get() extensively to avoid errors if a section is missing/None
    if cv_data.get('contact_info'):
        review_text += "*Contact Info:*\n"
        ci = cv_data['contact_info']
        review_text += f"  Name: {ci.get('full_name', 'N/A')}\n"
        review_text += f"  Email: {ci.get('email', 'N/A')}\n"
        review_text += f"  Phone: {ci.get('phone', 'N/A')}\n"
        review_text += f"  LinkedIn: {ci.get('linkedin_url', 'N/A')}\n"
        review_text += f"  Portfolio: {ci.get('portfolio_url', 'N/A')}\n" # Added
        review_text += f"  Address: {ci.get('address', 'N/A')}\n\n"       # Added

    if cv_data.get('summary'):
        review_text += f"*Summary:*\n{cv_data['summary']}\n\n"

    if cv_data.get('work_experience'):
        review_text += "*Work Experience:*\n"
        for i, job in enumerate(cv_data['work_experience']):
            title = job.get('job_title', 'N/A')
            company = job.get('company', 'N/A')
            start = job.get('start_date', 'N/A')
            end = job.get('end_date', 'N/A')
            loc = f" ({job.get('location')})" if job.get('location') else ""
            review_text += f"  *{i+1}. {title}* at {company}{loc}\n"
            review_text += f"      ({start} - {end})\n"
        review_text += "\n"

    if cv_data.get('education'):
        review_text += "*Education:*\n"
        for i, edu in enumerate(cv_data['education']):
            degree = edu.get('degree', 'N/A')
            inst = edu.get('institution', 'N/A')
            grad_date = edu.get('graduation_date', 'N/A')
            loc = f" ({edu.get('location')})" if edu.get('location') else ""
            review_text += f"  *{i+1}. {degree}* from {inst}{loc}\n"
            review_text += f"      (Graduated: {grad_date})\n"
            if edu.get('details'):
                review_text += f"      Details: {edu['details'][:100]}...\n" # Show snippet
        review_text += "\n"

    if cv_data.get('skills'):
        review_text += "*Skills:*\n"
        for skill_cat in cv_data['skills']:
             category = skill_cat.get('category', 'General')
             skills_list = skill_cat.get('skills_list', [])
             if skills_list:
                  review_text += f"  *{category}:* {', '.join(skills_list)}\n"
        review_text += "\n"

    if cv_data.get('projects'):
        review_text += "*Projects:*\n"
        for i, proj in enumerate(cv_data['projects']):
            name = proj.get('project_name', 'N/A')
            desc = proj.get('description', '')[:100] + '...' if proj.get('description') else 'N/A'
            tech = f" (Tech: {', '.join(proj.get('technologies',[]))})" if proj.get('technologies') else ""
            review_text += f"  *{i+1}. {name}*{tech}\n"
            review_text += f"      Desc: {desc}\n"
            if proj.get('project_url'):
                 review_text += f"      URL: {proj.get('project_url')}\n"
        review_text += "\n"

    if cv_data.get('languages'):
        review_text += "*Languages:*\n"
        lang_list = [f"{lang.get('language','?')} ({lang.get('proficiency','?')})" for lang in cv_data['languages']]
        if lang_list:
            review_text += f"  - {', '.join(lang_list)}\n"
        review_text += "\n"

    if cv_data.get('certifications'):
        review_text += "*Certifications:*\n"
        for i, cert in enumerate(cv_data['certifications']):
            name = cert.get('name', 'N/A')
            org = cert.get('issuing_organization', 'N/A')
            date = cert.get('issue_date', 'N/A')
            review_text += f"  *{i+1}. {name}* from {org} ({date})\n"
        review_text += "\n"

    if cv_data.get('awards'):
        review_text += "*Awards:*\n"
        for i, award in enumerate(cv_data['awards']):
            name = award.get('name', 'N/A')
            org = award.get('organization', 'N/A')
            date = award.get('date', 'N/A')
            review_text += f"  *{i+1}. {name}* from {org} ({date})\n"
        review_text += "\n"

    max_len = 4000 
    if len(review_text) > max_len:
        review_text = review_text[:max_len] + "\n\n... (output truncated, full data saved)"

    return review_text