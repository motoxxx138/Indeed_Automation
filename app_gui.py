import os
import sys
import threading
import webbrowser
import time
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_file

import config
from database import get_connection, update_job_status, get_job_by_id, update_job_tailored
from indeed_scraper import run_scraper
from tailor_processor import process_pending_resumes
from resume_tailor import tailor_resume_for_job
from indeed_applier import run_applier
from playwright.sync_api import sync_playwright
from browser_manager import launch_sync_context

app = Flask(__name__)

# State for background tasks
task_lock = threading.Lock()
task_state = {
    "running": False,
    "current_task": "Idle",
    "error": None
}

def set_task(running: bool, name: str = "Idle", err: str = None):
    with task_lock:
        task_state["running"] = running
        task_state["current_task"] = name
        task_state["error"] = err

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/jobs", methods=["GET"])
def get_jobs():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, job_key, title, company, location, salary, job_url, 
               job_description, is_easy_apply, status, tailored_resume_path, 
               tailored_summary, tailor_notes, created_at, applied_at
        FROM jobs
        ORDER BY id DESC
    """)
    jobs = [dict(row) for row in cursor.fetchall()]

    # Real-time disk verification: check if each tailored resume file exists
    missing_count = 0
    new_count = 0
    ready_count = 0

    for j in jobs:
        path_str = j.get("tailored_resume_path")
        file_exists = bool(path_str and Path(path_str).exists())
        j["resume_exists"] = file_exists

        if j["status"] == "tailored":
            if not file_exists:
                j["file_missing"] = True
                missing_count += 1
            else:
                j["file_missing"] = False
                ready_count += 1
        elif j["status"] == "new":
            new_count += 1
            j["file_missing"] = False
        else:
            j["file_missing"] = False

    cursor.execute("SELECT status, count(*) FROM jobs GROUP BY status")
    counts = dict(cursor.fetchall())
    conn.close()

    stats = {
        "total": len(jobs),
        "new": new_count,
        "tailored": ready_count,
        "missing": missing_count,
        "applied": counts.get("applied", 0),
        "skipped": counts.get("skipped", 0)
    }

    return jsonify({"jobs": jobs, "stats": stats, "missing_count": missing_count})

@app.route("/api/task_status", methods=["GET"])
def get_task_status():
    with task_lock:
        return jsonify(task_state)

@app.route("/api/scan", methods=["POST"])
def api_scan():
    if task_state["running"]:
        return jsonify({"status": "busy", "message": "Another task is already in progress."}), 400

    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip() or config.JOB_SEARCH_QUERY
    location = (data.get("location") or "").strip() or config.JOB_LOCATION
    clear_existing = bool(data.get("clear_existing", False))
    visible = bool(data.get("visible", False))

    # Update in-memory config
    config.JOB_SEARCH_QUERY = query
    config.JOB_LOCATION = location

    def worker():
        mode_text = " (Visible Browser)" if visible else ""
        if clear_existing:
            from database import clear_all_jobs
            clear_all_jobs()
            set_task(True, f"Cleared previous jobs. Scanning Indeed{mode_text} for '{query}' in '{location}'...")
        else:
            set_task(True, f"Scanning Indeed{mode_text} for '{query}' in '{location}'...")

        try:
            run_scraper(query=query, location=location, max_jobs=15, headless=not visible)
            set_task(False, "Scan completed.")
        except Exception as e:
            set_task(False, "Scan failed", str(e))

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"status": "started", "message": f"Scanning for '{query}' in '{location}'."})

@app.route("/api/open_search_browser", methods=["POST"])
def api_open_search_browser():
    """Opens visible browser directly to Indeed search so user can complete any Cloudflare challenge."""
    import urllib.parse
    data = request.get_json(silent=True) or {}
    q = urllib.parse.quote_plus((data.get("query") or config.JOB_SEARCH_QUERY).strip())
    l = urllib.parse.quote_plus((data.get("location") or config.JOB_LOCATION).strip())
    search_url = f"https://www.indeed.com/jobs?q={q}&l={l}"

    def worker():
        b_name = config.BROWSER_TYPE.capitalize()
        set_task(True, f"Opening {b_name} for Indeed security check...")
        try:
            with sync_playwright() as p:
                context = launch_sync_context(p, headless=False)
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(search_url)
                while len(context.pages) > 0:
                    try:
                        time.sleep(1)
                        if not context.pages:
                            break
                    except Exception:
                        break
        except Exception as e:
            print("Search browser error:", e)
        finally:
            set_task(False, "Verification window closed. Clearance saved to profile.")

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"status": "started", "message": "Opening verification browser window."})

@app.route("/api/delete_job/<int:job_id>", methods=["POST"])
def api_delete_job(job_id):
    from database import delete_job
    delete_job(job_id)
    return jsonify({"status": "ok", "message": f"Job #{job_id} deleted."})

@app.route("/api/clear_all_jobs", methods=["POST"])
def api_clear_all_jobs():
    from database import clear_all_jobs
    count = clear_all_jobs()
    return jsonify({"status": "ok", "message": f"Cleared {count} job(s) from database."})

@app.route("/api/tailor_all", methods=["POST"])
def api_tailor_all():
    if task_state["running"]:
        return jsonify({"status": "busy", "message": "Another task is already in progress."}), 400

    data = request.get_json(silent=True) or {}
    include_missing = data.get("include_missing", True)

    def worker():
        try:
            if include_missing:
                from database import mark_missing_resumes_as_new
                restored = mark_missing_resumes_as_new()
                if restored > 0:
                    set_task(True, f"Found {restored} deleted resume(s). Preparing to re-generate...")

            set_task(True, "Tailoring queued resumes with AI...")
            process_pending_resumes(limit=25)
            set_task(False, "Tailoring completed.")
        except Exception as e:
            set_task(False, "Tailoring failed", str(e))

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"status": "started", "message": "Batch tailoring initiated."})

@app.route("/api/regenerate_missing", methods=["POST"])
def api_regenerate_missing():
    if task_state["running"]:
        return jsonify({"status": "busy", "message": "Another task is already in progress."}), 400

    def worker():
        set_task(True, "Checking disk and restoring missing resumes...")
        try:
            from database import mark_missing_resumes_as_new
            restored = mark_missing_resumes_as_new()
            if restored > 0:
                set_task(True, f"Regenerating {restored} missing resume(s) with AI...")
                process_pending_resumes(limit=restored)
                set_task(False, f"Successfully regenerated {restored} resume(s).")
            else:
                set_task(False, "All tailored resumes are already present on disk.")
        except Exception as e:
            set_task(False, "Regeneration failed", str(e))

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"status": "started", "message": "Regenerating missing resumes."})

@app.route("/api/tailor/<int:job_id>", methods=["POST"])
def api_tailor_single(job_id):
    job = get_job_by_id(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    def worker():
        set_task(True, f"Tailoring resume for '{job['title']}'...")
        try:
            result = tailor_resume_for_job(
                job_title=job["title"],
                company=job["company"] or "Company",
                job_description=job["job_description"] or "",
                job_key=job["job_key"]
            )
            update_job_tailored(
                job_id=job_id,
                resume_path=result["file_path"],
                summary=result["summary"],
                notes=f"Match Score: {result['match_score']}% | {result['tailor_notes']}"
            )
            set_task(False, "Resume tailored successfully.")
        except Exception as e:
            set_task(False, "Tailoring failed", str(e))

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"status": "started", "message": f"Tailoring started for job #{job_id}"})

@app.route("/api/apply/<int:job_id>", methods=["POST"])
def api_apply(job_id):
    if task_state["running"]:
        return jsonify({"status": "busy", "message": "Another task is running."}), 400

    def worker():
        set_task(True, f"Running Guided Applier for Job #{job_id}...")
        try:
            run_applier(job_id)
            set_task(False, "Application flow finished.")
        except Exception as e:
            set_task(False, "Application flow error", str(e))

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"status": "started", "message": f"Applier launched for job #{job_id}"})

@app.route("/api/skip/<int:job_id>", methods=["POST"])
def api_skip(job_id):
    update_job_status(job_id, "skipped")
    return jsonify({"status": "ok", "message": f"Job #{job_id} marked as skipped."})

@app.route("/api/open_file/<int:job_id>", methods=["POST"])
def api_open_file(job_id):
    job = get_job_by_id(job_id)
    if not job or not job.get("tailored_resume_path"):
        return jsonify({"error": "not_tailored", "message": "No tailored resume on record for this job."}), 404

    file_path = job["tailored_resume_path"]
    if not Path(file_path).exists():
        return jsonify({
            "error": "file_missing",
            "message": f"Resume '{Path(file_path).name}' was deleted or moved from the output folder.",
            "job_id": job_id,
            "title": job.get("title", "")
        }), 404

    try:
        os.startfile(file_path)
        return jsonify({"status": "ok", "message": f"Opened {Path(file_path).name}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/login", methods=["POST"])
def api_login():
    def worker():
        b_name = config.BROWSER_TYPE.capitalize()
        set_task(True, f"Opening {b_name} for Indeed login...")
        try:
            with sync_playwright() as p:
                context = launch_sync_context(p, headless=False)
                page = context.pages[0] if context.pages else context.new_page()
                page.goto("https://secure.indeed.com/auth")
                # Wait for user to interact or close
                while len(context.pages) > 0:
                    try:
                        time.sleep(1)
                        if not context.pages:
                            break
                    except Exception:
                        break
        except Exception as e:
            print("Login browser closed:", e)
        finally:
            set_task(False, "Login completed.")

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"status": "started", "message": f"Opening {config.BROWSER_TYPE.capitalize()} for Indeed sign-in."})

@app.route("/api/login_default_browser", methods=["POST"])
def api_login_default_browser():
    """Opens system default browser directly to Indeed login."""
    webbrowser.open("https://secure.indeed.com/auth")
    return jsonify({"status": "ok", "message": "Opened default browser."})

@app.route("/api/settings", methods=["GET"])
def get_settings():
    return jsonify({
        "openrouter_api_key": config.OPENROUTER_API_KEY,
        "openrouter_model": config.OPENROUTER_MODEL,
        "browser_type": config.BROWSER_TYPE,
        "job_search_query": config.JOB_SEARCH_QUERY,
        "job_location": config.JOB_LOCATION,
        "user_full_name": config.USER_PROFILE.get("full_name", ""),
        "user_email": config.USER_PROFILE.get("email", ""),
        "user_phone": config.USER_PROFILE.get("phone", ""),
        "user_exp_years": config.USER_PROFILE.get("years_customer_service", 5)
    })

@app.route("/api/settings", methods=["POST"])
def save_settings():
    data = request.get_json(silent=True) or {}
    env_path = config.BASE_DIR / ".env"

    # Update in-memory
    if "openrouter_api_key" in data:
        config.OPENROUTER_API_KEY = data["openrouter_api_key"]
    if "openrouter_model" in data:
        config.OPENROUTER_MODEL = data["openrouter_model"]
    if "browser_type" in data:
        config.BROWSER_TYPE = data["browser_type"].lower().strip()
        config.BROWSER_PROFILE_DIR = config.FIREFOX_PROFILE_DIR if config.BROWSER_TYPE == "firefox" else config.CHROMIUM_PROFILE_DIR
    if "job_search_query" in data:
        config.JOB_SEARCH_QUERY = data["job_search_query"]
    if "job_location" in data:
        config.JOB_LOCATION = data["job_location"]

    prof = config.USER_PROFILE
    if "user_full_name" in data: prof["full_name"] = data["user_full_name"]
    if "user_email" in data: prof["email"] = data["user_email"]
    if "user_phone" in data: prof["phone"] = data["user_phone"]
    if "user_exp_years" in data: prof["years_customer_service"] = int(data["user_exp_years"] or 5)

    # Persist to .env
    content = f"""# OpenRouter API Key
OPENROUTER_API_KEY={config.OPENROUTER_API_KEY}
OPENROUTER_MODEL={config.OPENROUTER_MODEL}
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Browser Selection ('firefox' or 'chromium')
BROWSER_TYPE={config.BROWSER_TYPE}

# Job Search Settings
JOB_SEARCH_QUERY={config.JOB_SEARCH_QUERY}
JOB_LOCATION={config.JOB_LOCATION}
SEARCH_INTERVAL_MINUTES=15

# Profile Information
USER_FULL_NAME={prof.get('full_name', '')}
USER_EMAIL={prof.get('email', '')}
USER_PHONE={prof.get('phone', '')}
USER_CITY={prof.get('city', 'Dallas')}
USER_STATE={prof.get('state', 'TX')}
USER_ZIP={prof.get('zip_code', '75001')}
USER_EXP_YEARS={prof.get('years_customer_service', 5)}
USER_SALARY={prof.get('desired_hourly_salary', 22)}
"""
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(content)

    return jsonify({"status": "ok", "message": "Settings updated successfully."})

def open_browser():
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:5000")

def main():
    print("=" * 65)
    print("      INDEED AUTOMATION DASHBOARD (OPENROUTER AI)")
    print("=" * 65)
    print("Starting local Web GUI at: http://127.0.0.1:5000")
    print("Opening in your default browser automatically...")
    print("Press Ctrl+C in this terminal to stop the application.")
    print("=" * 65)

    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="127.0.0.1", port=5000, debug=False)

if __name__ == "__main__":
    main()
