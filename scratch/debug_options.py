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

    # Click Subround trigger to open dropdown
    print("Opening Subround dropdown...")
    subround_wrapper = page.locator("div.filter-container, div.filter-control_container, div").filter(has_text="Subround").first
    select_trigger = subround_wrapper.locator(".ant-select-selector, [role='combobox']").first
    select_trigger.click(no_wait_after=True)
    time.sleep(2)

    # Dump the dropdown list container and option HTML/bounding box
    print("Inspecting dropdown options...")
    try:
        dropdowns = page.locator(".ant-select-dropdown").all()
        print(f"Found {len(dropdowns)} .ant-select-dropdown containers in the DOM")
        for i, d in enumerate(dropdowns):
            is_visible = d.is_visible()
            box = d.bounding_box()
            classes = d.get_attribute("class")
            print(f"Dropdown {i}: class='{classes}', visible={is_visible}, bounding_box={box}")
            
            # Find options inside this dropdown
            options = d.locator("[role='option']").all()
            print(f"  Contains {len(options)} options:")
            for o in options:
                text = o.inner_text().strip()
                o_visible = o.is_visible()
                o_box = o.bounding_box()
                o_id = o.get_attribute("id")
                html = o.inner_html()
                print(f"    - Text='{text}', id='{o_id}', visible={o_visible}, box={o_box}")
                print(f"      HTML: {html}")
                
        # Try to select option 2 using keyboard
        print("Selecting option 2 using keyboard...")
        time.sleep(1)
        page.keyboard.press("2")
        time.sleep(0.5)
        page.keyboard.press("Enter")
        time.sleep(2)
        
        # Check current value of select
        current_val = page.locator(".ant-select-selection-item").first.inner_text()
        print(f"After keyboard select, Subround input value: {current_val}")
    except Exception as e:
        print(f"Error inspecting: {e}")

    browser.close()
