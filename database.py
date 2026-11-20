import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from config import DATABASE_PATH

def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_key TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            company TEXT,
            location TEXT,
            salary TEXT,
            job_url TEXT NOT NULL,
            job_description TEXT,
            is_easy_apply INTEGER DEFAULT 0,
            status TEXT DEFAULT 'new',
            tailored_resume_path TEXT,
            tailored_summary TEXT,
            tailor_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            applied_at TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_job(
    job_key: str,
    title: str,
    company: str,
    location: str,
    salary: str,
    job_url: str,
    job_description: str,
    is_easy_apply: bool
) -> bool:
    """Save a job posting if not already tracked. Returns True if newly added, False if duplicate."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO jobs (job_key, title, company, location, salary, job_url, job_description, is_easy_apply, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new')
        ''', (job_key, title, company, location, salary, job_url, job_description, 1 if is_easy_apply else 0))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_pending_tailoring(limit: int = 10, include_missing: bool = True) -> List[Dict[str, Any]]:
    """Retrieve jobs marked as 'new' or 'missing_resume' to be tailored."""
    conn = get_connection()
    cursor = conn.cursor()
    if include_missing:
        cursor.execute('''
            SELECT * FROM jobs WHERE status IN ('new', 'missing_resume') ORDER BY id ASC LIMIT ?
        ''', (limit,))
    else:
        cursor.execute('''
            SELECT * FROM jobs WHERE status = 'new' ORDER BY id ASC LIMIT ?
        ''', (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def check_and_sync_missing_resumes() -> List[Dict[str, Any]]:
    """Checks all jobs with status 'tailored' and verifies if the file exists on disk.
    Returns the list of jobs whose tailored resume file is missing."""
    from pathlib import Path
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE status = 'tailored'")
    jobs = [dict(r) for r in cursor.fetchall()]
    missing = []
    for j in jobs:
        path_str = j.get("tailored_resume_path")
        if not path_str or not Path(path_str).exists():
            missing.append(j)
    conn.close()
    return missing

def mark_missing_resumes_as_new(job_ids: Optional[List[int]] = None) -> int:
    """Resets missing resumes to 'new' status so they can be regenerated."""
    from pathlib import Path
    conn = get_connection()
    cursor = conn.cursor()
    if job_ids:
        placeholders = ",".join("?" for _ in job_ids)
        cursor.execute(f"UPDATE jobs SET status = 'new' WHERE id IN ({placeholders})", job_ids)
        updated = cursor.rowcount
    else:
        cursor.execute("SELECT id, tailored_resume_path FROM jobs WHERE status = 'tailored'")
        rows = cursor.fetchall()
        to_reset = []
        for r in rows:
            path_str = r[1]
            if not path_str or not Path(path_str).exists():
                to_reset.append(r[0])
        if to_reset:
            placeholders = ",".join("?" for _ in to_reset)
            cursor.execute(f"UPDATE jobs SET status = 'new' WHERE id IN ({placeholders})", to_reset)
            updated = len(to_reset)
        else:
            updated = 0
    conn.commit()
    conn.close()
    return updated

def get_pending_review(limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieve jobs with tailored resumes awaiting human review/approval."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM jobs WHERE status = 'tailored' ORDER BY id DESC LIMIT ?
    ''', (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def update_job_tailored(job_id: int, resume_path: str, summary: str, notes: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE jobs
        SET status = 'tailored',
            tailored_resume_path = ?,
            tailored_summary = ?,
            tailor_notes = ?,
            updated_at = ?
        WHERE id = ?
    ''', (resume_path, summary, notes, datetime.now().isoformat(), job_id))
    conn.commit()
    conn.close()

def update_job_status(job_id: int, status: str, applied: bool = False):
    conn = get_connection()
    cursor = conn.cursor()
    applied_time = datetime.now().isoformat() if applied else None
    if applied:
        cursor.execute('''
            UPDATE jobs
            SET status = ?, applied_at = ?, updated_at = ?
            WHERE id = ?
        ''', (status, applied_time, datetime.now().isoformat(), job_id))
    else:
        cursor.execute('''
            UPDATE jobs
            SET status = ?, updated_at = ?
            WHERE id = ?
        ''', (status, datetime.now().isoformat(), job_id))
    conn.commit()
    conn.close()

def get_job_by_id(job_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM jobs WHERE id = ?', (job_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_job(job_id: int) -> bool:
    """Deletes a single job from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM jobs WHERE id = ?', (job_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def clear_all_jobs() -> int:
    """Deletes all jobs from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM jobs')
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count

# Initialize on import
init_db()
