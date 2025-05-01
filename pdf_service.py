import logging
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML
from typing import Optional
from schemas import CVData
from config import TEMPLATES

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"
env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(['html', 'xml'])
)


async def generate_cv_pdf(cv_data: CVData, template_key: str) -> Optional[bytes]:
    """Generates a PDF CV using WeasyPrint and Jinja2."""
    if template_key not in TEMPLATES:
        logger.error(f"Invalid template key specified: {template_key}")
        return None

    template_filename = TEMPLATES[template_key]["file"]
    template_path = TEMPLATE_DIR / template_filename

    if not template_path.is_file():
        logger.error(f"Template file not found: {template_path}")
        return None

    try:
        template = env.get_template(template_filename)
        
        rendered_html = template.render(cv=cv_data) 

        logger.info(f"Rendering PDF using template: {template_filename}")
        
        html = HTML(string=rendered_html, base_url=str(TEMPLATE_DIR))


        pdf_bytes = html.write_pdf()

        logger.info(f"Successfully generated PDF for template {template_key}")
        return pdf_bytes

    except Exception as e:
        logger.error(f"Error generating PDF for template {template_key}: {e}", exc_info=True)
        return None