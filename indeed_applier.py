import asyncio
import os
from pathlib import Path
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright, Page

from config import USER_PROFILE, BROWSER_TYPE
from database import update_job_status, get_job_by_id
from browser_manager import launch_async_context

async def apply_to_job(
    job_id: int,
    auto_submit: bool = False
) -> bool:
    """
    Automates the application flow on Indeed for a specific job:
    1. Opens browser with user's persistent profile.
    2. Navigates to the job posting.
    3. Clicks 'Easily Apply'.
    4. Enters contact details from USER_PROFILE.
    5. Uploads the tailored resume file.
    6. Fills common screening questions (authorization, experience, salary).
    7. In semi-automated mode: pauses at the review screen for user inspection.
    """
    job = get_job_by_id(job_id)
    if not job:
        print(f"[APPLIER] Error: Job #{job_id} not found in database.")
        return False

    resume_path = job.get("tailored_resume_path")
    if not resume_path or not Path(resume_path).exists():
        print(f"[APPLIER] Error: Tailored resume not found at '{resume_path}'. Run tailor first.")
        return False

    job_url = job.get("job_url") or f"https://www.indeed.com/viewjob?jk={job['job_key']}"
    title = job.get("title", "")
    company = job.get("company", "")

    print(f"\n=======================================================")
    print(f"[APPLIER] Starting application for:")
    print(f"Role: {title}")
    print(f"Company: {company}")
    print(f"Resume: {Path(resume_path).name}")
    print(f"URL: {job_url}")
    print(f"=======================================================\n")

    async with async_playwright() as p:
        # Launch headed browser (Firefox or Chromium) so user can see and verify in semi-automated mode
        context = await launch_async_context(p, headless=False)
        page = context.pages[0] if context.pages else await context.new_page()

        try:
            print("[APPLIER] Navigating to job posting...")
            await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2500)

            # Look for Indeed Apply button
            apply_btn = await page.query_selector(
                "#indeedApplyButton, button[data-testid='indeedApplyButton'], button:has-text('Apply now'), button:has-text('Easily apply')"
            )

            if not apply_btn:
                print("[APPLIER] 'Easily Apply' button not found on page. This may be an external company ATS.")
                print(f"[APPLIER] Please inspect the open browser window to apply manually. URL: {page.url}")
                input("Press [Enter] after you are done reviewing or applying...")
                return False

            print("[APPLIER] Clicking 'Apply now / Easily apply'...")
            await apply_btn.click()
            await page.wait_for_timeout(3000)

            # Some Indeed apply flows open in a popup or iframe
            active_page = page
            if len(context.pages) > 1:
                active_page = context.pages[-1]

            # Loop through application modal steps
            step = 1
            max_steps = 8
            submitted = False

            while step <= max_steps:
                print(f"[APPLIER] Processing application step #{step}...")
                await active_page.wait_for_timeout(1500)

                # Check if file upload input is present on current step
                file_input = await active_page.query_selector("input[type='file']")
                if file_input:
                    print(f"[APPLIER] Uploading tailored resume: {Path(resume_path).name}")
                    await file_input.set_input_files(str(resume_path))
                    await active_page.wait_for_timeout(2000)

                # Fill standard inputs if empty
                inputs = await active_page.query_selector_all("input[type='text'], input[type='tel'], input[type='email']")
                for inp in inputs:
                    name_attr = (await inp.get_attribute("name") or "").lower()
                    id_attr = (await inp.get_attribute("id") or "").lower()
                    val = await inp.input_value()

                    if not val:
                        if "name" in name_attr or "name" in id_attr:
                            await inp.fill(USER_PROFILE.get("full_name", ""))
                        elif "email" in name_attr or "email" in id_attr:
                            await inp.fill(USER_PROFILE.get("email", ""))
                        elif "phone" in name_attr or "phone" in id_attr or "tel" in id_attr:
                            await inp.fill(USER_PROFILE.get("phone", ""))
                        elif "city" in name_attr or "city" in id_attr or "location" in id_attr:
                            await inp.fill(f"{USER_PROFILE.get('city', '')}, {USER_PROFILE.get('state', '')}")

                # Answer common screening radio questions
                radios = await active_page.query_selector_all("fieldset, div[role='radiogroup']")
                for rg in radios:
                    text = (await rg.inner_text()).lower()
                    if "authorized to work" in text or "legally authorized" in text:
                        # Select Yes
                        yes_opt = await rg.query_selector("label:has-text('Yes'), input[value*='yes' i]")
                        if yes_opt:
                            await yes_opt.click()
                    elif "sponsorship" in text or "visa" in text:
                        # Select No
                        no_opt = await rg.query_selector("label:has-text('No'), input[value*='no' i]")
                        if no_opt:
                            await no_opt.click()

                # Handle numeric experience fields
                num_inputs = await active_page.query_selector_all("input[type='number']")
                for num_inp in num_inputs:
                    val = await num_inp.input_value()
                    if not val:
                        await num_inp.fill(str(USER_PROFILE.get("years_customer_service", 5)))

                # Check for final "Submit your application" or "Review" button
                submit_btn = await active_page.query_selector(
                    "button:has-text('Submit your application'), button[aria-label*='Submit your application']"
                )

                review_btn = await active_page.query_selector(
                    "button:has-text('Review your application'), button:has-text('Review')"
                )

                next_btn = await active_page.query_selector(
                    "button:has-text('Continue'), button:has-text('Next'), button[aria-label*='Continue']"
                )

                if submit_btn or review_btn:
                    print("\n" + "=" * 60)
                    print("[SEMI-AUTOMATED APPROVAL REQUIRED]")
                    print("The application has been prepared and filled with your tailored resume!")
                    print("Please check the browser window to review all fields.")
                    print("=" * 60)

                    user_choice = input("\nSubmit application now? (y = Submit / s = Skip / manual submit in browser): ").strip().lower()

                    if user_choice == "y" or user_choice == "yes":
                        if review_btn:
                            await review_btn.click()
                            await active_page.wait_for_timeout(2000)
                            submit_btn = await active_page.query_selector("button:has-text('Submit your application')")

                        if submit_btn:
                            print("[APPLIER] Submitting application...")
                            await submit_btn.click()
                            await active_page.wait_for_timeout(4000)
                            submitted = True
                            update_job_status(job_id, "applied", applied=True)
                            print("[APPLIER] Application submitted successfully!")
                            break
                    else:
                        print("[APPLIER] Application skipped by user.")
                        update_job_status(job_id, "skipped")
                        break

                elif next_btn:
                    await next_btn.click()
                    await active_page.wait_for_timeout(2000)
                    step += 1
                else:
                    print("[APPLIER] No next or submit button recognized. You can finish in the browser.")
                    input("Press [Enter] when done...")
                    break

        except Exception as e:
            print(f"[APPLIER] Error during application: {e}")
            update_job_status(job_id, "apply_error")
        finally:
            await context.close()

    return submitted

def run_applier(job_id: int):
    """Synchronous runner."""
    return asyncio.run(apply_to_job(job_id))

if __name__ == "__main__":
    import sys
    jid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    run_applier(jid)
