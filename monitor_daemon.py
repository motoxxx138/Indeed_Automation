import time
from datetime import datetime
import config
from indeed_scraper import run_scraper
from tailor_processor import process_pending_resumes
from database import get_pending_review

def notify_user(title: str, message: str):
    """Sends a desktop notification on Windows if available, or prints an alert."""
    print(f"\n[ALERT - {datetime.now().strftime('%H:%M:%S')}] {title}: {message}")
    try:
        # PowerShell notification or beep
        import winsound
        winsound.MessageBeep()
    except Exception:
        pass

def run_monitoring_cycle():
    """Runs a single monitoring & tailoring cycle."""
    active_query = config.JOB_SEARCH_QUERY
    active_loc = config.JOB_LOCATION
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Indeed search cycle...")
    print(f"Query: '{active_query}' | Location: '{active_loc}'")
    
    # 1. Scrape new jobs
    new_jobs = run_scraper(query=active_query, location=active_loc, max_jobs=10)
    print(f"[MONITOR] Found {len(new_jobs)} new matching postings.")

    # 2. Tailor resumes for new jobs
    if new_jobs:
        tailored_count = process_pending_resumes(limit=len(new_jobs))
        if tailored_count > 0:
            notify_user(
                "New Job Matches Found!",
                f"{tailored_count} tailored resumes are generated and waiting for your review in the Dashboard."
            )

    pending = get_pending_review(limit=10)
    print(f"[MONITOR] Total jobs currently awaiting review: {len(pending)}")

def start_daemon(interval_minutes: int = SEARCH_INTERVAL_MINUTES):
    """Starts the continuous background loop."""
    print("=" * 60)
    print(f"INDEED MONITORING DAEMON ACTIVE")
    print(f"Checking Indeed every {interval_minutes} minutes.")
    print("Press Ctrl+C to stop.")
    print("=" * 60)

    try:
        while True:
            run_monitoring_cycle()
            print(f"\n[DAEMON] Sleeping for {interval_minutes} minutes until next scan...")
            time.sleep(interval_minutes * 60)
    except KeyboardInterrupt:
        print("\n[DAEMON] Monitoring daemon stopped.")

if __name__ == "__main__":
    start_daemon()
