import os
import sys
import time
from playwright.sync_api import sync_playwright

USERNAME = "riva.adli"
PASSWORD = "adliriva16"
TARGET_URL = "https://fasih-dashboard.bps.go.id/superset/dashboard/ubinan26s/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    print("Navigating...")
    page.goto("https://fasih-dashboard.bps.go.id/", wait_until="networkidle")
    
    try:
        page.locator("button, input[type='button']").filter(has_text="GO").first.click(timeout=5000)
        time.sleep(2)
    except Exception:
        pass

    page.wait_for_load_state("networkidle")
    if "sso.bps.go.id" in page.url or page.locator('input[name="username"]').is_visible():
        page.fill('input[name="username"]', USERNAME)
        page.fill('input[name="password"]', PASSWORD)
        page.click('button[type="submit"], input[type="submit"]')
        page.wait_for_load_state("networkidle")
        time.sleep(5)

    print("Navigating to target...")
    page.goto(TARGET_URL, wait_until="networkidle")
    time.sleep(5)

    print("Clicking RAW tab...")
    page.locator("div[role='tab']:has-text('RAW')").first.click()
    time.sleep(5)

    # Dump the HTML around the card header
    print("Dumping card header controls HTML...")
    try:
        # Find elements containing "Raw Data" and dump their container HTML
        headers = page.locator("div").filter(has_text="Raw Data Ubinan 2026").all()
        print(f"Found {len(headers)} div elements containing 'Raw Data Ubinan 2026'")
        for idx, h in enumerate(headers):
            # Print outer HTML of its parent or itself if it has controls
            parent = h.locator("xpath=..")
            print(f"--- Header {idx} Parent HTML ---")
            print(parent.inner_html()[:2000])
    except Exception as e:
        print(f"Error dumping: {e}")

    browser.close()
