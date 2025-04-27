import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Missing environment variable: TELEGRAM_BOT_TOKEN")
if not GEMINI_API_KEY:
    raise ValueError("Missing environment variable: GEMINI_API_KEY")

# Define CV sections for the "From Scratch" flow
CV_SECTIONS = [
    "contact_info.full_name",
    "contact_info.email",
    "contact_info.phone",
    "contact_info.linkedin_url", # Optional field example
    "summary",
    "work_experience", # Will need special handling for multiple entries
    "education",       # Will need special handling for multiple entries
    "skills",          # Will need special handling for list
]

# Template Definitions (Maps internal name to display name and filename)
TEMPLATES = {
    "modern": {"name": "Modern Minimalist", "file": "template_1.html"},
    "classic": {"name": "Classic Professional", "file": "template_2.html"},
    "creative": {"name": "Creative Tech", "file": "template_3.html"},
}

# State Constants (optional, but good practice)
STATE_START = "START"
STATE_AWAITING_CHOICE = "AWAITING_CHOICE" # After /start
STATE_SCRATCH_START = "SCRATCH_START"
STATE_SCRATCH_AWAIT_DATA = "SCRATCH_AWAIT_DATA"
STATE_UPLOAD_AWAIT_FILE = "UPLOAD_AWAIT_FILE"
STATE_UPLOAD_PARSING = "UPLOAD_PARSING"
STATE_REVIEWING_DATA = "REVIEWING_DATA"
STATE_SELECTING_TEMPLATE = "SELECTING_TEMPLATE"
STATE_GENERATING_PDF = "GENERATING_PDF"