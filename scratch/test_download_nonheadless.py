import os
import sys
import time
from playwright.sync_api import sync_playwright

USERNAME = "riva.adli"
PASSWORD = "adliriva16"
TARGET_URL = "https://fasih-dashboard.bps.go.id/superset/dashboard/ubinan26s/"

with sync_playwright() as p:
    # Run in non-headless mode so we/user can see it
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()

    # Listen to console logs
    page.on("console", lambda msg: print(f"[Browser Console] {msg.type}: {msg.text}"))
    page.on("pageerror", lambda err: print(f"[Browser Error] {err}"))

    print("Navigating to portal...")
    page.goto("https://fasih-dashboard.bps.go.id/", wait_until="load")
    
    try:
        page.locator("button, input[type='button']").filter(has_text="GO").first.click(timeout=5000)
        time.sleep(2)
    except Exception:
        pass

    try:
        page.wait_for_load_state("load", timeout=10000)
    except Exception:
        pass
    
    # Wait up to 10 seconds for SSO url if needed
    for _ in range(10):
        if "sso.bps.go.id" in page.url or page.locator('input[name="username"]').is_visible():
            break
        time.sleep(1)

    if "sso.bps.go.id" in page.url or page.locator('input[name="username"]').is_visible():
        print("Logging in via SSO...")
        page.fill('input[name="username"]', USERNAME)
        page.fill('input[name="password"]', PASSWORD)
        page.click('button[type="submit"], input[type="submit"]')
        
        # Wait for redirect away from SSO
        for _ in range(30):
            if "sso.bps.go.id" not in page.url:
                break
            time.sleep(1)
        time.sleep(5)

    print("Navigating to target dashboard...")
    page.goto(TARGET_URL, wait_until="load")
    
    # Wait for RAW tab to be visible
    print("Waiting for RAW tab...")
    page.locator("div.ant-tabs-tab:has-text('RAW'), div[role='tab']:has-text('RAW')").first.wait_for(state="visible", timeout=20000)
    page.locator("div.ant-tabs-tab:has-text('RAW'), div[role='tab']:has-text('RAW')").first.click()
    time.sleep(5)

    # Set filter Subround to 2
    print("Setting filter Subround to 2...")
    subround_wrapper = page.locator("div.filter-container, div.filter-control_container, div").filter(has_text="Subround").first
    select_trigger = subround_wrapper.locator(".ant-select-selector, [role='combobox']").first
    select_trigger.click(no_wait_after=True)
    time.sleep(2)
    page.keyboard.press("2")
    time.sleep(0.5)
    page.keyboard.press("Enter")
    time.sleep(2)

    print("Clicking APPLY FILTERS...")
    page.locator("button:visible").filter(has_text="APPLY FILTERS").first.click(no_wait_after=True)
    time.sleep(5)

    # Wait for loading spinner to disappear
    print("Waiting for spinner to disappear...")
    try:
        page.locator("img.loading, .ant-spin-spinning, .loading, svg.spin").first.wait_for(state="hidden", timeout=60000)
        print("Spinner disappeared.")
    except Exception:
        print("Spinner wait timed out.")

    time.sleep(5)

    # Click 3-dots
    print("Clicking 3-dots...")
    three_dots = page.locator("xpath=//div[contains(@data-test-chart-name, 'data.tab')]//span[@aria-label='More Options']").first
    three_dots.click()
    time.sleep(2)

    # Hover Download
    print("Hovering Download...")
    download_menu = page.locator(".ant-dropdown:not(.ant-dropdown-hidden) .ant-dropdown-menu-submenu-title, .ant-dropdown:not(.ant-dropdown-hidden) [role='menuitem']").filter(has_text="Download").first
    download_menu.hover()
    time.sleep(2)

    # Try to click Export to .CSV directly on the span
    print("Clicking Export to .CSV...")
    try:
        with page.expect_download(timeout=30000) as download_info:
            # Target the span containing the text directly
            page.locator(".ant-dropdown-menu-submenu-popup:not(.ant-dropdown-menu-hidden) span").filter(has_text="Export to .CSV").first.click(timeout=5000, no_wait_after=True)
        download = download_info.value
        print(f"Download succeeded! Suggested filename: {download.suggested_filename}")
        download.save_as("test_raw.csv")
        print("File saved to test_raw.csv")
    except Exception as e:
        print(f"Download failed: {e}")

    time.sleep(10)
    browser.close()
