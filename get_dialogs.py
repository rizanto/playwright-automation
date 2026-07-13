from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    try:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0] # Tab 0 is the edit page
        
        print("Mencari semua dialog di Tab 0...")
        dialogs = page.locator("[role='alertdialog'], [role='dialog']").all()
        for i, d in enumerate(dialogs):
            print(f"--- Dialog {i} ---")
            print(d.inner_text())
            html = d.evaluate('el => el.outerHTML')
            print(f"HTML:\n{html}")
            
    except Exception as e:
        print(f"Error: {e}")
