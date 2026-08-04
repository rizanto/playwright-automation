import os
import sys
import time
import re
import subprocess
from playwright.sync_api import sync_playwright

# Masukkan folder parent (root) ke dalam system path agar bisa mengimpor vpn_auto_connect
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(current_dir)

import vpn_auto_connect
from humanizer import human_click, human_move_to, human_type, human_scroll

def load_config():
    import configparser
    config_file = os.path.join(current_dir, "config.txt")
    if not os.path.exists(config_file):
        print(f"[ERROR] config.txt tidak ditemukan di {config_file}.")
        sys.exit(1)
    config = configparser.ConfigParser()
    config.read(config_file)
    sections = config.sections()
    if not sections:
        print("[ERROR] Tidak ada section di config.txt.")
        sys.exit(1)
    return dict(config[sections[0]])

def force_kill_cdp_chrome():
    import psutil
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == 'chrome.exe':
                    cmdline = proc.info['cmdline']
                    if cmdline and any('--remote-debugging-port=9222' in arg for arg in cmdline):
                        proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except:
        pass

def launch_real_chrome(headless=False):
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Users\TECNO\AppData\Local\Google\Chrome\Application\chrome.exe"
    ]
    executable = None
    for path in chrome_paths:
        if os.path.exists(path):
            executable = path
            break
    if not executable:
        print("[ERROR] Google Chrome asli tidak ditemukan di sistem Anda.")
        return False
        
    user_data_dir = os.path.join(parent_dir, "chrome_debug_data")
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)
        
    mode_text = "Headless" if headless else "GUI"
    print(f"Membuka Chrome asli secara otomatis (Mode: {mode_text}) dari: {executable}")
    
    args = [
        executable,
        "--remote-debugging-port=9222",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars"
    ]
    if headless:
        args.append("--headless=new")
        args.append("--window-position=-2400,-2400") # Pindahkan jendela kosong di luar layar (Bug Chrome 129+ Windows)
        args.append("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    else:
        args.append("--start-maximized")
        
    try:
        # Gunakan STARTUPINFO dan flags agar tidak ada window konsol/terminal kosong di Windows
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
        
        creation_flags = 0x08000000 if os.name == 'nt' else 0
        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, creationflags=creation_flags, startupinfo=startupinfo)
        time.sleep(3)
        return proc
    except Exception as e:
        print(f"[ERROR] Gagal membuka Chrome: {e}")
        return False



def click_floating_button_and_wait(page_obj, indicator_selectors, max_retries=6):
    """Mengeklik tombol melayang (+) dan memastikan menu/efek target muncul."""
    print("[INFO] Mencari floating button (+) di kanan bawah...")
    
    # Selektor spesifik untuk Ant Design FloatButton atau Custom FAB
    fab_selectors = [
        "button.fab-button",
        ".ant-float-btn-menu-trigger",
        ".ant-float-btn-body",
        ".ant-float-btn",
        "button.ant-btn-circle",
        "div.f\\:fixed button",
        ".fixed button",
        "button:has(svg)"
    ]
    
    for attempt in range(max_retries):
        # Cari FAB yang visible di kuadran kanan bawah layar pada setiap attempt
        fab_loc = None
        for sel in fab_selectors:
            loc = page_obj.locator(sel)
            for i in range(loc.count()):
                el = loc.nth(i)
                if el.is_visible():
                    box = el.bounding_box()
                    if box and box['x'] > 800 and box['y'] > 500:  # Harus di kuadran kanan bawah
                        fab_loc = el
                        print(f"[OK] Menemukan FAB dengan selector: {sel} pada koordinat x={box['x'] + box['width']/2}, y={box['y'] + box['height']/2}")
                        break
            if fab_loc:
                break
                
        if not fab_loc:
            # Fallback ke selector umum yang visible di kanan bawah
            loc = page_obj.locator(".ant-float-btn, .ant-float-btn-body, button.ant-btn-circle").last
            if loc.is_visible():
                fab_loc = loc
                
        if not fab_loc:
            print(f"[WARN] Tombol melayang (+) belum siap/ditemukan (Percobaan {attempt + 1}/{max_retries}). Menunggu pemuatan...")
            time.sleep(3)
            continue
            
        print(f"[INFO] Mengeklik floating button (+) (Percobaan {attempt + 1}/{max_retries})...")
        try:
            # Mengutamakan pemicu klik via DOM Javascript agar kebal terhadap halangan overlay
            fab_loc.evaluate("el => { el.click(); el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true})); }")
        except Exception as e:
            print(f"[WARN] Gagal klik via JS: {e}. Mencoba klik biasa Playwright...")
            try:
                fab_loc.click(force=True, timeout=3000)
            except Exception as click_err:
                print(f"[WARN] Klik biasa Playwright juga gagal: {click_err}")
        
        # Tunggu transisi rendering secara perlahan menggunakan wait_for Playwright
        for sel in indicator_selectors:
            try:
                # wait_for secara otomatis menunggu hingga animasi/transisi selesai dan elemen benar-benar visibel
                page_obj.locator(sel).first.wait_for(state="visible", timeout=3000)
                print(f"[OK] Indikator target '{sel}' terkonfirmasi aktif secara visual. Menu berhasil dibuka!")
                return True
            except:
                pass
                
        print("[WARN] Indikator menu belum muncul secara visual, mengulangi klik...")
        time.sleep(1) # Beri jeda sejenak sebelum mencoba toggle ulang
        
    return False

def toggle_checkbox_by_label(page_obj, label_text, target_state=True):
    """Mencari checkbox berdasarkan label teks dan menyetel statusnya."""
    print(f"[INFO] Mengatur checkbox '{label_text}' ke: {target_state}")
    
    # 1. Selector presisi dari Outer HTML:
    #    Switchbox memiliki id="switch-*-control" dan class 'tw:data-checked:bg-primary'
    #    Status ON: thumb di dalam memiliki class 'tw:data-checked:translate-x-4'
    priority_switch_selectors = [
        "[id$='-control'][id*='switch']",
        "div[class*='data-checked:bg-primary']",
    ]
    for sw_sel in priority_switch_selectors:
        try:
            loc = page_obj.locator(f"xpath=//div[contains(normalize-space(.),'{label_text}')]").locator(sw_sel)
            if loc.count() == 0:
                loc = page_obj.locator(sw_sel)
            if loc.count() > 0 and loc.first.is_visible():
                sw = loc.first
                data_checked = sw.evaluate("""
                    el => {
                        if (el.getAttribute('data-checked') !== null) return true;
                        const thumb = el.querySelector('[id$="-thumb"]');
                        if (thumb) {
                            const cls = thumb.getAttribute('class') || '';
                            return cls.includes('translate-x-4');
                        }
                        return false;
                    }
                """)
                is_checked = bool(data_checked)
                print(f"   -> Switchbox '{label_text}' status: {'ON' if is_checked else 'OFF'}, target: {'ON' if target_state else 'OFF'}")
                if is_checked != target_state:
                    sw.click(force=True)
                    time.sleep(1)
                    print(f"   -> Switchbox berhasil di-toggle.")
                else:
                    print(f"   -> Status switchbox sudah sesuai.")
                return True
        except: pass

    # 2. Fallback: pencarian relatif berdasarkan teks label
    try:
        label_loc = page_obj.locator(f"text={label_text}").first
        label_loc.wait_for(state="visible", timeout=15000)
        
        container = label_loc.locator("xpath=ancestor::div[.//input[@type='checkbox'] or .//*[@role='switch'] or .//*[@id[contains(.,'-control')]]  ][1]")
        if container.count() == 0:
            print(f"[WARN] Tidak dapat menemukan checkbox di sekitar label '{label_text}'.")
            return False
            
        checkbox_input = container.locator("[id$='-control'][id*='switch'], input[type='checkbox'], [role='switch']").first
        
        is_checked = False
        if checkbox_input.count() > 0:
            try:
                data_checked = checkbox_input.evaluate("""
                    el => {
                        if (el.getAttribute('data-checked') !== null) return true;
                        const thumb = el.querySelector('[id$="-thumb"]');
                        if (thumb) return (thumb.getAttribute('class') || '').includes('translate-x-4');
                        return false;
                    }
                """)
                is_checked = bool(data_checked)
            except:
                try:
                    is_checked = checkbox_input.is_checked()
                except:
                    aria_checked = checkbox_input.get_attribute("aria-checked")
                    if aria_checked:
                        is_checked = (aria_checked.lower() == "true")
        else:
            class_attr = container.get_attribute("class") or ""
            is_checked = "checked" in class_attr
            
        if is_checked != target_state:
            print(f"   -> Mengklik elemen switch untuk mengubah status.")
            visual_switch = container.locator("[id$='-control'][id*='switch'], div[class*='cursor-pointer']").first
            if visual_switch.count() > 0:
                visual_switch.click(force=True)
            else:
                checkbox_input.click(force=True)
            time.sleep(1)
        else:
            print(f"   -> Status sudah sesuai.")
        return True
    except Exception as e:
        print(f"[WARN] Gagal menyetel checkbox '{label_text}': {e}")
        return False

def login_sso_tab(sso_tab, username, password):
    """Mengakses halaman login SSO BPS pada Tab 1, mengisi kredensial, dan memastikan login sukses ke dashboard."""
    print("[INFO] Membuka halaman login SSO di Tab 1...")
    sso_tab.goto("https://fasih-sm.bps.go.id/oauth_login.html", wait_until="domcontentloaded", timeout=60000)
    time.sleep(3)
    
    # Cek jika cookies lama langsung redirect ke dashboard BPS (sudah login)
    if "oauth_login" not in sso_tab.url and "sso.bps" not in sso_tab.url:
        print("[SUCCESS] Sesi login terdetect masih aktif secara otomatis pada Tab 1.")
        return True
        
    print("[INFO] Sesi login kosong. Melakukan login SSO BPS...")
    # Klik tombol Login SSO BPS
    try:
        btn = sso_tab.locator("text=SSO BPS").first
        if btn.count() > 0:
            btn.click(force=True, timeout=5000)
        else:
            sso_tab.click("//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'sso bps')]", force=True, timeout=5000)
    except Exception as e:
        print(f"[WARN] Gagal klik SSO BPS (namun navigasi mungkin sudah berjalan): {e}")
            
    # Tunggu redirect ke sso.bps.go.id dengan batas 45 detik
    try:
        import re
        sso_tab.wait_for_url(re.compile(r".*sso\.bps\.go\.id.*"), timeout=45000)
        print("[INFO] Mengisi kredensial SSO BPS pada Tab 1...")
        sso_tab.fill('input[name="username"]', username, timeout=10000)
        sso_tab.fill('input[name="password"]', password, timeout=10000)
        sso_tab.click('button[type="submit"], input[type="submit"]', timeout=10000)
    except Exception as e:
        print(f"[WARN] Pengisian kredensial SSO terlewati/gagal (mungkin sudah login atau koneksi lambat): {e}")
            
    # Tunggu redirect selesai ke dashboard fasih-sm
    print("[INFO] Menunggu redirect akhir ke dashboard Fasih-SM...")
    try:
        sso_tab.wait_for_url(lambda url: "fasih-sm.bps.go.id" in url and "oauth_login" not in url and "sso.bps" not in url, timeout=40000)
        print("[SUCCESS] Login berhasil pada Tab 1.")
        return True
    except Exception as e:
        print(f"[ERROR] Gagal login SSO BPS pada Tab 1: {e}")
        return False


def run_automation():
    # Load konfigurasi lokal
    cfg = load_config()
    username = cfg.get("username", "")
    password = cfg.get("password", "")
    target_url = cfg.get("target_url", "")
    dry_run = cfg.get("dry_run", "True").strip().lower() == "true"
    headless = cfg.get("headless", "False").strip().lower() == "true"

    print("=== FASIH-SM ANOMALY & REJECT AUTOMATION ===")
    print(f"[INFO] Target URL: {target_url}")
    print(f"[INFO] Mode Dry Run (Simulasi): {dry_run}")
    print(f"[INFO] Mode Headless (Background): {headless}")

    # 1. Cek Koneksi VPN BPS
    print("[INFO] Memeriksa status koneksi VPN BPS...")
    if not vpn_auto_connect.is_vpn_connected():
        print("[WARN] VPN terputus. Mencoba menghubungkan VPN otomatis...")
        vpn_auto_connect.run_auto_vpn()
        if not vpn_auto_connect.is_vpn_connected():
            print("[ERROR] Gagal menyambungkan VPN. Automasi dihentikan.")
            return
    else:
        print("[SUCCESS] VPN BPS aktif/terhubung.")

    # Tutup chrome sisa port 9222
    force_kill_cdp_chrome()
    
    # Hubungkan mode headless
    headless_mode = headless or "--headless" in sys.argv
    chrome_proc = launch_real_chrome(headless=headless_mode)
    if not chrome_proc:
        return

    with sync_playwright() as p:
        try:
            print("[INFO] Menghubungkan ke browser Chrome via CDP...")
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            try:
                context.clear_cookies()
                print("[INFO] Menghapus cookies sesi sebelumnya agar login dengan kredensial baru...")
            except Exception as ce:
                print(f"[WARN] Gagal membersihkan cookies: {ce}")
            
            # Tab 1: Khusus menangani sesi login SSO
            sso_tab = context.pages[0] if len(context.pages) > 0 else context.new_page()
            if headless_mode:
                sso_tab.set_viewport_size({"width": 1366, "height": 768})
            
            # Lakukan login di SSO Tab (Tab 1)
            print("[INFO] Menyiapkan sesi login BPS di Tab 1...")
            if not login_sso_tab(sso_tab, username, password):
                raise Exception("Gagal melakukan login SSO BPS pada Tab 1.")

            # Menggunakan Tab 1 langsung untuk navigasi ke detail assignment
            target_tab = sso_tab
            print(f"[INFO] Membuka URL target detail assignment di Tab 1: {target_url}")
            target_tab.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(5) # Tunggu AJAX loading selesai

            # Deteksi jika halaman error (sesi tidak sah / gagal muat)
            if "There's some error" in target_tab.content() or target_tab.locator("text=There's some error").count() > 0:
                print("[WARN] Terdeteksi halaman error. Mencoba login ulang...")
                if not login_sso_tab(sso_tab, username, password):
                    raise Exception("Gagal login ulang pada Tab 1.")
                
                print("[INFO] Membuka kembali URL target...")
                target_tab.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(5)

            # 3. Klik tombol Review di kanan atas (membuka tab baru, yaitu Tab 3)
            print("[INFO] Menunggu tombol 'Review'...")
            # Selector presisi: data-tsd-source dari assignment-action.tsx:142, atau ikon telegram
            review_btn = target_tab.locator("[data-tsd-source*='assignment-action.tsx:142']").first
            if review_btn.count() == 0 or not review_btn.is_visible():
                review_btn = target_tab.locator("button:has(.tabler-icon-brand-telegram)").first
            if review_btn.count() == 0 or not review_btn.is_visible():
                review_btn = target_tab.locator("button:has-text('Review')").first
            review_btn.wait_for(state="visible", timeout=20000)
            
            print("[INFO] Mengeklik tombol 'Review' (secara alami/humanizer) dan menunggu tab baru terbuka...")
            with context.expect_page() as new_page_info:
                human_click(target_tab, review_btn)
            new_page = new_page_info.value
            new_page.wait_for_load_state("domcontentloaded")
            if headless_mode:
                new_page.set_viewport_size({"width": 1366, "height": 768})
            preview_url = new_page.url
            print(f"[SUCCESS] Tab baru berhasil dimuat. URL: {preview_url}")
            
            # Menunggu konten form preview selesai dimuat
            print("[INFO] Menunggu konten form preview selesai dimuat...")
            try:
                new_page.wait_for_load_state("networkidle", timeout=30000)
            except:
                pass
            try:
                new_page.locator("text=SENSUS EKONOMI 2026").first.wait_for(state="visible", timeout=60000)
                print("[OK] Konten halaman review terdeteksi sudah dimuat.")
            except Exception as e:
                print(f"[WARN] Timeout menunggu konten review: {e}")
            time.sleep(2)

            # 4. Masuk ke Mode Edit langsung via URL + /edit (lebih andal dari klik floating button)
            edit_url = preview_url.rstrip("/") + "/edit"
            print(f"[INFO] Navigasi langsung ke Mode Edit: {edit_url}")
            new_page.goto(edit_url, wait_until="domcontentloaded", timeout=60000)
            
            # Tunggu Mode Edit terkonfirmasi
            print("[INFO] Menunggu konfirmasi Mode Edit dimuat...")
            try:
                new_page.wait_for_load_state("networkidle", timeout=30000)
            except:
                pass
            try:
                new_page.locator("text=Mode Edit").first.wait_for(state="visible", timeout=30000)
                print("[OK] Halaman sudah dalam Mode Edit!")
            except:
                try:
                    new_page.locator("text=Kirim").first.wait_for(state="visible", timeout=15000)
                    print("[OK] Tombol Kirim terdeteksi. Halaman sudah dalam Mode Edit!")
                except Exception as e:
                    print(f"[WARN] Timeout menunggu konfirmasi Mode Edit: {e}")
            time.sleep(2)


            print("[INFO] Menunggu seluruh elemen halaman Mode Edit ter-render sepenuhnya...")
            for _ in range(20):
                try:
                    body_txt = new_page.evaluate("() => document.body ? document.body.innerText : ''")
                    if "Kirim" in body_txt or "KIRIM" in body_txt or "CATATAN" in body_txt or "Catatan" in body_txt:
                        print("[OK] Komponen Halaman Mode Edit terdeteksi selesai dimuat!")
                        break
                except: pass
                time.sleep(1)
            time.sleep(2)

            # 5. Klik bagian CATATAN di sidebar kiri
            print("[INFO] Mencari dan mengeklik 'CATATAN' di sidebar kiri...")
            catatan_clicked = False
            catatan_selectors = [
                "div[title='CATATAN']",
                "div[title='Catatan']",
                "[title='CATATAN']",
                "[title='Catatan']",
                "nav >> text=CATATAN",
                "[class*='sidebar'] >> text=CATATAN",
                "aside >> text=CATATAN",
                "text=CATATAN",
                "text=Catatan",
                "//span[contains(translate(text(), 'catatan', 'CATATAN'), 'CATATAN')]",
                "//div[contains(translate(text(), 'catatan', 'CATATAN'), 'CATATAN')]",
                "//a[contains(translate(text(), 'catatan', 'CATATAN'), 'CATATAN')]"
            ]
            
            start_t = time.time()
            while time.time() - start_t < 20:
                for nav_sel in catatan_selectors:
                    try:
                        loc = new_page.locator(nav_sel)
                        for idx in range(loc.count()):
                            item = loc.nth(idx)
                            if item.is_visible():
                                box = item.bounding_box()
                                if box and box['x'] < 350:
                                    print(f"[OK] Menemukan 'CATATAN' di sidebar kiri (x={box['x']}, y={box['y']}). Mengeklik...")
                                    item.scroll_into_view_if_needed()
                                    item.click(force=True)
                                    catatan_clicked = True
                                    break
                        if catatan_clicked: break
                    except: pass
                if catatan_clicked: break
                time.sleep(1)

            if not catatan_clicked:
                print("[WARN] Mencoba JS click fallback untuk menu 'CATATAN' di sidebar...")
                js_click_catatan = """
                () => {
                    let els = Array.from(document.querySelectorAll('*'));
                    let target = els.find(e => e.offsetWidth > 0 && e.offsetHeight > 0 && e.getBoundingClientRect().x < 350 && e.innerText && e.innerText.trim().toUpperCase() === 'CATATAN');
                    if (target) {
                        target.click();
                        let parent = target.closest('a, button, li, div[role="button"]');
                        if (parent && parent !== target) parent.click();
                        return true;
                    }
                    return false;
                }
                """
                catatan_clicked = new_page.evaluate(js_click_catatan)

            print("[INFO] Menunggu form CATATAN & switchbox dimuat di layar...")
            for _ in range(15):
                try:
                    if new_page.locator("text=Tampilkan Anomali Usaha dan Keluarga").first.is_visible():
                        print("[SUCCESS] Form CATATAN & Switchbox 'Tampilkan Anomali Usaha dan Keluarga' BERHASIL terlihat di layar!")
                        break
                except: pass
                time.sleep(1)

            # 6. Centang "Tampilkan Anomali Usaha dan Keluarga"
            toggle_checkbox_by_label(new_page, "Tampilkan Anomali Usaha dan Keluarga", True)
            time.sleep(1)

            # 7. Check & uncheck "Anomali diselesaikan oleh admin"
            try:
                with open("catatan_dom.html", "w", encoding="utf-8") as f:
                    f.write(new_page.content())
                new_page.screenshot(path="catatan_screen.png", full_page=True)
            except:
                pass
            toggle_checkbox_by_label(new_page, "Anomali diselesaikan oleh admin", True)
            time.sleep(1.5)
            toggle_checkbox_by_label(new_page, "Anomali diselesaikan oleh admin", False)

            time.sleep(1)

            # 8. Klik tombol KIRIM di header edit mode
            print("[INFO] Mengeklik tombol KIRIM...")
            # Tombol KIRIM: class tw:bg-primary, teks 'Kirim'
            kirim_btn = new_page.locator("button[class*='tw:bg-primary']:has-text('Kirim')").first
            if kirim_btn.count() == 0 or not kirim_btn.is_visible():
                kirim_btn = new_page.locator("button:has-text('Kirim')").first
            kirim_btn.click(force=True)
            time.sleep(2)

            # 9. Klik KIRIM di pop-up konfirmasi pertama
            print("[INFO] Konfirmasi pertama: pop-up KIRIM...")
            if dry_run:
                print("[DRY_RUN] Membatalkan pengiriman dengan menekan Escape pada modal KIRIM.")
                new_page.keyboard.press("Escape")
                time.sleep(2)
            else:
                # Tahap 1: Popup KIRIM - tombol 'Kirim' (class tw:bg-primary)
                print("[LIVE] Mengeklik KIRIM di popup pertama...")
                modal_kirim1 = new_page.locator("[role='dialog'] button[class*='tw:bg-primary']:has-text('Kirim')").first
                if modal_kirim1.count() == 0 or not modal_kirim1.is_visible():
                    modal_kirim1 = new_page.locator("[role='dialog'] button:has-text('Kirim')").first
                if modal_kirim1.count() > 0:
                    modal_kirim1.click(force=True)
                    time.sleep(2)
                else:
                    print("[WARN] Tombol Kirim pada popup pertama tidak ditemukan!")
                
                # Tahap 2: Popup KONFIRMASI KIRIM - tombol 'Konfirmasi' (class tw:bg-primary)
                print("[LIVE] Mengeklik KONFIRMASI di popup kedua...")
                modal_kirim2 = new_page.locator("[role='dialog'] button[class*='tw:bg-primary']:has-text('Konfirmasi')").first
                if modal_kirim2.count() == 0 or not modal_kirim2.is_visible():
                    modal_kirim2 = new_page.locator("[role='dialog'] button:has-text('Konfirmasi')").first
                if modal_kirim2.count() > 0:
                    modal_kirim2.click(force=True)
                    time.sleep(5)
                else:
                    print("[WARN] Tombol Konfirmasi pada popup kedua tidak ditemukan!")

            # 11. Tombol Kembali ke preview: ikon tabler-icon-arrow-left (draggable-toolbar.tsx:123)
            print("[INFO] Kembali ke mode preview...")
            back_fab = new_page.locator("button:has(.tabler-icon-arrow-left)").first
            if back_fab.count() == 0 or not back_fab.is_visible():
                back_fab = new_page.locator("[data-tsd-source*='draggable-toolbar.tsx:123']").first
            if back_fab.count() == 0 or not back_fab.is_visible():
                back_fab = new_page.locator("button[title*='Kembali']").first
            if back_fab.count() > 0 and back_fab.is_visible():
                back_fab.click(force=True)
            time.sleep(2)

            # Pop-up konfirmasi tinggalkan halaman: tombol 'Tinggalkan' class f:bg-warning
            print("[INFO] Mengecek pop-up konfirmasi tinggalkan halaman...")
            leave_btn = new_page.locator("[role='dialog'] button[class*='bg-warning']:has-text('Tinggalkan')").first
            if leave_btn.count() == 0 or not leave_btn.is_visible():
                leave_btn = new_page.locator("[role='dialog'] button:has-text('Tinggalkan'), [role='dialog'] button:has-text('Keluar')").first
            if leave_btn.count() > 0:
                print("[INFO] Memilih 'Tinggalkan' pada pop-up konfirmasi...")
                leave_btn.click(force=True)
                time.sleep(5)

            # 12. Reject langsung dari halaman review
            # Tombol Reject FAB: ikon tabler-icon-x, class f:bg-destructive
            print("[INFO] Mencari tombol Reject FAB...")
            reject_fab = new_page.locator("button:has(.tabler-icon-x)").first
            if reject_fab.count() == 0 or not reject_fab.is_visible():
                reject_fab = new_page.locator("[data-tsd-source*='draggable-toolbar.tsx:138']:has(.tabler-icon-x)").first
            if reject_fab.count() == 0 or not reject_fab.is_visible():
                reject_fab = new_page.locator("button[class*='bg-destructive']").first
            if reject_fab.count() > 0 and reject_fab.is_visible():
                print("[OK] Tombol Reject FAB ditemukan. Mengeklik...")
                reject_fab.evaluate("e => { e.click(); e.dispatchEvent(new MouseEvent('click', {bubbles: true})); }")
            else:
                raise Exception("Gagal menemukan tombol FAB Reject di halaman review")
            time.sleep(2)

            # Pop-up konfirmasi reject: tombol 'Konfirmasi' class f:bg-destructive (action-reject.tsx)
            print("[INFO] Membaca tombol konfirmasi Reject...")
            confirm_reject_btn = new_page.locator("[role='dialog'] button[class*='bg-destructive']:has-text('Konfirmasi')").first
            if confirm_reject_btn.count() == 0 or not confirm_reject_btn.is_visible():
                confirm_reject_btn = new_page.locator("[data-tsd-source*='action-reject.tsx']:has-text('Konfirmasi')").first
            if confirm_reject_btn.count() == 0 or not confirm_reject_btn.is_visible():
                confirm_reject_btn = new_page.locator("[role='dialog'] button:has-text('Konfirmasi')").first
            if confirm_reject_btn.count() == 0:
                confirm_reject_btn = new_page.locator("text=Konfirmasi").last

            if dry_run:
                print("[DRY_RUN] Menghentikan klik KONFIRMASI reject agar assignment tetap utuh.")
                new_page.keyboard.press("Escape")
                time.sleep(1)
            else:
                print("[LIVE] Mengeklik KONFIRMASI Reject...")
                confirm_reject_btn.click()
                time.sleep(4)

            print("[SUCCESS] Seluruh rangkaian otomatisasi anomali/reject selesai dijalankan.")
            
        except Exception as e:
            print(f"[ERROR] Rangkaian otomatisasi terhenti karena: {e}")
            try:
                if new_page:
                    with open("error_dump.html", "w", encoding="utf-8") as f:
                        f.write(new_page.content())
                    new_page.screenshot(path="error_screen.png", full_page=True)
                    print("[INFO] DOM dan Screenshot error berhasil disimpan.")
                else:
                    print("[INFO] Error terjadi sebelum halaman target terbuka, tidak ada DOM yang didump.")
            except Exception as inner_e:
                print(f"[ERROR] Gagal menyimpan dump: {inner_e}")
            
            print("[INFO] Menahan browser tetap terbuka selama 10 menit untuk debugging...")
            time.sleep(600)
        finally:
            print("[INFO] Menutup browser...")
            try:
                browser.close()
            except:
                pass
            if chrome_proc:
                try:
                    chrome_proc.terminate()
                except:
                    pass
            force_kill_cdp_chrome()

if __name__ == "__main__":
    run_automation()
