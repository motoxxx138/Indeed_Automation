import argparse
import sys
from dashboard import run_dashboard
from indeed_scraper import run_scraper
from tailor_processor import process_pending_resumes
from monitor_daemon import start_daemon, run_monitoring_cycle
from indeed_applier import run_applier

def main():
    parser = argparse.ArgumentParser(description="Indeed Job Monitor & AI Resume Tailorer")
    parser.add_argument("--gui", action="store_true", help="Launch interactive Web GUI (default)")
    parser.add_argument("--cli", action="store_true", help="Launch terminal interactive dashboard")
    parser.add_argument("--scan", action="store_true", help="Scan Indeed once for new jobs")
    parser.add_argument("--tailor", action="store_true", help="Tailor resumes for pending jobs")
    parser.add_argument("--monitor", action="store_true", help="Start continuous monitoring daemon")
    parser.add_argument("--apply", type=int, help="Apply to a specific job ID (semi-automated)")

    args = parser.parse_args()

    if args.scan:
        run_scraper()
    elif args.tailor:
        process_pending_resumes()
    elif args.monitor:
        start_daemon()
    elif args.apply:
        run_applier(args.apply)
    elif args.cli:
        run_dashboard()
    else:
        # Default action: launch modern Web GUI
        from app_gui import main as run_gui
        run_gui()

if __name__ == "__main__":
    main()
