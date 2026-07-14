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

def check_page_state(page_obj):
    """
    Mengecek kondisi halaman secara global (Captcha, Sesi Habis, Error Fetch).
    Returns: "OK", "CAPTCHA_SOLVED", "ERROR_SESSION", "ERROR_FETCH", "ERROR_CAPTCHA_TIMEOUT"
    """
    import time
    try:
        content_text = page_obj.content()
        url = page_obj.url
        
        if "oauth_login" in url or "sso.bps" in url or "Lanjutkan dengan SSO" in content_text or "Selamat Datang Kembali" in content_text:
            print("[WARN] Terdeteksi Sesi Habis! Halaman ter-redirect ke Login SSO.")
            return "ERROR_SESSION"
            
        # 1.5 Cek Sesi Habis (Terlempar murni ke dashboard utama tanpa path assignment)
        if url.endswith("/app/") or url.endswith("/app") or ("/app/" in url and "/assignment" not in url):
            print("[WARN] Terlempar ke dashboard utama Fasih (Sesi / Token kemungkinan tidak valid atau API error).")
            return "ERROR_SESSION"
            
        # 2. Cek Error Fetch (Server BPS ngadat)
        if "There's some error" in content_text or "Failed to fetch" in content_text:
            print("[WARN] Terdeteksi Error Halaman ('There\'s some error / Failed to fetch').")
            return "ERROR_FETCH"
            
        # 3. Cek CAPTCHA
        if "perilaku yang tidak wajar pada perangkat anda" in content_text or "What code is in the image" in content_text or "support ID is:" in content_text:
            print("\n" + "!"*70)
            print("[WARNING] TERDETEKSI CAPTCHA ANTI-BOT DARI SERVER BPS!")
            print("[WARNING] Otomatisasi dijeda sementara.")
            print("[ACTION] Silakan buka browser Chrome yang sedang berjalan, dan isi kode Captcha secara manual.")
            print("!"*70 + "\n")
            
            import winsound
            for _ in range(3):
                winsound.Beep(1500, 500)
                time.sleep(0.1)
                
            print("[INFO] Menunggu Anda mensubmit CAPTCHA... (Timeout 5 menit)")
            for _ in range(60): # 60 * 5 detik = 300 detik (5 menit)
                try:
                    if "What code is in the image" not in page_obj.content():
                        print("[INFO] CAPTCHA berhasil dilewati! Melanjutkan otomatisasi...")
                        time.sleep(2)
                        return "CAPTCHA_SOLVED"
                except:
                    pass
                time.sleep(5)
            print("[ERROR] Timeout menunggu penyelesaian CAPTCHA.")
            return "ERROR_CAPTCHA_TIMEOUT"
            
    except Exception as e:
        pass
    return "OK"
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
        "--disable-infobars",
        "--test-type",
        "--hide-crash-restore-bubble",
        "--disable-session-crashed-bubble",
        "--disable-crash-reporter"
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
    try:
        label_loc = page_obj.locator(f"text={label_text}").first
        label_loc.wait_for(state="visible", timeout=15000)
        
        container = label_loc.locator("xpath=ancestor::div[.//input[@type='checkbox'] or .//*[@role='switch']][1]")
        if container.count() == 0:
            print(f"[WARN] Tidak dapat menemukan checkbox di sekitar label '{label_text}'.")
            return False
            
        checkbox_input = container.locator("input[type='checkbox'], [role='switch']").first
        
        is_checked = False
        if checkbox_input.count() > 0:
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
            
            # Coba cari elemen div visual yang biasa menjadi trigger click (Tailwind/Custom UI)
            visual_switch = container.locator("div[class*='cursor-pointer'], div[id$='-control']").first
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



def process_assignment(context, url, headless_mode, dry_run):
    print(f"\\n{'='*50}")
    print(f"[INFO] Memproses URL: {url}")
    print(f"{'='*50}")
    
    target_tab = None
    try:
        target_tab = context.new_page()
        if headless_mode:
            target_tab.set_viewport_size({"width": 1366, "height": 768})

        target_tab.goto(url, wait_until="domcontentloaded", timeout=60000)
        import time
        time.sleep(5)
        
        state1 = check_page_state(target_tab)
        if state1 != "OK" and state1 != "CAPTCHA_SOLVED":
            return state1
            
        print("[INFO] Menunggu detail assignment dimuat...")
        try:
            target_tab.locator("text=Informasi Assignment").first.wait_for(state="visible", timeout=15000)
        except:
            pass
            
        print("[INFO] Mengecek status assignment di halaman detail...")
        try:
            page_text = target_tab.evaluate("document.body.innerText").upper()
        except:
            page_text = target_tab.content().upper()
            
        # Abaikan bagian "Riwayat Assignment" agar tidak membaca status masa lalu
        if "RIWAYAT ASSIGNMENT" in page_text:
            page_text = page_text.split("RIWAYAT ASSIGNMENT")[0]
            
        # Validasi Ekstra Ketat: Hanya proses yang berstatus "Approved by pengawas" (di luar riwayat)
        if "APPROVED BY PENGAWAS" not in page_text:
            if "REJECTED BY" in page_text or "REJECTED" in page_text:
                print("[INFO] Status saat ini sudah REJECTED. Melewati assignment ini (ALREADY_REJECTED).")
                return "ALREADY_REJECTED"
            else:
                # Bisa jadi SUBMITTED BY Pencacah, DRAFT, dll
                print("[INFO] Status saat ini BUKAN 'Approved by pengawas' (UNPROCESSABLE_STATUS). Melewati...")
                return "UNPROCESSABLE_STATUS"
            
        print("[INFO] Menunggu tombol 'Review'...")

        review_btn = target_tab.locator("text=Review").first

        # Deteksi ALREADY_REJECTED
        try:
            review_btn.wait_for(state="visible", timeout=15000)
        except:
            print("[WARN] Tombol Review tidak ditemukan. Mencari FAB di preview tab ini (siapa tau tidak ada halaman review)...")
            # Coba cek apakah ada FAB (karena kalau sudah reject, FAB tidak ada)
            fab_check = target_tab.locator("button.fab-button, .ant-float-btn, button:has(svg)").first
            if fab_check.count() == 0:
                print("[INFO] Tidak ada tombol Review dan tidak ada FAB. Assignment kemungkinan sudah ALREADY_REJECTED.")
                return "ALREADY_REJECTED"
            else:
                print("[WARN] Tombol Review tidak ada, namun FAB ada? Ini di luar dugaan. Melanjutkan dengan asumsi Error.")
                return "ERROR_REVIEW_BTN"

        print("[INFO] Mengeklik tombol 'Review' dan menunggu tab baru terbuka...")
        with context.expect_page() as new_page_info:
            review_btn.click()
        new_page = new_page_info.value
        new_page.wait_for_load_state("domcontentloaded")
        if headless_mode:
            new_page.set_viewport_size({"width": 1366, "height": 768})
        preview_url = new_page.url
        print(f"[SUCCESS] Tab baru berhasil dimuat. URL: {preview_url}")

        print("[INFO] Menunggu konten form preview selesai dimuat...")
        # Polling untuk memastikannya form preview selesai dimuat secara penuh (ditandai dengan munculnya FAB)
        for _ in range(12): # Tunggu maksimal 12 * 5 = 60 detik
            state_preview = check_page_state(new_page)
            if state_preview != "OK" and state_preview != "CAPTCHA_SOLVED":
                return state_preview
                
            try:
                fab_locs = new_page.locator("button.fab-button, .ant-float-btn-menu-trigger, .ant-float-btn, button:has(svg)")
                is_fab_visible = False
                for i in range(fab_locs.count()):
                    if fab_locs.nth(i).is_visible():
                        is_fab_visible = True
                        break
                
                if is_fab_visible:
                    print("[OK] FAB terdeteksi. Form Preview telah selesai dimuat.")
                    break
            except:
                pass
            time.sleep(5)
        else:
            print("[WARN] Timeout 60 detik menunggu form Preview. Asumsi halaman stuck atau ALREADY_REJECTED.")
            new_page.close()
            return "ERROR_TIMEOUT_PREVIEW"
            
        time.sleep(2)

        edit_url = preview_url.rstrip("/") + "/edit"
        print(f"[INFO] Navigasi langsung ke Mode Edit: {edit_url}")
        new_page.goto(edit_url, wait_until="domcontentloaded", timeout=60000)
        
        print("[INFO] Menunggu konfirmasi Mode Edit dan memastikan tidak ada pesan error...")
        # Polling untuk memastikannya tidak stuck di "Failed to fetch" atau loading selamanya
        for _ in range(12): # Tunggu maksimal 12 * 5 = 60 detik
            state_edit = check_page_state(new_page)
            if state_edit != "OK" and state_edit != "CAPTCHA_SOLVED":
                return state_edit
                
            try:
                if new_page.locator("text=Mode Edit").count() > 0 and new_page.locator("text=Mode Edit").first.is_visible():
                    print("[OK] Halaman sudah dalam Mode Edit!")
                    break
                # Atau alternatif jika tombol Kirim muncul
                if new_page.locator("text=Kirim").count() > 0 and new_page.locator("text=Kirim").first.is_visible():
                    print("[OK] Tombol Kirim terdeteksi. Halaman sudah dalam Mode Edit!")
                    break
            except:
                pass
            time.sleep(5)
        else:
            print("[ERROR] Timeout 60 detik menunggu Mode Edit dimuat (mungkin loading terus/stuck).")
            return "ERROR_TIMEOUT_EDIT"
            
        time.sleep(2)

        print("[INFO] Mencari dan mengeklik 'CATATAN' di sidebar kiri...")
        catatan_loc = None
        for nav_sel in ["nav >> text=CATATAN", "[class*='sidebar'] >> text=CATATAN", "aside >> text=CATATAN", "text=CATATAN"]:
            try:
                loc = new_page.locator(nav_sel)
                if loc.count() > 0 and loc.first.is_visible():
                    catatan_loc = loc.first
                    break
            except:
                pass

        if not catatan_loc:
            all_catatan = new_page.locator("text=CATATAN")
            for i in range(all_catatan.count()):
                el = all_catatan.nth(i)
                if el.is_visible():
                    box = el.bounding_box()
                    if box and box["x"] < 200:
                        catatan_loc = el
                        break
                        
        if catatan_loc:
            catatan_loc.click()
            time.sleep(2)
            try:
                new_page.locator("text=Tampilkan Anomali Usaha dan Keluarga").wait_for(state="visible", timeout=15000)
            except:
                print("[ERROR] Konten CATATAN tidak termuat setelah diklik.")
                return "ERROR_TIMEOUT_CATATAN"
        else:
            print("[ERROR] CATATAN sidebar tidak ditemukan. Membatalkan proses agar tidak merusak form.")
            return "ERROR_NO_SIDEBAR"

        toggle_checkbox_by_label(new_page, "Tampilkan Anomali Usaha dan Keluarga", True)
        time.sleep(1)
        toggle_checkbox_by_label(new_page, "Anomali diselesaikan oleh admin", True)
        time.sleep(1.5)
        toggle_checkbox_by_label(new_page, "Anomali diselesaikan oleh admin", False)
        time.sleep(1)

        print("[INFO] Mengeklik tombol KIRIM...")
        kirim_btn = new_page.locator("button:has-text('KIRIM'):visible").first
        if kirim_btn.count() == 0:
            kirim_btn = new_page.locator("button:has-text('Kirim'):visible").first
        if kirim_btn.count() > 0:
            kirim_btn.click()
        time.sleep(2)

        print("[INFO] Konfirmasi pertama: pop-up KIRIM...")
        if dry_run:
            print("[DRY_RUN] Membatalkan pengiriman dengan mengeklik 'Batal' pada modal KIRIM.")
            batal_btn = new_page.locator("div.ant-modal-content, div[role='dialog']").locator("button:has-text('Batal'):visible").first
            if batal_btn.count() > 0:
                batal_btn.click()
            else:
                new_page.keyboard.press("Escape")
            time.sleep(2)
        else:
            print("[LIVE] Mengeklik KIRIM di modal pertama...")
            modal_kirim1 = new_page.locator("div.ant-modal-content, div[role='dialog'], div[role='alertdialog']").locator("button:has-text('Kirim'):visible, button:has-text('KIRIM'):visible").first
            if modal_kirim1.count() > 0:
                modal_kirim1.click()
                time.sleep(2)

            print("[LIVE] Mengeklik KONFIRMASI di modal kedua...")
            modal_kirim2 = new_page.locator("div.ant-modal-content, div[role='dialog'], div[role='alertdialog']").locator("button:has-text('Konfirmasi'):visible, button:has-text('KONFIRMASI'):visible").first
            if modal_kirim2.count() > 0:
                modal_kirim2.click()
                
                print("[INFO] Menunggu notifikasi 'Assignment berhasil disubmit' dari server...")
                try:
                    new_page.locator("text=Assignment berhasil disubmit").first.wait_for(state="visible", timeout=15000)
                    print("[OK] Notifikasi sukses disubmit muncul.")
                except:
                    print("[ERROR] Timeout/Gagal mendapatkan notifikasi sukses setelah submit Edit. Meminta ulangi...")
                    return "ERROR_SUBMIT_EDIT"

        print("[INFO] Kembali ke mode preview...")
        back_fab = new_page.locator("button[title*='Kembali']:visible").first
        if back_fab.count() > 0:
            back_fab.click(force=True)
        else:
            new_page.locator("#fasih-fab-root button").first.click(force=True)
        time.sleep(2)

        print("[INFO] Mengecek pop-up konfirmasi tinggalkan halaman...")
        leave_btn = new_page.locator("div[role='dialog'] button:has-text('Keluar'), div[role='alertdialog'] button:has-text('Keluar'), div[role='dialog'] button:has-text('Tinggalkan'), div[role='alertdialog'] button:has-text('Tinggalkan'), div[role='dialog'] button:has-text('Kembali')").first
        if leave_btn.count() > 0:
            leave_btn.click()
            time.sleep(5)

        if not click_floating_button_and_wait(new_page, ["button[class*='bg-destructive'] >> visible=true", "text=Reject >> visible=true", "text=REJECT >> visible=true", "text=Tolak >> visible=true"]):
            state_fab = check_page_state(new_page)
            if state_fab != "OK" and state_fab != "CAPTCHA_SOLVED":
                return state_fab
            return "ERROR_FAB_REJECT"

        time.sleep(1)
        print("[INFO] Mengeklik menu 'Reject'...")
        reject_btn = new_page.locator("button[class*='bg-destructive'], div.fab-item:has(span:has-text('Reject')) button, div.fab-item:has(span:has-text('Tolak')) button, button:has-text('Reject'), button:has-text('REJECT'), button:has-text('Tolak')").first
        reject_btn.wait_for(state="visible", timeout=10000)
        reject_btn.click()
        time.sleep(2)

        print("[INFO] Membaca tombol konfirmasi Reject...")
        confirm_reject_btn = new_page.locator("div.ant-modal-content, div[role='dialog'], div[role='alertdialog']").locator("text=KONFIRMASI").first
        if confirm_reject_btn.count() == 0:
            confirm_reject_btn = new_page.locator("text=KONFIRMASI").last

        if dry_run:
            print("[DRY_RUN] Menghentikan klik KONFIRMASI reject agar assignment tetap utuh.")
            new_page.keyboard.press("Escape")
            time.sleep(1)
        else:
            print("[LIVE] Mengeklik KONFIRMASI Reject...")
            confirm_reject_btn.click()
            
            print("[INFO] Menunggu respon dari server pasca-Reject...")
            try:
                new_page.locator("text=Berhasil reject assignment").first.wait_for(state="visible", timeout=15000)
                print("[OK] Notifikasi 'Berhasil reject assignment' muncul.")
            except:
                state_after_reject = check_page_state(new_page)
                if state_after_reject == "CAPTCHA_SOLVED":
                    print("[WARN] Terkena CAPTCHA persis saat submit Reject. Status reject kemungkinan gagal.")
                    return "ERROR_CAPTCHA_INTERRUPT"
                    
                if new_page.locator("text=failed to edit assignment approval").count() > 0 or new_page.locator("text=failed to edit").count() > 0:
                    print("[ERROR] Server menolak reject (failed to edit assignment approval). Meminta ulangi...")
                    return "ERROR_SERVER_REJECT"
                
                print("[ERROR] Tidak mendapatkan notifikasi sukses reject. Meminta ulangi...")
                return "ERROR_SERVER_REJECT"
                
            time.sleep(2)

        new_page.close()
        return "SUCCESS"

    except Exception as e:
        print(f"[ERROR] Assignment gagal diproses: {e}")
        try:
            if 'new_page' in locals() and new_page:
                new_page.close()
        except: pass
        return f"ERROR: {str(e)[:50]}"
    finally:
        if target_tab:
            try: target_tab.close()
            except: pass


def run_automation():
    import datetime
    import csv

    cfg = load_config()
    username = cfg.get("username", "")
    password = cfg.get("password", "")
    dry_run = cfg.get("dry_run", "True").strip().lower() == "true"
    headless = cfg.get("headless", "False").strip().lower() == "true"

    # Membaca daftar URL dari file assignment_links.txt
    target_urls = []
    links_file = os.path.join(current_dir, "assignment_links.txt")
    try:
        with open(links_file, "r", encoding="utf-8") as lf:
            for line in lf:
                url = line.strip()
                if url and url.startswith("http"):
                    target_urls.append(url)
    except FileNotFoundError:
        print(f"[ERROR] File {links_file} tidak ditemukan! Buat file tersebut dan isi dengan daftar URL.")
        return
        
    if not target_urls:
        print("[ERROR] Daftar URL kosong! Harap isi file assignment_links.txt.")
        return

    print("=== FASIH-SM ANOMALY & REJECT AUTOMATION (BATCH RUNNER) ===")
    print(f"[INFO] Total URL yang akan diproses: {len(target_urls)}")
    print(f"[INFO] Mode Dry Run (Simulasi): {dry_run}")
    print(f"[INFO] Mode Headless (Background): {headless}")

    if not vpn_auto_connect.is_vpn_connected():
        print("[WARN] VPN terputus. Mencoba menghubungkan VPN otomatis...")
        vpn_auto_connect.run_auto_vpn()
        if not vpn_auto_connect.is_vpn_connected():
            print("[ERROR] Gagal menyambungkan VPN.")
            return
    else:
        print("[SUCCESS] VPN BPS aktif/terhubung.")

    force_kill_cdp_chrome()
    headless_mode = headless or "--headless" in sys.argv
    chrome_proc = launch_real_chrome(headless=headless_mode)
    if not chrome_proc: return

    # Siapkan logger csv
    os.makedirs("../scrape_results", exist_ok=True)
    timestamp_str = datetime.datetime.now().strftime("%Y%md_%H%M%S")
    log_file = f"../scrape_results/reject_batch_log_{timestamp_str}.csv"
    with open(log_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "URL", "Status"])

    with sync_playwright() as p:
        try:
            print("[INFO] Menghubungkan ke browser Chrome via CDP...")
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            try: context.clear_cookies()
            except: pass

            sso_tab = context.pages[0] if len(context.pages) > 0 else context.new_page()
            if headless_mode: sso_tab.set_viewport_size({"width": 1366, "height": 768})

            print("[INFO] Menyiapkan sesi login BPS di Tab 1...")
            if not login_sso_tab(sso_tab, username, password):
                raise Exception("Gagal login SSO BPS.")

            for url in target_urls:
                status = process_assignment(context, url, headless_mode, dry_run)

                # Cek jika butuh login ulang
                if status == "ERROR_SESSION":
                    print("[WARN] Sesi terputus! Melakukan relogin...")
                    if not login_sso_tab(sso_tab, username, password):
                        print("[ERROR] Relogin gagal. Menghentikan batch.")
                        break
                    # Coba proses ulang url yang sama
                    status = process_assignment(context, url, headless_mode, dry_run)
                
                # Cek jika reject gagal karena interupsi server / CAPTCHA
                if status in ["ERROR_CAPTCHA_INTERRUPT", "ERROR_SERVER_REJECT", "ERROR_SUBMIT_EDIT"]:
                    print(f"[WARN] Status {status}. Mencoba ulang URL ini 1 kali lagi...")
                    status = process_assignment(context, url, headless_mode, dry_run)

                print(f"[RESULT] URL {url[-8:]} -> {status}")

                # Tulis log
                with open(log_file, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), url, status])

            print(f"\\n[SUCCESS] Seluruh URL selesai diproses. Laporan tersimpan di: {log_file}")

        except Exception as e:
            print(f"[ERROR] Automation terhenti mendadak: {e}")
        finally:
            print("[INFO] Menutup browser...")
            try: browser.close()
            except: pass
            if chrome_proc:
                try: chrome_proc.terminate()
                except: pass
            force_kill_cdp_chrome()

if __name__ == '__main__':
    run_automation()
