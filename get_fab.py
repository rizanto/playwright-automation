from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    try:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        
        for i, page in enumerate(context.pages):
            print(f"Tab {i}: {page.url}")
            if "edit" in page.url or "assignment/" in page.url:
                print(f"--- Elements in Tab {i} ---")
                btns = page.locator("button, a").all()
                for b in btns:
                    if b.is_visible():
                        html = b.evaluate('el => el.outerHTML')
                        if 'kembali' in html.lower() or 'svg' in html.lower() or 'float' in html.lower():
                            print(f"Found: {html[:200]}")
    except Exception as e:
        print(f"Error: {e}")
