import os
from dotenv import load_dotenv

load_dotenv() 

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Missing environment variable: TELEGRAM_BOT_TOKEN")
if not GEMINI_API_KEY:
    raise ValueError("Missing environment variable: GEMINI_API_KEY")


CV_SECTIONS = [
    "contact_info.full_name",
    "contact_info.email",
    "contact_info.phone",
    "contact_info.linkedin_url",
    "contact_info.address",     
    "summary",
    "work_experience", 
    "education",      
    "skills",         
    "projects",       
    "languages",      
    "certifications",  
    "awards",          
]

TEMPLATES = {
    "modern": {"name": "Modern Minimalist", "file": "template_1.html"},
    "classic": {"name": "Classic Professional", "file": "template_2.html"},
    "creative": {"name": "Creative Tech", "file": "template_3.html"},
}

STATE_START = "START"
STATE_AWAITING_CHOICE = "AWAITING_CHOICE" 
STATE_SCRATCH_START = "SCRATCH_START"
STATE_SCRATCH_AWAIT_DATA = "SCRATCH_AWAIT_DATA"
STATE_UPLOAD_AWAIT_FILE = "UPLOAD_AWAIT_FILE"
STATE_UPLOAD_PARSING = "UPLOAD_PARSING"
STATE_REVIEWING_DATA = "REVIEWING_DATA"
STATE_SELECTING_TEMPLATE = "SELECTING_TEMPLATE"
STATE_GENERATING_PDF = "GENERATING_PDF"