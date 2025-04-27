import logging
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML, CSS
from typing import Optional
from schemas import CVData
from config import TEMPLATES

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"
# Create Jinja2 environment (cache templates in production)
env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(['html', 'xml'])
)
# Configure fonts for WeasyPrint (optional, if defaults aren't enough or you need custom fonts)
# font_config = FontConfiguration()

async def generate_cv_pdf(cv_data: CVData, template_key: str) -> Optional[bytes]:
    """Generates a PDF CV using WeasyPrint and Jinja2."""
    if template_key not in TEMPLATES:
        logger.error(f"Invalid template key specified: {template_key}")
        return None

    template_filename = TEMPLATES[template_key]["file"]
    template_path = TEMPLATE_DIR / template_filename
    css_path = TEMPLATE_DIR / "base_template.css" # Example common CSS

    if not template_path.is_file():
        logger.error(f"Template file not found: {template_path}")
        return None

    try:
        template = env.get_template(template_filename)
        # Pass the Pydantic model directly, Jinja2 can access its attributes
        # Or convert to dict: cv_data.model_dump(mode='json') # Use mode='json' for serializable types
        rendered_html = template.render(cv=cv_data) # Pass data under 'cv' key

        logger.info(f"Rendering PDF using template: {template_filename}")

        # Load base CSS if it exists
        stylesheets = []
        if css_path.is_file():
            stylesheets.append(CSS(filename=css_path)) #, font_config=font_config))
        else:
             logger.warning(f"Base CSS file not found: {css_path}")

        # Create HTML object
        html = HTML(string=rendered_html, base_url=str(TEMPLATE_DIR)) # base_url helps resolve relative paths in HTML/CSS

        # Generate PDF bytes
        # Pass font_config=font_config if using custom font configuration
        pdf_bytes = html.write_pdf(stylesheets=stylesheets)

        logger.info(f"Successfully generated PDF for template {template_key}")
        return pdf_bytes

    except Exception as e:
        logger.error(f"Error generating PDF for template {template_key}: {e}", exc_info=True)
        return None