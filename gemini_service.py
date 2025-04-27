import logging
import google.generativeai as genai
import json
from pydantic import ValidationError
from typing import Optional

import config
from schemas import CVData

logger = logging.getLogger(__name__)

# Configure the Gemini client (do this once)
try:
    genai.configure(api_key=config.GEMINI_API_KEY)
    # Optional: Set safety settings if needed
    # safety_settings = [
    #     {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    #     # ... other categories
    # ]
    model = genai.GenerativeModel(
        'gemini-2.5-pro-exp-03-25', # Use the appropriate model name
        # safety_settings=safety_settings
        generation_config=genai.types.GenerationConfig(
            # Ensure JSON output if model supports it directly, otherwise rely on prompt.
             # response_mime_type="application/json" # Requires specific model support
             temperature=0.2 # Lower temperature for more predictable structured output
        )
    )
    logger.info("Gemini AI client configured successfully.")
except Exception as e:
    logger.error(f"Failed to configure Gemini AI client: {e}", exc_info=True)
    model = None

def get_parsing_prompt(cv_text: str) -> str:
    """Creates the prompt for Gemini to parse CV text."""

    # Define the desired JSON schema structure within the prompt
    # This helps Gemini understand the target output format.
    # Using the Pydantic schema definition directly can be helpful.
    schema_description = CVData.model_json_schema()

    prompt = f"""
    Analyze the following CV text and extract the information into a structured JSON object.

    **CV Text:**
    ---
    {cv_text}
    ---

    **Instructions:**
    1.  Extract the following sections: Contact Information, Summary, Work Experience, Education, Skills.
    2.  For Work Experience and Education, create a list of objects, one for each job or degree.
    3.  For skills, try to categorize them if possible (e.g., "Programming Languages", "Tools"), otherwise provide a flat list. The desired category structure is: [{{"category": "...", "skills_list": ["...", "..."]}}, ...]. If categorization is not clear, use a single category like "Technical Skills" or "Other Skills".
    4.  Format dates consistently if possible (e.g., YYYY-MM or Month YYYY), but preserve original if unclear. Use "Present" for current roles/studies if indicated.
    5.  For work experience descriptions, provide a list of strings, where each string is a bullet point or responsibility statement.
    6.  If a section is clearly missing in the text, omit it from the JSON or represent it as null/empty list as appropriate based on the schema.
    7.  **Output MUST be a valid JSON object conforming to this Pydantic schema:**
        ```json
        {schema_description}
        ```
    8.  Do NOT include any introductory text, explanations, or markdown formatting around the JSON output. Only output the JSON object itself.

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
        # Ensure we handle potential API errors during generation
        response = await model.generate_content_async(prompt) # Use async if available & needed

        # Debug: Log raw response
        # logger.debug(f"Gemini Raw Response Parts: {response.parts}")
        # logger.debug(f"Gemini Raw Response Text: {response.text}")

        # Attempt to parse the JSON response
        try:
            # Clean potential markdown code fences if present
            json_text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
            # Validate the parsed JSON against the Pydantic schema
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
        # Catching broad exceptions from the API call itself
        logger.error(f"Error calling Gemini API: {e}", exc_info=True)
        # Check for specific Gemini exceptions if the SDK provides them
        # Example: if isinstance(e, google.api_core.exceptions.ResourceExhausted): ...
        return None