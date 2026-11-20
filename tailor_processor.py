import time
from typing import Optional
from database import get_pending_tailoring, update_job_tailored, update_job_status, get_job_by_id
from resume_tailor import tailor_resume_for_job

def process_pending_resumes(limit: int = 15, job_ids: Optional[list] = None):
    """
    Pulls newly discovered or specified jobs and tailors resumes
    specifically for each job's requirements and language.
    """
    if job_ids:
        jobs = [get_job_by_id(jid) for jid in job_ids]
        jobs = [j for j in jobs if j is not None]
    else:
        jobs = get_pending_tailoring(limit=limit)

    if not jobs:
        print("[TAILOR] No jobs queued for resume tailoring.")
        return 0

    print(f"[TAILOR] Found {len(jobs)} jobs queued for resume tailoring.")
    processed = 0

    for job in jobs:
        job_id = job["id"]
        job_key = job["job_key"]
        title = job["title"]
        company = job["company"] or "Company"
        desc = job["job_description"] or ""

        print(f"\n[TAILOR] Optimizing resume for Job #{job_id}: '{title}' at '{company}'...")
        try:
            result = tailor_resume_for_job(
                job_title=title,
                company=company,
                job_description=desc,
                job_key=job_key
            )

            update_job_tailored(
                job_id=job_id,
                resume_path=result["file_path"],
                summary=result["summary"],
                notes=f"Match Score: {result['match_score']}% | {result['tailor_notes']}"
            )

            print(f"  [SUCCESS] Generated: {result['file_name']}")
            print(f"  [SUMMARY]: {result['summary'][:120]}...")
            print(f"  [NOTES]: {result['tailor_notes'][:120]}...")
            processed += 1
            time.sleep(1)  # courteous delay between LLM calls

        except Exception as e:
            print(f"  [ERROR] Tailoring failed for Job #{job_id}: {e}")
            update_job_status(job_id, "tailor_error")

    print(f"\n[TAILOR] Finished tailoring {processed} resumes. Ready for review.")
    return processed

if __name__ == "__main__":
    process_pending_resumes(limit=3)
