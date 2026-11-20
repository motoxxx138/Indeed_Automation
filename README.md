# Indeed Remote Job Monitor & AI Resume Tailorer

An end-to-end automation system that monitors **Indeed** for new job postings matching your query, analyzes the employer's requirements using **OpenRouter AI**, automatically customizes your resume for that exact role into an ATS-friendly `.docx`, and guides you through the semi-automated application submission.

---

## Features

- 🕵️ **Indeed Job Monitor**: Periodically scans Indeed for remote customer service postings, extracts full job descriptions, compensation, and flags "Easily Apply" roles.
- 🤖 **OpenRouter AI Tailor Engine**: Automatically optimizes the Professional Summary, aligns Core Competencies, and adapts Experience bullet points to naturally incorporate the job's vocabulary and keywords (without fabricating credentials or false claims). Choose any model (e.g. `google/gemini-2.5-flash`, `anthropic/claude-3.5-sonnet`, `openai/gpt-4o-mini`, etc.).
- 📄 **ATS-Friendly `.docx` Generation**: Produces a clean, formatted Word document ready to upload to Indeed or ATS portals.
- 🎛️ **Interactive Web GUI & Dashboard**: Clean modern visual dashboard that opens directly in your browser. Live tracking stats, job details preview, 1-click resume opening in Word, and guided application launcher.
- 🚀 **Guided Applier**: Automatically launches a browser session, pre-fills your contact details and screening answers (authorization, years of experience, salary), uploads your tailored resume, and pauses at the final review screen for your 1-click confirmation.
- 🛡️ **Stealth & Persistent Login**: Saves your logged-in Indeed session in `browser_profile/` to avoid repeated logins and anti-bot verification.

---

## Project Structure

```
Indeed_Automation/
├── input_resume/           # Put your base resume here (.docx or .pdf)
│   └── master_resume.docx  # Pre-populated customer service resume template
├── tailored_resumes/       # Generated custom resumes (Resume_<Company>_<JobKey>.docx)
├── browser_profile/        # Saved browser cookies and authenticated Indeed session
├── data/
│   └── indeed_jobs.db      # SQLite database tracking found jobs & application status
├── .env                    # Your OpenRouter API key & screening profile details
├── config.py               # Settings & profile configuration
├── indeed_scraper.py       # Scraper engine
├── resume_parser.py        # Reads .docx / .pdf base resumes
├── resume_tailor.py        # OpenRouter AI tailoring & docx builder
├── tailor_processor.py     # Batch tailoring queue
├── indeed_applier.py       # Semi-automated Indeed Apply automation
├── monitor_daemon.py       # Background scheduler loop
├── dashboard.py            # Interactive management menu
├── main.py                 # Main CLI entrypoint
└── start.bat               # 1-click Windows launcher
```

---

## Quick Start Guide

### 1. Configure Your OpenRouter API Key & Profile
Open the `.env` file in this directory and enter:
```env
# Get your API key from https://openrouter.ai/keys
OPENROUTER_API_KEY=your_actual_openrouter_key_here
OPENROUTER_MODEL=google/gemini-2.5-flash
```
# Your Contact & Screening Details
USER_FULL_NAME=Jane Doe
USER_EMAIL=your.email@example.com
USER_PHONE=555-123-4567
USER_CITY=Dallas
USER_STATE=TX
USER_ZIP=75001
USER_EXP_YEARS=5
USER_SALARY=22
```

### 2. Put Your Master Resume in `input_resume/`
- A sample customer service template `master_resume.docx` is already included in `input_resume/` so you can test right away.
- When ready, simply drop your own base resume (`.docx` or `.pdf`) into `input_resume/`.

### 3. Launch the Interactive Dashboard
Double-click `start.bat` or run:
```powershell
.\.venv\Scripts\python.exe main.py
```

From the dashboard menu:
- Press **`L`**: Opens a browser window where you can log into your Indeed account once. Your login cookies will be saved in `browser_profile/` so you never have to sign in again.
- Press **`R`**: Runs an instant scan for new remote customer service jobs.
- Press **`T`**: Automatically tailors resumes for all newly found jobs using Gemini.
- Press **`V <id>`**: Opens the generated tailored resume in Microsoft Word or your default viewer.
- Press **`A <id>`**: Runs the semi-automated applier (attaches the tailored resume, fills screening inputs, and pauses for your approval).
- Press **`O <id>`**: Opens the job posting in your browser.

---

## Running the Continuous Background Monitor

To have the system constantly watch for new jobs and alert you automatically:
```powershell
.\.venv\Scripts\python.exe main.py --monitor
```
It scans Indeed every 15 minutes (configurable in `.env`), automatically crafts tailored resumes for any matching postings, and emits an alert so you can approve and submit with one click.
