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
    page.goto("https://fasih-dashboard.bps.go.id/", wait_until="load")
    
    try:
        page.locator("button, input[type='button']").filter(has_text="GO").first.click(timeout=5000)
        time.sleep(2)
    except Exception:
        pass

    page.wait_for_load_state("load")
    if "sso.bps.go.id" in page.url or page.locator('input[name="username"]').is_visible():
        page.fill('input[name="username"]', USERNAME)
        page.fill('input[name="password"]', PASSWORD)
        page.click('button[type="submit"], input[type="submit"]')
        time.sleep(5)

    print("Navigating to target...")
    page.goto(TARGET_URL, wait_until="load")
    time.sleep(10) # wait extra 10s for sidebar filters to load

    print("Clicking RAW tab...")
    page.locator("div[role='tab']:has-text('RAW')").first.click()
    time.sleep(5)

    print("Dumping filter-bar HTML...")
    try:
        fb = page.locator("[data-test='filter-bar']").first
        print(fb.inner_html()[:8000])
    except Exception as e:
        print(f"Error: {e}")

    browser.close()
