import os
import sys
import subprocess
from pathlib import Path
from database import get_connection, update_job_status, get_job_by_id
from indeed_scraper import run_scraper
from tailor_processor import process_pending_resumes
from indeed_applier import run_applier
from config import BROWSER_PROFILE_DIR

def open_file_or_url(target: str):
    """Opens a file or URL using the Windows default handler."""
    try:
        os.startfile(target)
    except Exception as e:
        print(f"Error opening '{target}': {e}")

def display_menu():
    print("\n" + "=" * 70)
    print("        INDEED REMOTE JOB MONITOR & AI RESUME TAILOR        ")
    print("=" * 70)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, job_key, title, company, salary, is_easy_apply, status, 
               tailored_resume_path, tailor_notes, created_at
        FROM jobs
        ORDER BY id DESC
        LIMIT 25
    """)
    jobs = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if not jobs:
        print("\n  [Database is currently empty. Press 'R' to scan Indeed for jobs.]")
    else:
        print(f"\n {'ID':<4} | {'Status':<10} | {'Company':<20} | {'Job Title':<30} | {'EasyApply'}")
        print("-" * 75)
        for j in jobs:
            st = j['status'].upper()
            comp = (j['company'] or 'Unknown')[:18]
            tit = (j['title'] or 'Unknown')[:28]
            easy = "YES" if j['is_easy_apply'] else "No"
            print(f" #{j['id']:<3} | {st:<10} | {comp:<20} | {tit:<30} | {easy}")

    print("\n" + "-" * 70)
    print("COMMANDS:")
    print("  [R] Scan Indeed for new jobs        [T] Tailor all pending resumes with AI")
    print("  [A <id>] Apply to job (Guided)      [V <id>] View tailored resume (.docx)")
    print("  [O <id>] Open job on Indeed         [S <id>] Skip / archive job")
    print("  [D <id>] View job & tailor details  [L] Log in to Indeed in browser")
    print("  [Q] Quit")
    print("-" * 70)

def handle_login():
    """Launches a visible browser window so the user can log into their Indeed account."""
    print("\n[LOGIN] Opening browser for Indeed login...")
    print("Please log into your Indeed account in the opened window.")
    print("Your session and cookies will be automatically saved in 'browser_profile/'.")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE_DIR),
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://secure.indeed.com/auth")
        input("\nAfter you have logged in, press [Enter] here to close browser and return to menu: ")
        context.close()
    print("[LOGIN] Session saved successfully!")

def view_job_details(job_id: int):
    job = get_job_by_id(job_id)
    if not job:
        print(f"Job #{job_id} not found.")
        return

    print("\n" + "=" * 60)
    print(f"JOB #{job['id']}: {job['title']} at {job['company']}")
    print(f"Status: {job['status']} | Easy Apply: {'Yes' if job['is_easy_apply'] else 'No'}")
    print(f"Location: {job['location']} | Salary: {job.get('salary', 'N/A')}")
    print(f"URL: {job['job_url']}")
    print("-" * 60)
    if job.get("tailor_notes"):
        print(f"TAILOR NOTES / MATCH:\n{job['tailor_notes']}\n")
    if job.get("tailored_summary"):
        print(f"TAILORED SUMMARY:\n{job['tailored_summary']}\n")
    if job.get("tailored_resume_path"):
        print(f"RESUME FILE: {job['tailored_resume_path']}")
    print("=" * 60)
    input("Press [Enter] to return...")

def run_dashboard():
    while True:
        display_menu()
        cmd = input("\nEnter command: ").strip().lower()

        if not cmd:
            continue

        if cmd == "q" or cmd == "exit":
            print("Exiting Indeed Automation. Happy job hunting!")
            break

        elif cmd == "r":
            print("\n[SCAN] Running Indeed scraper...")
            run_scraper(max_jobs=10)
            input("Press [Enter] to continue...")

        elif cmd == "t":
            print("\n[TAILOR] Processing all pending resumes...")
            process_pending_resumes(limit=10)
            input("Press [Enter] to continue...")

        elif cmd == "l":
            handle_login()

        elif cmd.startswith("a "):
            try:
                jid = int(cmd.split()[1])
                run_applier(jid)
                input("Press [Enter] to continue...")
            except (IndexError, ValueError):
                print("Usage: a <job_id> (e.g. 'a 1')")

        elif cmd.startswith("v "):
            try:
                jid = int(cmd.split()[1])
                job = get_job_by_id(jid)
                if job and job.get("tailored_resume_path"):
                    open_file_or_url(job["tailored_resume_path"])
                else:
                    print(f"No tailored resume generated yet for Job #{jid}. Run 'T' first.")
            except (IndexError, ValueError):
                print("Usage: v <job_id> (e.g. 'v 1')")

        elif cmd.startswith("o "):
            try:
                jid = int(cmd.split()[1])
                job = get_job_by_id(jid)
                if job and job.get("job_url"):
                    open_file_or_url(job["job_url"])
                else:
                    print(f"Job #{jid} URL not found.")
            except (IndexError, ValueError):
                print("Usage: o <job_id>")

        elif cmd.startswith("d "):
            try:
                jid = int(cmd.split()[1])
                view_job_details(jid)
            except (IndexError, ValueError):
                print("Usage: d <job_id>")

        elif cmd.startswith("s "):
            try:
                jid = int(cmd.split()[1])
                update_job_status(jid, "skipped")
                print(f"Job #{jid} marked as skipped.")
            except (IndexError, ValueError):
                print("Usage: s <job_id>")
        else:
            print("Unknown command. Please choose from the menu options.")

if __name__ == "__main__":
    run_dashboard()
