import os
import sys
import time
from playwright.sync_api import sync_playwright

current_dir = r"c:\Users\TECNO\Desktop\Project\playwright-automation"
sys.path.append(current_dir)
from automation.automate_anomaly_reject import load_config, launch_real_chrome, is_logged_in_bps, login_sso_bps, click_floating_button_and_wait

cfg = load_config()
target_url = cfg.get("target_url", "")
username = cfg.get("username", "")
password = cfg.get("password", "")

def run_debug():
    proc = launch_real_chrome(headless=False)
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            new_page = context.pages[-1]
            
            # Asumsi page sudah di mode Edit dan modal KIRIM masih kebuka.
            # Kita coba tutup modal KIRIM yang terbuka.
            batal = new_page.locator("text=Batal")
            if batal.count() > 0:
                batal.first.click()
                time.sleep(1)
            
            # Coba klik FAB back
            print("Clicking FAB back...")
            new_page.locator("#fasih-fab-root button").first.click()
            time.sleep(2)
            
            print("Getting all buttons...")
            buttons = new_page.locator("button").all()
            for b in buttons:
                if b.is_visible():
                    print("Button:", b.inner_text())
                    
            print("Getting all modals...")
            print(new_page.locator("div[role='dialog']").inner_text())
            
        except Exception as e:
            print(f"[ERROR] {e}")
        finally:
            if proc:
                import psutil
                try:
                    for child in psutil.Process(proc.pid).children(recursive=True):
                        child.kill()
                    proc.kill()
                except:
                    pass

if __name__ == '__main__':
    run_debug()
