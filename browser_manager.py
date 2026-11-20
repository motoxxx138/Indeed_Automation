import os
from pathlib import Path
from typing import Optional, Tuple
from config import BROWSER_TYPE, FIREFOX_PROFILE_DIR, CHROMIUM_PROFILE_DIR

def get_browser_settings(browser_type: Optional[str] = None) -> Tuple[str, Path]:
    """Returns the browser engine name ('firefox' or 'chromium') and profile path."""
    b_type = (browser_type or BROWSER_TYPE or "firefox").lower().strip()
    if b_type not in ["firefox", "chromium"]:
        b_type = "firefox"

    if b_type == "firefox":
        profile_dir = FIREFOX_PROFILE_DIR
    else:
        profile_dir = CHROMIUM_PROFILE_DIR

    profile_dir.mkdir(parents=True, exist_ok=True)
    return b_type, profile_dir

async def launch_async_context(
    playwright_instance,
    headless: bool = True,
    browser_type: Optional[str] = None
):
    """Launches async persistent browser context using chosen browser (Firefox or Chromium)."""
    b_type, profile_dir = get_browser_settings(browser_type)

    if b_type == "firefox":
        context = await playwright_instance.firefox.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            viewport={"width": 1280, "height": 800}
        )
    else:
        # Chromium with stealth flags and no automation banner
        context = await playwright_instance.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            ignore_default_args=["--enable-automation"],
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--start-maximized"
            ],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )

    return context

def launch_sync_context(
    playwright_instance,
    headless: bool = False,
    browser_type: Optional[str] = None
):
    """Launches sync persistent browser context using chosen browser (Firefox or Chromium)."""
    b_type, profile_dir = get_browser_settings(browser_type)

    if b_type == "firefox":
        context = playwright_instance.firefox.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            viewport={"width": 1280, "height": 800}
        )
    else:
        context = playwright_instance.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            ignore_default_args=["--enable-automation"],
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )

    return context
