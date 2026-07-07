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

    # Click 3-dots of raw data table
    print("Clicking 3-dots...")
    three_dots = page.locator("xpath=//div[contains(@data-test-chart-name, 'data.tab')]//span[@aria-label='More Options']").first
    three_dots.click()
    time.sleep(2)

    # Hover Download
    print("Hovering Download...")
    download_menu = page.locator(".ant-dropdown:not(.ant-dropdown-hidden) .ant-dropdown-menu-item, .ant-dropdown:not(.ant-dropdown-hidden) [role='menuitem']").filter(has_text="Download").first
    download_menu.hover()
    time.sleep(2)

    # Print HTML of all active dropdowns and submenus
    print("Dumping dropdown HTML...")
    try:
        dropdowns = page.locator(".ant-dropdown:not(.ant-dropdown-hidden), .ant-dropdown-menu-submenu-popup").all()
        for idx, d in enumerate(dropdowns):
            print(f"\n--- Dropdown/Submenu {idx} (visible={d.is_visible()}, class={d.get_attribute('class')}) ---")
            print(d.inner_html()[:4000])
    except Exception as e:
        print(f"Error: {e}")

    browser.close()
