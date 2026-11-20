import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# OpenRouter API Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# Search Queries & Filters
JOB_SEARCH_QUERY = os.getenv("JOB_SEARCH_QUERY", "remote customer service")
JOB_LOCATION = os.getenv("JOB_LOCATION", "remote")
SEARCH_INTERVAL_MINUTES = int(os.getenv("SEARCH_INTERVAL_MINUTES", "15"))

# Browser Configuration ('firefox' or 'chromium')
BROWSER_TYPE = os.getenv("BROWSER_TYPE", "firefox")

# Directories
RESUME_INPUT_DIR = BASE_DIR / "input_resume"
RESUME_OUTPUT_DIR = BASE_DIR / "tailored_resumes"
DATA_DIR = BASE_DIR / "data"
FIREFOX_PROFILE_DIR = DATA_DIR / "firefox_profile"
CHROMIUM_PROFILE_DIR = DATA_DIR / "chromium_profile"
BROWSER_PROFILE_DIR = FIREFOX_PROFILE_DIR if BROWSER_TYPE == "firefox" else CHROMIUM_PROFILE_DIR

# Ensure directories exist
RESUME_INPUT_DIR.mkdir(parents=True, exist_ok=True)
RESUME_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
FIREFOX_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
CHROMIUM_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

# Database
DATABASE_PATH = DATA_DIR / "indeed_jobs.db"

# User Profile for Screening Questions
USER_PROFILE = {
    "full_name": os.getenv("USER_FULL_NAME", "Jane Doe"),
    "email": os.getenv("USER_EMAIL", "jane.doe@example.com"),
    "phone": os.getenv("USER_PHONE", "(555) 123-4567"),
    "city": os.getenv("USER_CITY", "Dallas"),
    "state": os.getenv("USER_STATE", "TX"),
    "zip_code": os.getenv("USER_ZIP", "75001"),
    "years_customer_service": int(os.getenv("USER_EXP_YEARS", "5")),
    "desired_hourly_salary": os.getenv("USER_SALARY", "22"),
    "authorized_in_us": True,
    "requires_sponsorship": False,
    "highest_education": "Associate Degree"
}
