import asyncio
import json
import urllib.parse
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright, Page, Response

import config
from database import save_job, get_connection
from browser_manager import launch_async_context

async def scrape_indeed_jobs(
    query: Optional[str] = None,
    location: Optional[str] = None,
    max_jobs: int = 15,
    headless: bool = True
) -> List[Dict[str, Any]]:
    """
    Searches Indeed for jobs matching query and location.
    Extracts full structured descriptions and saves new jobs to the database.
    """
    active_query = query if query is not None else config.JOB_SEARCH_QUERY
    active_location = location if location is not None else config.JOB_LOCATION

    new_jobs_found = []
    
    encoded_query = urllib.parse.quote_plus(active_query)
    encoded_loc = urllib.parse.quote_plus(active_location)
    search_url = f"https://www.indeed.com/jobs?q={encoded_query}&l={encoded_loc}"

    async with async_playwright() as p:
        context = await launch_async_context(p, headless=headless)
        page = context.pages[0] if context.pages else await context.new_page()

        # Map to store captured GraphQL viewjob payloads by jobKey
        captured_jobs: Dict[str, Dict[str, Any]] = {}

        async def on_response(response: Response):
            if "graphql" in response.url:
                try:
                    payload = await response.json()
                    items = payload if isinstance(payload, list) else [payload]
                    for item in items:
                        if isinstance(item, dict) and "data" in item:
                            vj = item["data"].get("viewjob")
                            if vj and isinstance(vj, dict):
                                job_data = vj.get("job", {})
                                jk = vj.get("key") or job_data.get("key")
                                if jk:
                                    captured_jobs[jk] = job_data
                except Exception:
                    pass

        page.on("response", on_response)

        print(f"[SCRAPER] Navigating to Indeed search: {search_url}")
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=25000)
            await page.wait_for_timeout(2500)
        except Exception as e:
            print(f"[SCRAPER] Failed to load search page: {e}")
            await context.close()
            return []

        # Find job cards
        cards = await page.query_selector_all("div.job_seen_beacon")
        print(f"[SCRAPER] Found {len(cards)} job cards on current search page.")

        # Check existing jobs in database to avoid unnecessary clicks
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT job_key FROM jobs")
        existing_keys = {row[0] for row in cursor.fetchall()}
        conn.close()

        for idx, card in enumerate(cards[:max_jobs]):
            try:
                link_el = await card.query_selector("a[data-jk], a.jcs-JobTitle")
                if not link_el:
                    continue

                jk = await link_el.get_attribute("data-jk")
                if not jk:
                    href = await link_el.get_attribute("href") or ""
                    if "jk=" in href:
                        jk = href.split("jk=")[1].split("&")[0]

                if not jk or jk in existing_keys:
                    continue  # Already processed

                # Get title & company from card as baseline
                title_el = await card.query_selector("h2.jobTitle, a.jcs-JobTitle")
                title = (await title_el.inner_text()).strip() if title_el else "Unknown Title"

                comp_el = await card.query_selector("[data-testid='company-name']")
                company = (await comp_el.inner_text()).strip() if comp_el else "Unknown Company"

                card_text = await card.inner_text()
                is_easy = "Easily apply" in card_text or "Easily Apply" in card_text

                print(f"[SCRAPER] Found new job [{jk}]: {title} at {company} (EasyApply: {is_easy})")

                # Click the card to trigger GraphQL description load
                await link_el.click()
                await page.wait_for_timeout(2000)

                # Check if we captured description from GraphQL
                full_description = ""
                salary = ""
                location_text = location

                if jk in captured_jobs:
                    j_info = captured_jobs[jk]
                    desc_obj = j_info.get("description", {})
                    full_description = desc_obj.get("text", "") if isinstance(desc_obj, dict) else str(desc_obj)
                    if j_info.get("title"):
                        title = j_info.get("title")
                    if j_info.get("sourceEmployerName"):
                        company = j_info.get("sourceEmployerName")
                    
                    loc_info = j_info.get("location", {})
                    if isinstance(loc_info, dict):
                        location_text = loc_info.get("formattedLocation", location)

                    comp_info = j_info.get("compensation", {})
                    if isinstance(comp_info, dict) and comp_info.get("text"):
                        salary = comp_info.get("text")
                    
                    if "indeedApply" in j_info and j_info["indeedApply"]:
                        is_easy = True

                # If GraphQL didn't fire, try reading from DOM pane
                if not full_description:
                    pane = await page.query_selector("#jobDescriptionText")
                    if pane:
                        full_description = await pane.inner_text()

                job_url = f"https://www.indeed.com/viewjob?jk={jk}"
                
                # Save into database
                saved = save_job(
                    job_key=jk,
                    title=title,
                    company=company,
                    location=location_text,
                    salary=salary,
                    job_url=job_url,
                    job_description=full_description or card_text,
                    is_easy_apply=is_easy
                )

                if saved:
                    new_jobs_found.append({
                        "job_key": jk,
                        "title": title,
                        "company": company,
                        "location": location_text,
                        "salary": salary,
                        "job_url": job_url,
                        "is_easy_apply": is_easy,
                        "description_length": len(full_description)
                    })
                    existing_keys.add(jk)

            except Exception as card_err:
                print(f"[SCRAPER] Error inspecting card {idx}: {card_err}")
                continue

        await context.close()

    print(f"[SCRAPER] Completed scan. {len(new_jobs_found)} new jobs stored in database.")
    return new_jobs_found

def run_scraper(query: Optional[str] = None, location: Optional[str] = None, max_jobs: int = 15):
    """Synchronous wrapper for scrape_indeed_jobs."""
    active_query = query if query is not None else config.JOB_SEARCH_QUERY
    active_location = location if location is not None else config.JOB_LOCATION
    return asyncio.run(scrape_indeed_jobs(active_query, active_location, max_jobs))

if __name__ == "__main__":
    jobs = run_scraper()
    for j in jobs:
        print(f" -> {j['title']} @ {j['company']} (EasyApply: {j['is_easy_apply']}, Desc len: {j['description_length']})")
