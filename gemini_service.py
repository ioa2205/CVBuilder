import logging
import google.generativeai as genai
import json
from pydantic import ValidationError
from typing import Optional

import config
from schemas import CVData

logger = logging.getLogger(__name__)

try:
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        'gemini-2.5-flash-preview-04-17',
        generation_config=genai.types.GenerationConfig(
             temperature=0.2 
        )
    )
    logger.info("Gemini AI client configured successfully.")
except Exception as e:
    logger.error(f"Failed to configure Gemini AI client: {e}", exc_info=True)
    model = None

def get_parsing_prompt(cv_text: str) -> str:
    """Creates the prompt for Gemini to parse CV text."""

    schema_description = CVData.model_json_schema()

    prompt = f"""
    Analyze the following CV text and extract the information into a structured JSON object.

    **CV Text:**
    ---
    {cv_text}
    ---

    **Instructions:**
    1.  Extract the relevant information for the following sections if present: Contact Information (`contact_info`), Summary (`summary`), Work Experience (`work_experience`), Education (`education`), Skills (`skills`), Projects (`projects`), Languages (`languages`), Certifications (`certifications`), Awards (`awards`).
    2.  For `work_experience`, `education`, `projects`, `languages`, `certifications`, and `awards`, create a list of objects, one for each distinct item found in the text.
    3.  For `skills`, structure them as a list of objects: `[{{"category": "...", "skills_list": ["...", "..."]}}]`. Attempt categorization (e.g., "Programming Languages", "Software", "Databases", "Soft Skills", "Languages"). If unsure, use a general category like "Technical Skills" or "Other Skills".
    4.  For `languages`, extract the language name and proficiency level (e.g., Native, Fluent, Conversational, Basic).
    5.  For `projects`, include name, description, technologies used, and URL if available.
    6.  For `certifications`, include name, issuing body, issue date, and credential URL/ID if available.
    7.  For `awards`, include name, organization, and date.
    8.  Format dates consistently if possible (e.g., YYYY-MM or Month YYYY), but preserve original if unclear. Use "Present" for current roles.
    9.  For descriptions (work experience, projects), provide a list of strings or a single string where appropriate based on the schema.
    10. If a section is clearly missing in the text, omit its key from the JSON or represent it as `null` or an empty list (`[]`) as appropriate based on the schema definition.
    11. **Output MUST be a valid JSON object conforming strictly to this Pydantic schema:**
        ```json
        {schema_description}
        ```
    12. Do NOT include any introductory text, explanations, comments, or markdown formatting (like ```json) around the JSON output. Only output the raw, valid JSON object itself.

    **JSON Output:**
    """
    return prompt

async def parse_cv_text_with_gemini(cv_text: str) -> Optional[CVData]:
    """Uses Gemini API to parse CV text into a structured CVData object."""
    if not model:
        logger.error("Gemini model not initialized.")
        return None
    if not cv_text or cv_text.isspace():
        logger.warning("Received empty CV text for parsing.")
        return None

    prompt = get_parsing_prompt(cv_text)
    logger.info("Sending request to Gemini API for CV parsing...")

    try:
        response = await model.generate_content_async(prompt) 

        try:
            json_text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
            parsed_data = CVData.model_validate_json(json_text)
            logger.info("Successfully parsed and validated CV data from Gemini.")
            return parsed_data
        except json.JSONDecodeError as e:
            logger.error(f"Gemini response was not valid JSON: {e}\nRaw response:\n{response.text}", exc_info=True)
            return None
        except ValidationError as e:
            logger.error(f"Gemini response JSON did not match schema: {e}\nRaw response:\n{response.text}", exc_info=True)
            return None
        except AttributeError:
             logger.error(f"Could not access Gemini response text. Response object: {response}", exc_info=True)
             return None


    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}", exc_info=True)
        return None