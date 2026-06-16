"""
keep_awake.py
=============
Keeps the Streamlit Community Cloud app from going to sleep.

Community Cloud puts an app to sleep after ~12 hours with no visitors. This
script loads the app in a headless browser; if it finds the "sleeping" page, it
clicks the wake button and waits for the app to boot. Run it on a schedule
(every 8 hours) via .github/workflows/keep-awake.yml so the page is always up.

Set your app URL either by editing APP_URL below, or via the STREAMLIT_APP_URL
environment variable (the workflow passes it in).
"""

import os
import sys

from playwright.sync_api import sync_playwright

# 👇 Paste your Streamlit app URL here (or set STREAMLIT_APP_URL in the workflow).
APP_URL = "https://x-daily-feed-9ugaabtyjzevvcwajenuxk.streamlit.app/"  # e.g. "https://your-app.streamlit.app"

URL = os.getenv("STREAMLIT_APP_URL") or APP_URL

# Text on the button shown when an app is asleep.
WAKE_TEXT = "get this app back up"


def main() -> None:
    if not URL or "PASTE_YOUR_STREAMLIT_URL_HERE" in URL:
        sys.exit(
            "ERROR: No app URL set. Edit APP_URL in keep_awake.py or set the "
            "STREAMLIT_APP_URL repository variable."
        )

    print(f"Visiting {URL} ...")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(URL, timeout=60_000, wait_until="domcontentloaded")
        page.wait_for_timeout(6_000)  # let the page settle

        # If the app is asleep, click the wake button.
        try:
            button = page.get_by_text(WAKE_TEXT, exact=False)
            if button.count() > 0:
                print("App was asleep — clicking the wake button.")
                button.first.click()
                # Booting can take ~30-60s; give it time.
                page.wait_for_timeout(60_000)
                print("Wake request sent.")
            else:
                print("App is already awake.")
        except Exception as e:  # noqa: BLE001
            # Never fail the job just because the wake check hiccuped; the visit
            # itself still counts as traffic.
            print(f"Wake-check note (non-fatal): {e}")

        browser.close()
    print("Done.")


if __name__ == "__main__":
    main()
