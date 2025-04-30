# CVBuilder Telegram Bot

A Telegram bot designed to help users create professional, minimalist, and visually appealing CVs (Resumes). Users can either upload an existing CV (PDF/DOCX) for intelligent parsing via the Google Gemini API or create one from scratch through a guided question-and-answer process. The final CV is rendered into a PDF using a selection of pre-defined, stylish HTML/CSS templates.

## Features

*   **CV Creation from Upload:** Parses uploaded PDF or DOCX files using the Gemini API to extract structured information (Contact, Summary, Experience, Education, Skills).
*   **CV Creation from Scratch:** Guides users through a conversational Q&A flow to collect CV details section by section.
*   **Template Selection:** Offers multiple pre-defined, professional HTML/CSS templates for the final PDF output.
*   **PDF Generation:** Renders the structured CV data into a chosen template, producing a high-quality PDF file.
*   **Minimalist Interface:** Focuses on a clean and intuitive user experience within the Telegram chat interface.
*   **State Management:** Remembers user progress during the multi-step creation process (using Redis or file-based persistence).

## Technology Stack

*   **Language:** Python 3.9+
*   **Bot Framework:** `python-telegram-bot`
*   **AI Integration:** `google-generativeai` (Google Gemini API)
*   **PDF Generation:** `WeasyPrint` (HTML/CSS to PDF rendering)
*   **Templating:** `Jinja2`
*   **Data Validation:** `Pydantic`
*   **Environment Variables:** `python-dotenv`
*   **State Persistence:** `Redis` (recommended) or `PicklePersistence` (file-based fallback)
*   **(Optional) Service Runner:** `Docker` (for easily running Redis)

## Prerequisites

Before you begin, ensure you have the following installed:

1.  **Python:** Version 3.9 or higher. ([Download Python](https://www.python.org/downloads/))
2.  **pip:** Python package installer (usually comes with Python).
3.  **Git:** (Optional, for cloning the repository).
4.  **API Keys:**
    *   **Telegram Bot Token:** Obtainable from [@BotFather](https://t.me/BotFather) on Telegram.
    *   **Google Gemini API Key:** Obtainable from [Google AI Studio](https://aistudio.google.com/app/apikey).
5.  **WeasyPrint System Dependencies:** This is crucial! `pip install WeasyPrint` is not enough. WeasyPrint relies on external C libraries (Pango, Cairo, GDK-PixBuf, Fontconfig).
    *   **Windows:** The recommended way is to install [MSYS2](https://www.msys2.org/) and then use its `pacman` package manager in the **MSYS2 MINGW64 terminal** to install the required libraries:
        ```bash
        # Update MSYS2 first (run twice if prompted to close)
        pacman -Syu
        pacman -Su
        # Install dependencies
        pacman -S mingw-w64-x86_64-pango mingw-w64-x86_64-cairo mingw-w64-x86_64-gdk-pixbuf2 mingw-w64-x86_64-fontconfig
        ```
        **IMPORTANT:** After installing via MSYS2, you MUST add the MSYS2 MINGW64 bin directory (e.g., `C:\msys64\mingw64\bin`) to your Windows System PATH environment variable and **restart VS Code or your terminal**.
    *   **macOS:** Use Homebrew: `brew install pango gdk-pixbuf libffi cairo`
    *   **Linux (Debian/Ubuntu):** `sudo apt update && sudo apt install python3-pip python3-venv python3-cffi libpango-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info`
    *   Refer to the official [WeasyPrint Installation Guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation) for details specific to your OS.
6.  **(Optional) Docker Desktop:** If you want to use Redis for state persistence via Docker. ([Download Docker Desktop](https://www.docker.com/products/docker-desktop/))

## Setup Instructions

1.  **Clone the Repository (or Download Files):**
    ```bash
    git clone https://github.com/ioa2205/CVBuilder.git
    cd cvbuilder-telegram-bot
    ```
    Or download the ZIP and extract it.

2.  **Install WeasyPrint System Dependencies:** Make sure you have completed this step from the "Prerequisites" section above for your operating system.

3.  **Create a Python Virtual Environment:**
    ```bash
    python -m venv .venv
    ```
    (Use `python3` if `python` doesn't work)

4.  **Activate the Virtual Environment:**
    *   **Windows (PowerShell):** `.\.venv\Scripts\Activate.ps1`
    *   **Windows (Git Bash / CMD):** `.\.venv\Scripts\activate`
    *   **macOS / Linux:** `source .venv/bin/activate`
    (You should see `(.venv)` at the start of your terminal prompt)

5.  **Install Python Requirements:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

1.  **Create `.env` File:** Copy the example file or create a new file named `.env` in the project root directory.
    ```bash
    # Example: Copy on Linux/macOS/Git Bash
    cp .env.example .env
    # Or just create the file manually
    ```

2.  **Edit `.env` File:** Add your API keys and configure Redis settings (if using):
    ```dotenv
    TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN_HERE
    GEMINI_API_KEY=YOUR_GEMINI_API_KEY_HERE

    # Optional: Redis configuration (defaults shown)
    # If Redis is not available, the bot will fall back to file-based persistence.
    REDIS_HOST=localhost
    REDIS_PORT=6379
    REDIS_DB=0
    ```
    *   Replace the placeholder values with your actual keys.
    *   **IMPORTANT:** Do **NOT** commit your `.env` file to version control. The `.gitignore` file should prevent this.

## Running the Bot

1.  **(Optional) Start Redis:** If you want to use Redis for state persistence and have Docker installed:
    ```bash
    docker run -d -p 6379:6379 --name cvbuilder-redis redis:alpine
    ```
    You only need to do this once. You can start/stop the container later using `docker start cvbuilder-redis` / `docker stop cvbuilder-redis`. If Redis isn't running, the bot will use a local file (`bot_persistence.pkl`) instead.

2.  **Activate Virtual Environment:** (If not already active)
    *   Windows: `.\.venv\Scripts\Activate.ps1`
    *   macOS/Linux: `source .venv/bin/activate`

3.  **Run the Main Script:**
    ```bash
    python main.py
    ```

4.  **Stop the Bot:** Press `Ctrl + C` in the terminal where the script is running.

## Usage

1.  Open Telegram and find your bot (using the username you gave it in BotFather).
2.  Send the `/start` command.
3.  Follow the instructions and use the inline buttons to choose your desired action (Create from Scratch / Upload Existing).
4.  Answer the questions or upload your file.
5.  Review the extracted/entered data.
6.  Select a template.
7.  Receive your generated PDF CV!

## Customization

*   **Templates:** The visual appearance of the generated PDFs is controlled by the HTML and CSS files in the `templates/` directory (`template_1.html`, `template_2.html`, `template_3.html`). You can modify these files to change the layout, fonts, colors, and overall style. Ensure the Jinja2 template variables (e.g., `{{ cv.contact_info.full_name }}`) remain intact.
*   **Prompts:** Bot messages and questions can be modified in `flows.py` and `handlers.py`.
*   **Parsing Logic:** The Gemini API prompt for parsing CVs is located in `gemini_service.py` (`get_parsing_prompt` function). You can adjust this prompt to improve parsing accuracy or tailor it to specific CV formats.

## Folder Structure (Key Files)

cvbuilder-telegram-bot/
├── .env                  # Local environment variables (e.g., API keys, bot tokens) — NEVER commit this file
├── .gitignore             # Specifies files and directories Git should ignore (e.g., .env, __pycache__)
├── requirements.txt       # Python package dependencies with pinned versions
├── main.py                # Main entry point: initializes the bot, sets up dispatcher and polling
├── config.py              # Centralized configuration: environment loading, constants, templates, section mappings
├── handlers.py            # Telegram handlers: commands (/start, /help), message responses, button callbacks
├── flows.py               # Business logic: CV creation flows (create from scratch, upload existing CV)
├── gemini_service.py      # Service layer for Google Gemini API: prompt construction, response parsing
├── pdf_service.py         # Service layer for PDF generation: renders HTML templates with Jinja2 + WeasyPrint
├── utils.py               # Utility functions: inline keyboards, text cleaning, temporary file management
├── schemas.py             # Pydantic models: strict data validation and serialization of user CV data
└── templates/             # HTML/CSS templates for generating beautiful, customizable CVs
    ├── template_1.html    # Modern Minimalist Design (Single-column layout)
    ├── template_2.html    # Classic Professional Design (Traditional resume style)
    └── template_3.html    # Clean Two-Column Design (Balanced, space-efficient)

## License

The [MIT License](https://opensource.org/licenses/MIT) is a common and permissive choice for open-source projects.
