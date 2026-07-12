import os
import sys
import time
import re
import subprocess
from playwright.sync_api import sync_playwright

# Masukkan folder parent (root) ke dalam system path agar bisa mengimpor vpn_auto_connect
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import vpn_auto_connect

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



def check_menu_item_visible_js(page_obj, selector):
    """Mengecek apakah elemen indikator benar-benar visible secara fisik dan visual oleh user menggunakan JS."""
    js_check = """
    (sel) => {
        const cleanSel = sel.replace('text=', '').replace(' >> visible=true', '').replace(/"/g, '').trim();
        
        function isElementTrulyVisible(el) {
            if (!el) return false;
            const rect = el.getBoundingClientRect();
            // Cek jika ukuran elemen 0 atau posisinya off-screen
            if (rect.width === 0 || rect.height === 0) return false;
            if (rect.bottom < 0 || rect.right < 0 || rect.top > window.innerHeight || rect.left > window.innerWidth) {
                return false;
            }
            
            let parent = el;
            while (parent) {
                const style = window.getComputedStyle(parent);
                if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) < 0.1) {
                    return false;
                }
                if (style.transform && (style.transform.includes('matrix(0') || style.transform.includes('scale(0)'))) {
                    return false;
                }
                const pRect = parent.getBoundingClientRect();
                if (style.overflow === 'hidden' && (pRect.width === 0 || pRect.height === 0)) {
                    return false;
                }
                parent = parent.parentElement;
            }
            return true;
        }

        const all = Array.from(document.querySelectorAll('*'));
        const match = all.find(el => {
            const text = el.textContent || '';
            const matchesText = text.trim() === cleanSel || text.includes(cleanSel);
            return matchesText && isElementTrulyVisible(el);
        });
        return match != null;
    }
    """
    try:
        return page_obj.evaluate(js_check, selector)
    except Exception as e:
        print(f"[WARN] Gagal cek visibilitas riil via JS: {e}")
        return False

def click_floating_button_and_wait(page_obj, indicator_selectors, max_retries=6):
    """Mengeklik tombol melayang (+) dan memastikan menu/efek target muncul."""
    print("[INFO] Mencari floating button (+) di kanan bawah...")
    
    # Selektor spesifik untuk Ant Design FloatButton atau Floating Action Button
    fab_selectors = [
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
                        print(f"✅ Menemukan FAB dengan selector: {sel} pada koordinat x={box['x'] + box['width']/2}, y={box['y'] + box['height']/2}")
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
        
        # Tunggu transisi rendering
        time.sleep(2.5)
        for sel in indicator_selectors:
            if check_menu_item_visible_js(page_obj, sel):
                print(f"✅ Indikator target '{sel}' terkonfirmasi aktif secara visual (opacity > 0.5). Menu berhasil dibuka!")
                return True
        print("[WARN] Indikator menu belum muncul secara visual, mengulangi klik...")
        
    return False

def toggle_checkbox_by_label(page_obj, label_text, target_state=True):
    """Mencari checkbox berdasarkan label teks dan menyetel statusnya."""
    print(f"[INFO] Mengatur checkbox '{label_text}' ke: {target_state}")
    try:
        label_loc = page_obj.locator(f"text={label_text}").first
        label_loc.wait_for(state="visible", timeout=15000)
        
        parent = label_loc.locator("xpath=..")
        checkbox_input = parent.locator("input[type='checkbox']").first
        
        is_checked = False
        if checkbox_input.count() > 0:
            is_checked = checkbox_input.is_checked()
        else:
            class_attr = parent.get_attribute("class") or ""
            is_checked = "checked" in class_attr
            
        if is_checked != target_state:
            print(f"   -> Mengklik label untuk mengubah status.")
            label_loc.click()
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
        sso_tab.locator("text=SSO BPS").first.click(timeout=8000)
    except Exception:
        try:
            sso_tab.click("//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'sso bps')]", timeout=8000)
        except Exception as e:
            print(f"[WARN] Gagal klik SSO BPS: {e}")
            
    # Tunggu redirect ke sso.bps.go.id
    time.sleep(3)
    if "sso.bps.go.id" in sso_tab.url:
        print("[INFO] Mengisi kredensial SSO BPS pada Tab 1...")
        try:
            sso_tab.fill('input[name="username"]', username, timeout=10000)
            sso_tab.fill('input[name="password"]', password, timeout=10000)
            sso_tab.click('button[type="submit"], input[type="submit"]', timeout=10000)
        except Exception as e:
            print(f"[WARN] Pengisian kredensial SSO terlewati/gagal: {e}")
            
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

            # Tab 2: Khusus memuat detail assignment dan navigasi preview
            print("[INFO] Membuka Target Tab (Tab 2)...")
            target_tab = context.new_page()
            if headless_mode:
                target_tab.set_viewport_size({"width": 1366, "height": 768})

            # Buka URL target detail assignment di Tab 2
            print(f"[INFO] Membuka URL target detail assignment di Tab 2: {target_url}")
            target_tab.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(5) # Tunggu AJAX loading selesai

            # Deteksi jika halaman error (sesi tidak sah / gagal muat)
            if "There's some error" in target_tab.content() or target_tab.locator("text=There's some error").count() > 0:
                print("[WARN] Terdeteksi halaman error di Tab 2. Mencoba login ulang di Tab 1...")
                target_tab.close()
                
                # Ulangi login di Tab 1
                if not login_sso_tab(sso_tab, username, password):
                    raise Exception("Gagal login ulang pada Tab 1.")
                
                # Buka ulang Tab 2
                print("[INFO] Membuka kembali Target Tab (Tab 2)...")
                target_tab = context.new_page()
                if headless_mode:
                    target_tab.set_viewport_size({"width": 1366, "height": 768})
                target_tab.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(5)

            # 3. Klik tombol Review di kanan atas (membuka tab baru, yaitu Tab 3)
            print("[INFO] Menunggu tombol 'Review'...")
            review_btn = target_tab.locator("text=Review").first
            review_btn.wait_for(state="visible", timeout=20000)
            
            print("[INFO] Mengeklik tombol 'Review' dan menunggu tab baru terbuka...")
            with context.expect_page() as new_page_info:
                review_btn.click()
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
                print("✅ Konten halaman review terdeteksi sudah dimuat.")
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
                print("✅ Halaman sudah dalam Mode Edit!")
            except:
                try:
                    new_page.locator("text=Kirim").first.wait_for(state="visible", timeout=15000)
                    print("✅ Tombol Kirim terdeteksi. Halaman sudah dalam Mode Edit!")
                except Exception as e:
                    print(f"[WARN] Timeout menunggu konfirmasi Mode Edit: {e}")
            time.sleep(2)


            # 5. Klik bagian CATATAN di sidebar kiri
            print("[INFO] Mencari dan mengeklik 'CATATAN' di sidebar kiri...")
            # Berdasarkan gambar, CATATAN adalah item di sidebar navigasi kiri
            catatan_loc = None
            # Coba selektor nav sidebar
            for nav_sel in [
                "nav >> text=CATATAN", 
                "[class*='sidebar'] >> text=CATATAN",
                "[class*='nav'] >> text=CATATAN",
                "aside >> text=CATATAN",
                "text=CATATAN"
            ]:
                try:
                    loc = new_page.locator(nav_sel)
                    if loc.count() > 0 and loc.first.is_visible():
                        catatan_loc = loc.first
                        print(f"✅ Menemukan CATATAN dengan selektor: {nav_sel}")
                        break
                except:
                    pass
            
            if not catatan_loc:
                # Fallback: cari berdasarkan teks dan pilih yang di bagian kiri (x < 200)
                all_catatan = new_page.locator("text=CATATAN")
                for i in range(all_catatan.count()):
                    el = all_catatan.nth(i)
                    if el.is_visible():
                        box = el.bounding_box()
                        if box and box["x"] < 200:
                            catatan_loc = el
                            print(f"✅ Menemukan CATATAN di sidebar (x={box['x']})")
                            break
            
            if catatan_loc:
                catatan_loc.click()
                time.sleep(2)
                # Tunggu konten CATATAN form muncul di area tengah
                try:
                    new_page.locator("text=Tampilkan Anomali Usaha dan Keluarga").wait_for(state="visible", timeout=15000)
                except:
                    time.sleep(3)
                print("✅ Konten CATATAN berhasil dimuat.")
            else:
                print("[WARN] Tidak menemukan CATATAN di sidebar, mencoba scroll ke bawah halaman...")
                new_page.keyboard.press("End")
                time.sleep(2)

            # 6. Centang "Tampilkan Anomali Usaha dan Keluarga"
            toggle_checkbox_by_label(new_page, "Tampilkan Anomali Usaha dan Keluarga", True)
            time.sleep(1)

            # 7. Check & uncheck "Anomali diselesaikan oleh admin"
            toggle_checkbox_by_label(new_page, "Anomali diselesaikan oleh admin", True)
            time.sleep(1.5)
            toggle_checkbox_by_label(new_page, "Anomali diselesaikan oleh admin", False)

            time.sleep(1)

            # 8. Klik tombol KIRIM di kanan atas
            print("[INFO] Mengeklik tombol KIRIM...")
            kirim_btn = new_page.locator("text=KIRIM").first
            if kirim_btn.count() == 0:
                kirim_btn = new_page.locator("text=Kirim").first
            kirim_btn.click()
            time.sleep(2)

            # 9. Klik KIRIM di pop-up konfirmasi pertama
            print("[INFO] Konfirmasi pertama: Mengeklik KIRIM di modal...")
            modal_kirim = new_page.locator("div.ant-modal-content, div[role='dialog']").locator("text=KIRIM").first
            if modal_kirim.count() == 0:
                modal_kirim = new_page.locator("div.ant-modal-content, div[role='dialog']").locator("text=Kirim").first
            if modal_kirim.count() == 0:
                modal_kirim = new_page.locator("text=KIRIM").last
            modal_kirim.click()
            time.sleep(2)

            # 10. Klik KONFIRMASI di pop-up konfirmasi kedua
            print("[INFO] Konfirmasi kedua: Membaca status tombol KONFIRMASI...")
            confirm_btn = new_page.locator("div.ant-modal-content, div[role='dialog']").locator("text=KONFIRMASI").first
            if confirm_btn.count() == 0:
                confirm_btn = new_page.locator("div.ant-modal-content, div[role='dialog']").locator("text=Konfirmasi").first
            if confirm_btn.count() == 0:
                confirm_btn = new_page.locator("text=KONFIRSpecial").last  # Typo correction from confirming BPS modal
            if confirm_btn.count() == 0:
                confirm_btn = new_page.locator("text=KONFIRMASI").last

            if dry_run:
                print("[DRY_RUN] Menghentikan klik KONFIRMASI kirim anomali agar assignment tidak hangus.")
                new_page.keyboard.press("Escape")
                time.sleep(2)
            else:
                print("[LIVE] Mengeklik tombol KONFIRMASI...")
                confirm_btn.click()
                time.sleep(5)

            # 11. Klik tombol melayang kembali (panah/kembali) di kanan bawah
            print("[INFO] Kembali ke mode preview...")
            if not click_floating_button_and_wait(new_page, ["text=TINGGALKAN >> visible=true", "text=Tinggalkan >> visible=true"]):
                raise Exception("Gagal mengeklik floating button kembali")
            time.sleep(2)

            # Pop-up konfirmasi tinggalkan halaman
            print("[INFO] Memilih 'TINGGALKAN' pada pop-up konfirmasi...")
            tinggalkan_btn = new_page.locator("text=TINGGALKAN").first
            if tinggalkan_btn.count() == 0:
                tinggalkan_btn = new_page.locator("text=Tinggalkan").first
            tinggalkan_btn.click()
            time.sleep(5)

            # 12. Klik floating button (+) lagi, pilih Reject
            if not click_floating_button_and_wait(new_page, ["text=Reject >> visible=true", "text=REJECT >> visible=true", "text=Tolak >> visible=true"]):
                raise Exception("Gagal mengeklik floating button (+) di halaman preview")
            time.sleep(1)

            print("[INFO] Memilih menu 'Reject'...")
            reject_btn = new_page.locator("text=Reject >> visible=true").first
            if reject_btn.count() == 0:
                reject_btn = new_page.locator("text=REJECT >> visible=true").first
            if reject_btn.count() == 0:
                reject_btn = new_page.locator("text=Tolak >> visible=true").first
            reject_btn.wait_for(state="visible", timeout=10000)
            reject_btn.click()
            time.sleep(2)

            # Pop-up konfirmasi reject
            print("[INFO] Membaca tombol konfirmasi Reject...")
            confirm_reject_btn = new_page.locator("div.ant-modal-content, div[role='dialog']").locator("text=KONFIRMASI").first
            if confirm_reject_btn.count() == 0:
                confirm_reject_btn = new_page.locator("text=KONFIRMASI").last

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
