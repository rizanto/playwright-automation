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
    time.sleep(5)

    print("Clicking RAW tab...")
    page.locator("div[role='tab']:has-text('RAW')").first.click()
    time.sleep(5)

    # Dump all elements in the filters panel
    print("Dumping filter elements...")
    try:
        # Find all select boxes in the filters sidebar (which is on the left)
        filters = page.locator(".ant-select-selector, [role='combobox']").all()
        print(f"Found {len(filters)} select boxes/comboboxes on the page:")
        for idx, f in enumerate(filters):
            # Print parent elements and their class name/text
            parent = f.locator("xpath=./ancestor::div[1]")
            parent_text = parent.inner_text().strip() if parent.count() > 0 else "N/A"
            grandparent = f.locator("xpath=./ancestor::div[2]")
            gp_class = grandparent.get_attribute("class") if grandparent.count() > 0 else "N/A"
            gp_text = grandparent.inner_text().strip().replace("\n", " ")[:100] if grandparent.count() > 0 else "N/A"
            
            print(f"Filter {idx}: parent_text='{parent_text}', grandparent_class='{gp_class}', grandparent_text='{gp_text}'")
    except Exception as e:
        print(f"Error: {e}")

    browser.close()
