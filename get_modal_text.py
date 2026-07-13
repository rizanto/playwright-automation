from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    try:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        new_page = context.pages[-1]
        
        print("Mencari dialog...")
        dialogs = new_page.locator("div[role='dialog'], .ant-modal-content").all()
        for i, d in enumerate(dialogs):
            if d.is_visible():
                print(f"--- Dialog {i} ---")
                print(d.inner_text())
                
                print(f"--- Buttons in Dialog {i} ---")
                btns = d.locator("button").all()
                for b in btns:
                    if b.is_visible():
                        print(f"Button: '{b.inner_text()}' (HTML: {b.evaluate('el => el.outerHTML')})")
        
    except Exception as e:
        print(f"Error: {e}")
