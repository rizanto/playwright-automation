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

    selectors = [
        "xpath=//div[contains(@data-test-chart-name, 'data.tab')]//span[@aria-label='More Options']",
        "xpath=//div[contains(@class, 'chart-slice') and .//span[contains(., 'Raw Data Ubinan')]]//span[@aria-label='More Options']",
        "xpath=//div[contains(@class, 'chart-slice') and .//span[contains(., 'Raw Data Ubinan')]]//*[contains(@class, 'anticon-ellipsis') or @aria-label='More Options']",
        "xpath=//div[@data-test-chart-id='9868']//span[@aria-label='More Options']"
    ]

    for idx, s in enumerate(selectors):
        loc = page.locator(s).first
        visible = loc.is_visible()
        count = page.locator(s).count()
        print(f"Selector {idx} ('{s}'): visible={visible}, count={count}")
        if visible:
            box = loc.bounding_box()
            print(f"  Bounding box: {box}")

    browser.close()
