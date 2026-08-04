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

def check_page_state(page_obj):
    """
    Mengecek kondisi halaman secara global (Bot Detected, Captcha, Sesi Habis, Error Fetch).
    Returns: "OK", "CAPTCHA_SOLVED", "ERROR_SESSION", "ERROR_FETCH", "ERROR_CAPTCHA_TIMEOUT"
    """
    import time
    try:
        content_text = page_obj.content().lower()
        url = page_obj.url
        
        # 1. Cek Blokir Bot Detected (UTAMA: Harus dicek paling pertama sebelum mengecek URL!)
        if ("bot detected" in content_text or "koneksi anda sebagai bot" in content_text or 
            "perilaku yang tidak wajar pada koneksi anda" in content_text or
            "perilaku yang tidak wajar pada perangkat anda" in content_text):
            
            print("\n" + "!"*70)
            print("[WARNING] TERDETEKSI TAMPILAN BOT DETECTED DARI SERVER BPS!")
            print("[ACTION] MENGALAMI BLOKIR BOT. HARAP UBAH VPN/IP DAN TEKAN ENTER UNTUK LANJUT.")
            print("!"*70 + "\n")
            
            import winsound
            for _ in range(5):
                winsound.Beep(2000, 500)
            
            input("Press Enter to continue after changing IP/VPN...")
            return "ERROR_BOT_DETECTED"

        # 2. Cek CAPTCHA Gambar
        if "what code is in the image" in content_text or "support id is:" in content_text:
            print("\n" + "!"*70)
            print("[WARNING] TERDETEKSI CAPTCHA ANTI-BOT DARI SERVER BPS!")
            print("[ACTION] Silakan buka browser Chrome yang sedang berjalan, dan isi kode Captcha secara manual.")
            print("!"*70 + "\n")
            
            import winsound
            for _ in range(3):
                winsound.Beep(1500, 500)
                time.sleep(0.1)
                
            print("[INFO] Menunggu Anda mensubmit CAPTCHA... (Timeout 5 menit)")
            for _ in range(60):
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

        if "oauth_login" in url or "sso.bps" in url or "Lanjutkan dengan SSO" in content_text or "Selamat Datang Kembali" in content_text:
            print("[WARN] Terdeteksi Sesi Habis! Halaman ter-redirect ke Login SSO.")
            return "ERROR_SESSION"
            
        if "There's some error" in content_text or "Failed to fetch" in content_text:
            print("[WARN] Terdeteksi Error Halaman ('There\'s some error / Failed to fetch').")
            return "ERROR_FETCH"
            
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
                    if cmdline and any('chrome_automation_profile' in str(arg) or 'chrome_persistent_user_profile' in str(arg) or '--remote-debugging-port' in str(arg) for arg in cmdline):
                        proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except:
        pass
    time.sleep(1)

def wipe_chrome_profile_cookies():
    """Membersihkan cache dan cookie terinfeksi dari profil otomasi (chrome_automation_profile)."""
    user_data_dir = os.path.join(parent_dir, "chrome_automation_profile")
    if os.path.exists(user_data_dir):
        print(f"[INFO] Membersihkan cookie dan sesi terinfeksi dari {user_data_dir}...")
        try:
            import shutil
            shutil.rmtree(user_data_dir, ignore_errors=True)
            time.sleep(2)
            os.makedirs(user_data_dir, exist_ok=True)
            print("[SUCCESS] Profil otomasi berhasil dibersihkan (fresh session).")
        except Exception as e:
            print(f"[WARN] Gagal menghapus profil otomasi: {e}")

def play_alert_sound():
    """Memutar suara bip alarmperingatan untuk memanggil pengguna."""
    try:
        import winsound
        for _ in range(5):
            winsound.Beep(1000, 400)
            time.sleep(0.1)
    except:
        print("\a\a\a\a\a")

def launch_chrome_with_profile(headless=False):
    """Membuka Google Chrome secara otomatis dengan remote debugging port 9222 dan profil terisolasi (C:\\ChromeAutomationProfile)."""
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
        return None
        
    user_data_dir = r"C:\ChromeAutomationProfile"
    os.makedirs(user_data_dir, exist_ok=True)
    
    mode_text = "Headless" if headless else "GUI"
    print(f"[INFO] Meluncurkan Chrome otomatis (Mode: {mode_text}, Profile: {user_data_dir})...")
    
    args = [
        executable,
        "--remote-debugging-port=9222",
        f"--user-data-dir={user_data_dir}",
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-infobars",
        "--hide-crash-restore-bubble",
        "--disable-session-crashed-bubble",
        "--disable-crash-reporter"
    ]
    if headless:
        args.append("--headless=new")
    else:
        args.append("--start-maximized")
        
    args.append("about:blank")
    
    proc = subprocess.Popen(args)
    time.sleep(3)
    return proc

def connect_or_launch_chrome(p, headless=False):
    """Menghubungkan ke Chrome di port 9222. Jika belum terbuka, luncurkan Chrome secara otomatis."""
    try:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        print("[SUCCESS] Berhasil terhubung ke Chrome yang sedang berjalan!")
        return browser
    except:
        print("[INFO] Chrome di port 9222 belum aktif. Memulai peluncuran Chrome otomatis dengan profile C:\\ChromeAutomationProfile...")
        force_kill_cdp_chrome()
        proc = launch_chrome_with_profile(headless=headless)
        if not proc:
            raise Exception("Gagal meluncurkan peramban Chrome.")
            
        for attempt in range(10):
            try:
                browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
                print("[SUCCESS] Berhasil meluncurkan dan terhubung ke Chrome!")
                return browser
            except:
                time.sleep(1.5)
        raise Exception("Gagal terhubung ke Chrome setelah peluncuran otomatis.")

def apply_stealth_to_context(context):
    """Menyuntikkan skrip siluman anti-deteksi bot ke seluruh tab/page untuk menghapus jejak CDC Playwright."""
    try:
        context.set_extra_http_headers({
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"'
        })
    except: pass

    stealth_js = """
        // 1. Mask navigator.webdriver & automation flags
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        delete Object.getPrototypeOf(navigator).webdriver;
        
        // 2. Hapus seluruh jejak CDC/Playwright/Selenium di window & document
        for (const prop in window) {
            if (prop.match(/^cdc_/i) || prop.match(/^__playwright/i) || prop.match(/^__selenium/i)) {
                try { delete window[prop]; } catch(e){}
            }
        }
        for (const prop in document) {
            if (prop.match(/^cdc_/i) || prop.match(/^__playwright/i) || prop.match(/^__selenium/i)) {
                try { delete document[prop]; } catch(e){}
            }
        }
        
        // 3. Mask window.chrome & runtime
        window.chrome = {
            runtime: {
                OnInstalledReason: { INSTALL: "install", UPDATE: "update", CHROME_UPDATE: "chrome_update", SHARED_MODULE_UPDATE: "shared_module_update" },
                OnRestartRequiredReason: { APP_UPDATE: "app_update", OS_UPDATE: "os_update", PERIODIC: "periodic" },
                PlatformArch: { ARM: "arm", ARM64: "arm64", MIPS: "mips", MIPS64: "mips64", X86_32: "x86-32", X86_64: "x86-64" },
                PlatformNaclArch: { ARM: "arm", MIPS: "mips", MIPS64: "mips64", X86_32: "x86-32", X86_64: "x86-64" },
                PlatformOs: { ANDROID: "android", CROS: "cros", LINUX: "linux", MAC: "mac", OPENBSD: "openbsd", WIN: "win" }
            },
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };
        
        // 4. Fake navigator.languages & plugins
        Object.defineProperty(navigator, 'languages', { get: () => ['id-ID', 'id', 'en-US', 'en'] });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        
        // 5. Mask permissions query
        if (navigator.permissions && navigator.permissions.query) {
            const origQuery = navigator.permissions.query;
            navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                origQuery(parameters)
            );
        }
    """
    try:
        context.add_init_script(stealth_js)
    except: pass



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
        
def check_switchbox_state(page_obj, label_text):
    """Mengecek apakah switchbox dengan label tertentu aktif (ON/checked) atau mati (OFF/unchecked)."""
    try:
        # 1. Cek via selector presisi: id="switch-*-control", status dari thumb translate-x-4
        priority_selectors = [
            "[id$='-control'][id*='switch']",
            "div[class*='data-checked:bg-primary']"
        ]
        for sw_sel in priority_selectors:
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
                            if (thumb) return (thumb.getAttribute('class') || '').includes('translate-x-4');
                            return false;
                        }
                    """)
                    return bool(data_checked)
            except: pass
        
        # 2. Fallback: cari via label teks
        label_loc = page_obj.locator(f"text={label_text}").first
        if label_loc.count() > 0 and label_loc.is_visible():
            container = label_loc.locator("xpath=ancestor::div[.//input[@type='checkbox'] or .//*[@role='switch'] or contains(@class, 'switch')][1]")
            if container.count() > 0:
                sw = container.locator("[id$='-control'][id*='switch'], input[type='checkbox'], button[role='switch'], .ant-switch, [class*='switch']").first
                if sw.count() > 0:
                    is_checked = False
                    try: is_checked = sw.is_checked()
                    except: pass
                    aria_checked = sw.get_attribute("aria-checked") == "true"
                    cls = sw.get_attribute("class") or ""
                    has_class_checked = "ant-switch-checked" in cls or "checked" in cls or "bg-primary" in cls or "translate-x-4" in cls
                    if is_checked or aria_checked or has_class_checked:
                        return True
    except Exception as e:
        print(f"[WARN] Kendala cek status switchbox '{label_text}': {e}")
    return False


def has_unchecked_anomaly_in_sidebar(page_obj):
    """Mengecek apakah ada bagian anomali di sidebar kiri yang belum tercentang (tidak memiliki icon centang hijau ✓)."""
    try:
        result = page_obj.evaluate("""() => {
            // Gunakan div[title] langsung (dari Outer HTML nyata BPS)
            // ANOMALI USAHA: div[title='ANOMALI USAHA'], ANOMALI KELUARGA: div[title='ANOMALI KELUARGA']
            // Ikon centang hijau: svg.tw:text-success (class dari Outer HTML)
            
            const anomaliTitles = ['ANOMALI USAHA', 'ANOMALI KELUARGA'];
            let uncheckedItems = [];

            for (const titleAttr of anomaliTitles) {
                const el = document.querySelector(`div[title='${titleAttr}']`);
                if (!el) continue;
                
                // Cari row container terdekat
                const row = el.closest('[title]') || el.parentElement || el;
                
                // Cek ikon centang hijau (tw:text-success atau warna success)
                const svgs = Array.from(row.querySelectorAll('svg, path'));
                let hasCheck = false;
                for (let s of svgs) {
                    const style = window.getComputedStyle(s);
                    const cls = (s.getAttribute('class') || '').toLowerCase();
                    const color = (style.color || '').toLowerCase();
                    const stroke = (s.getAttribute('stroke') || '').toLowerCase();
                    const fill = (s.getAttribute('fill') || '').toLowerCase();
                    if (
                        cls.includes('success') || cls.includes('green') || cls.includes('check') ||
                        color.includes('rgb(34, 197, 94)') || color.includes('rgb(16, 185, 129)') ||
                        color.includes('rgb(82, 196, 26)') || color.includes('rgb(20, 184, 166)') ||
                        stroke.includes('green') || stroke.includes('#22c55e') || stroke.includes('#10b981') ||
                        fill.includes('green') || fill.includes('#22c55e') || fill.includes('#10b981')
                    ) {
                        hasCheck = true;
                        break;
                    }
                }
                if (!hasCheck) uncheckedItems.push(titleAttr);
            }

            // Fallback: jika div[title] tidak ditemukan, cek via sidebar text
            if (uncheckedItems.length === 0) {
                const sidebar = document.querySelector('aside') || document.querySelector('[class*="sidebar"]') || document.querySelector('nav');
                if (sidebar) {
                    const allLabels = Array.from(sidebar.querySelectorAll('div[title], span, div, a')).filter(el => {
                        const text = (el.getAttribute('title') || el.innerText || '').trim();
                        return text.length > 3 && text.length < 60 && (text.toUpperCase().includes('ANOMALI'));
                    });
                    for (let el of allLabels) {
                        const text = (el.getAttribute('title') || el.innerText || '').trim().toUpperCase();
                        if (!text.includes('ANOMALI')) continue;
                        const row = el.closest('[class*="flex"][class*="cursor"]') || el.parentElement || el;
                        const svgs = Array.from(row.querySelectorAll('svg, path'));
                        let hasCheck = false;
                        for (let s of svgs) {
                            const style = window.getComputedStyle(s);
                            const cls = (s.getAttribute('class') || '').toLowerCase();
                            const color = (style.color || '').toLowerCase();
                            if (cls.includes('success') || cls.includes('green') || cls.includes('check') ||
                                color.includes('rgb(34, 197, 94)') || color.includes('rgb(16, 185, 129)')) {
                                hasCheck = true; break;
                            }
                        }
                        if (!hasCheck && !uncheckedItems.includes(text)) uncheckedItems.push(text);
                    }
                }
            }

            if (uncheckedItems.length > 0) {
                return { has_unchecked: true, detail: `Item tanpa centang hijau: ${uncheckedItems.join(', ')}` };
            }
            return { has_unchecked: false, detail: "Semua anomali di sidebar terkonfirmasi tercentang hijau" };
        }""")

        if result.get("has_unchecked", True):
            print(f"[INFO] Terdeteksi anomali belum tercentang di sidebar ({result.get('detail', '')}). Diperlukan REJECT!")
            return True
        else:
            print("[INFO] Seluruh anomali di sidebar terkonfirmasi sudah tercentang hijau (✓). Assignment ini aman, dilewati.")
            return False

    except Exception as e:
        print(f"[WARN] Kendala evaluasi sidebar anomali: {e}. Mengasumsikan ada anomali untuk direject.")
        return True

def click_edit_fab_button(page_obj):
    """Mencari dan mengeklik tombol Edit Assignment (ikon pensil / tabler-icon-edit di float bar kanan)."""
    print("[INFO] Mencari dan mengeklik tombol FAB 'Edit Assignment' (Pensil/tabler-icon-edit)...")
    
    # 1. Selector presisi dari Outer HTML: tombol dengan ikon tabler-icon-edit, class f:bg-primary
    #    data-tsd-source="/src/.../draggable-toolbar.tsx:138:15" dan bukan f:bg-destructive
    priority_selectors = [
        "button:has(.tabler-icon-edit)",
        "[data-tsd-source*='draggable-toolbar.tsx:138']:has(.tabler-icon-edit)",
        "button.f\\:bg-primary:has(svg.tabler-icon-edit)"
    ]
    for sel in priority_selectors:
        try:
            loc = page_obj.locator(sel)
            for i in range(loc.count()):
                el = loc.nth(i)
                if el.is_visible():
                    box = el.bounding_box()
                    if box and box['x'] > 700:
                        print(f"[OK] Menemukan tombol Edit FAB via selector presisi '{sel}' di x={box['x']}")
                        human_click(page_obj, el)
                        return True
        except: pass

    # 2. Selector fallback berbasis class CSS
    fallback_selectors = [
        "button[title*='Edit']",
        "button[aria-label*='Edit']",
        "a[title*='Edit']",
        "button.bg-orange-500",
        "button[class*='orange']",
        "button[class*='amber']",
        "button[class*='warning']"
    ]
    for sel in fallback_selectors:
        try:
            loc = page_obj.locator(sel)
            for i in range(loc.count()):
                el = loc.nth(i)
                if el.is_visible():
                    box = el.bounding_box()
                    if box and box['x'] > 700:
                        print(f"[OK] Menemukan tombol Edit FAB via fallback '{sel}' di x={box['x']}")
                        human_click(page_obj, el)
                        return True
        except: pass

    # 3. Fallback posisi: tombol paling bawah di kuadran kanan layar (bukan destructive)
    try:
        right_btns = []
        all_btns = page_obj.locator("button:visible")
        for i in range(all_btns.count()):
            b = all_btns.nth(i)
            box = b.bounding_box()
            if box and box['x'] > 750 and box['y'] > 200:
                cls = (b.get_attribute("class") or "").lower()
                if "destructive" not in cls:
                    right_btns.append((box['y'], b))
        if right_btns:
            right_btns.sort(key=lambda item: item[0], reverse=True)
            print(f"[INFO] Fallback posisi: Mengeklik tombol paling bawah non-destructive di y={right_btns[0][0]}")
            human_click(page_obj, right_btns[0][1])
            return True
    except Exception as e:
        print(f"[WARN] Kendala fallback klik Edit FAB: {e}")
        
    return False


def click_reject_fab_button(page_obj):
    """Mencari dan mengeklik tombol Reject (ikon X / tabler-icon-x dengan class f:bg-destructive di float bar)."""
    print("[INFO] Mencari dan mengeklik tombol FAB 'Reject' (X/tabler-icon-x/destructive)...")
    
    # 1. Selector presisi dari Outer HTML: tombol dengan ikon tabler-icon-x, class f:bg-destructive
    priority_selectors = [
        "button:has(.tabler-icon-x)",
        "[data-tsd-source*='draggable-toolbar.tsx:138']:has(.tabler-icon-x)",
        "button[class*='bg-destructive']:has(svg.tabler-icon-x)"
    ]
    for sel in priority_selectors:
        try:
            loc = page_obj.locator(sel)
            for i in range(loc.count()):
                el = loc.nth(i)
                if el.is_visible():
                    box = el.bounding_box()
                    if box and box['x'] > 700:
                        print(f"[OK] Menemukan tombol Reject FAB via selector presisi '{sel}' di x={box['x']}")
                        human_click(page_obj, el)
                        return True
        except: pass

    # 2. Fallback berbasis class CSS
    fallback_selectors = [
        "button[title*='Reject']",
        "button[aria-label*='Reject']",
        "button[title*='Tolak']",
        "button:has-text('Reject')",
        "button:has-text('Tolak')",
        "button.bg-destructive",
        "button.bg-red-500",
        "button[class*='destructive']",
        "button[class*='red']",
        "button[class*='danger']"
    ]
    for sel in fallback_selectors:
        try:
            loc = page_obj.locator(sel)
            for i in range(loc.count()):
                el = loc.nth(i)
                if el.is_visible():
                    box = el.bounding_box()
                    if box and box['x'] > 700:
                        print(f"[OK] Menemukan tombol Reject FAB via fallback '{sel}' di x={box['x']}")
                        human_click(page_obj, el)
                        return True
        except: pass

    # 3. Fallback posisi: tombol ber-class destructive di kuadran kanan
    try:
        right_btns = []
        all_btns = page_obj.locator("button:visible")
        for i in range(all_btns.count()):
            b = all_btns.nth(i)
            box = b.bounding_box()
            if box and box['x'] > 750 and box['y'] > 200:
                right_btns.append((box['y'], b))
        if right_btns:
            right_btns.sort(key=lambda item: item[0])
            for y, btn in right_btns:
                cls = (btn.get_attribute("class") or "").lower()
                title = (btn.get_attribute("title") or "").lower()
                if "destructive" in cls or "red" in cls or "danger" in cls or "reject" in title or "tolak" in title:
                    print(f"[INFO] Fallback posisi: Mengeklik tombol Reject berdasarkan class di y={y}")
                    human_click(page_obj, btn)
                    return True
            if len(right_btns) >= 2:
                print(f"[INFO] Fallback posisi: Mengeklik tombol ke-2 di float bar kanan di y={right_btns[1][0]}")
                human_click(page_obj, right_btns[1][1])
                return True
    except Exception as e:
        print(f"[WARN] Kendala fallback klik Reject FAB: {e}")
        
    return False

def toggle_checkbox_by_label(page_obj, label_text, target_state=True):
    """Mencari checkbox berdasarkan label teks dan menyetel statusnya."""
    print(f"[INFO] Mengatur checkbox '{label_text}' ke: {target_state}")
    
    # 1. Coba selector presisi dari Outer HTML:
    #    Switchbox memiliki id="switch-*-control" dan class 'tw:data-checked:bg-primary'
    #    Status ON: elemen thumb di dalam memiliki class 'tw:data-checked:translate-x-4'
    priority_switch_selectors = [
        f"[id$='-control'][id*='switch']",          # id="switch-cl-14-control" (pattern stabil)
        f"div[class*='data-checked:bg-primary']",   # class unik dari Outer HTML switchbox
    ]
    for sw_sel in priority_switch_selectors:
        try:
            # Cari yang dekat dengan teks label
            loc = page_obj.locator(f"xpath=//div[contains(normalize-space(.),'{label_text}')]").locator(sw_sel)
            if loc.count() == 0:
                loc = page_obj.locator(sw_sel)
            if loc.count() > 0 and loc.first.is_visible():
                sw = loc.first
                # Cek status: data-checked attribute atau translate-x pada thumb
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
                print(f"   -> Switchbox '{label_text}' status saat ini: {'ON' if is_checked else 'OFF'}, target: {'ON' if target_state else 'OFF'}")
                if is_checked != target_state:
                    human_click(page_obj, sw)
                    time.sleep(1)
                    print(f"   -> Switchbox berhasil di-toggle.")
                else:
                    print(f"   -> Status switchbox sudah sesuai.")
                return True, is_checked
        except: pass

    # 2. Coba XPath relatif berdasarkan konten teks label
    relative_switch_xpaths = [
        f"xpath=//div[contains(normalize-space(.),'{label_text}')]//div[@id[contains(.,'switch') and contains(.,'-control')]]",
        f"xpath=//div[contains(.,'{label_text}')]//div[@role='switch']",
        f"xpath=//div[contains(.,'{label_text}')]//button[@role='switch']",
        f"xpath=//div[contains(.,'{label_text}')]//input[@type='checkbox']",
        f"xpath=//label[contains(.,'{label_text}')]//input"
    ]
    for rel_xp in relative_switch_xpaths:
        try:
            loc = page_obj.locator(rel_xp)
            if loc.count() > 0 and loc.first.is_visible():
                sw = loc.first
                class_attr = (sw.get_attribute("class") or "") + " " + (sw.get_attribute("aria-checked") or "")
                is_checked = "true" in class_attr.lower() or "checked" in class_attr.lower() or "active" in class_attr.lower()
                if is_checked != target_state:
                    sw.click(force=True)
                    time.sleep(1)
                return True, target_state
        except: pass

    try:
        label_loc = page_obj.locator(f"text={label_text}").first
        label_loc.wait_for(state="visible", timeout=15000)
        
        container = label_loc.locator("xpath=ancestor::div[.//input[@type='checkbox'] or .//*[@role='switch']][1]")
        if container.count() == 0:
            print(f"[WARN] Tidak dapat menemukan checkbox di sekitar label '{label_text}'.")
            return False, False
            
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
            
            visual_switch = container.locator("div[class*='cursor-pointer'], div[id$='-control']").first
            if visual_switch.count() > 0:
                visual_switch.click(force=True)
            else:
                checkbox_input.click(force=True)
            time.sleep(1)
        else:
            print(f"   -> Status sudah sesuai.")
        return True, is_checked
    except Exception as e:
        print(f"[WARN] Gagal menyetel checkbox '{label_text}': {e}")
        return False, False

def is_login_page(page_obj):
    """Mengecek apakah halaman saat ini adalah halaman landing/form login SSO dengan memeriksa innerText rendered."""
    try:
        url = page_obj.url
        if "oauth_login" in url or "sso.bps" in url or "authorization" in url:
            return True
            
        try:
            body_text = page_obj.evaluate("() => document.body ? document.body.innerText : ''")
        except:
            body_text = page_obj.content()
            
        if any(txt in body_text for txt in ["Selamat Datang Kembali", "Masuk ke akun Anda", "Lanjutkan dengan SSO", "Lanjutkan dengan SSO Eksternal"]):
            return True
        return False
    except:
        return False

def login_sso_tab(sso_tab, username, password):
    """Mengakses https://fasih-sm.bps.go.id/app, mengeklik 'Lanjutkan dengan SSO', mengisi kredensial di sso.bps.go.id, dan menunggu redirect ke dashboard."""
    print("[INFO] Memeriksa status halaman login SSO di Tab 1...")
    
    current_url = sso_tab.url
    if "fasih-sm.bps.go.id/app" not in current_url and "sso.bps" not in current_url:
        print("[INFO] Membuka portal Fasih-SM BPS (https://fasih-sm.bps.go.id/app)...")
        try:
            sso_tab.goto("https://fasih-sm.bps.go.id/app", wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"[WARN] Gagal memuat portal Fasih-SM: {e}")
            return False
    
    time.sleep(3)
    
    # Cek jika sudah login di dashboard (misal ada menu nav / aside / list survey)
    if not is_login_page(sso_tab) and "fasih-sm.bps.go.id/app" in sso_tab.url:
        print("[SUCCESS] Sesi login terdeteksi masih aktif di Dashboard Fasih-SM.")
        return True

    print("[INFO] Sesi login kosong. Memulai alur login SSO BPS via https://fasih-sm.bps.go.id/app...")
    
    for attempt in range(12):
        curr_url = sso_tab.url
        
        # 1. Cek jika sudah di dashboard (bukan login page, dan di fasih-sm.bps.go.id/app)
        if not is_login_page(sso_tab) and "fasih-sm.bps.go.id" in curr_url and "sso.bps" not in curr_url and "oauth" not in curr_url:
            print("[SUCCESS] Login berhasil! Sudah berada di Dashboard Fasih-SM BPS.")
            try:
                time.sleep(2)
                close_btn = sso_tab.locator("button.ant-modal-close, .ant-modal-close-x, text=Jangan tampilkan lagi, button:has-text('Tutup')").first
                if close_btn.count() > 0 and close_btn.is_visible():
                    close_btn.click(force=True)
            except: pass
            return True

        # Jika ada pesan Bot Detected
        st = check_page_state(sso_tab)
        if st == "ERROR_BOT_DETECTED":
            print("[ERROR] Terdeteksi Bot Detected saat login SSO!")
            return False

        # 2. Jika di halaman landing SSO fasih-sm.bps.go.id/app (ada tombol Lanjutkan dengan SSO)
        if "sso.bps.go.id" not in curr_url and is_login_page(sso_tab):
            print(f"[INFO] Siklus {attempt+1}: Mencari dan mengeklik tombol 'Lanjutkan dengan SSO'...")
            try:
                btn = sso_tab.locator("xpath=//button[contains(., 'Lanjutkan dengan SSO') and not(contains(., 'Eksternal'))] | //a[contains(., 'Lanjutkan dengan SSO') and not(contains(., 'Eksternal'))] | //button[contains(., 'SSO')] | //a[contains(@href, 'oauth2')]").first
                if btn.count() > 0 and btn.is_visible():
                    print(f"[OK] Menemukan tombol SSO BPS ('{btn.inner_text().strip()}'). Mengeklik...")
                    btn.evaluate("e => { e.click(); e.dispatchEvent(new MouseEvent('click', {bubbles: true})); }")
                    time.sleep(1)
                    try:
                        sso_tab.wait_for_url(lambda u: "sso.bps" in u or "oauth" in u, timeout=8000)
                        print(f"[INFO] Ter-redirect ke URL login SSO: {sso_tab.url}")
                    except:
                        print("[INFO] Navigasi manual ke endpoint authorization...")
                        sso_tab.goto("https://fasih-sm.bps.go.id/oauth2/authorization/ics", wait_until="domcontentloaded")
                else:
                    print("[INFO] Tombol SSO belum terlihat, menavigasi langsung ke endpoint authorization...")
                    sso_tab.goto("https://fasih-sm.bps.go.id/oauth2/authorization/ics", wait_until="domcontentloaded")
            except Exception as e:
                print(f"[WARN] Gagal mengeklik tombol SSO: {e}")
            time.sleep(5)

        # 3. Jika sudah ter-redirect ke sso.bps.go.id (form username/password)
        elif "sso.bps.go.id" in curr_url:
            print(f"[INFO] Siklus {attempt+1}: Di halaman login sso.bps.go.id. Mengisi kredensial username & password...")
            try:
                if sso_tab.locator('input[name="username"]').is_visible():
                    sso_tab.fill('input[name="username"]', username, timeout=5000)
                    sso_tab.fill('input[name="password"]', password, timeout=5000)
                    print("[INFO] Mengeklik tombol Log In / Submit SSO...")
                    sso_tab.click('button[type="submit"], input[type="submit"], button:has-text("Log In"), button:has-text("Masuk")', no_wait_after=True, timeout=5000)
            except Exception as e:
                print(f"[WARN] Kendala pengisian form SSO: {e}")
            time.sleep(8)
            
    time.sleep(3)
    if not is_login_page(sso_tab) and "fasih-sm.bps.go.id" in sso_tab.url:
        print("[SUCCESS] Login berhasil pada Tab 1!")
        return True
        
    print(f"[ERROR] Gagal login SSO BPS: URL terakhir {sso_tab.url}")
    return False
def process_assignment(main_tab, url, headless_mode, dry_run):
    print(f"\n{'='*50}")
    print(f"[INFO] Memproses URL (di tab yang sama): {url}")
    print(f"{'='*50}")
    
    if main_tab.is_closed():
        main_tab = main_tab.context.new_page()
        if headless_mode:
            main_tab.set_viewport_size({"width": 1366, "height": 768})

    review_tab = None
    try:
        # Step 1: Di Tab baru, buka halaman Assignment Detail
        max_retries = 3
        goto_success = False
        for attempt in range(max_retries):
            try:
                main_tab.goto(url, wait_until="domcontentloaded", timeout=60000)
                goto_success = True
                break
            except Exception as e:
                print(f"[WARN] Gagal memuat halaman assignment di Tab 1 (Percobaan {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    import vpn_auto_connect
                    if not vpn_auto_connect.is_vpn_connected():
                        print("[WARN] VPN terputus! Mencoba menyambungkan kembali...")
                        vpn_auto_connect.run_auto_vpn()
                    time.sleep(10)
                    
        if not goto_success:
            return "ERROR_GOTO_FAILED"

        time.sleep(2)
        state1 = check_page_state(main_tab)
        if state1 != "OK" and state1 != "CAPTCHA_SOLVED":
            return state1
            
        print("[INFO] Tab 1: Menunggu konten assignment selesai dimuat...")
        # Cek apakah spinner yang benar-benar visible di layar (kebal terhadap tag HTML statis ant-spin-spinning)
        for _ in range(10):
            try:
                visible_spinner = main_tab.locator(".ant-spin-spinning:visible, text='Memuat Halaman...':visible")
                if visible_spinner.count() > 0 and visible_spinner.first.is_visible():
                    time.sleep(0.5)
                else:
                    break
            except:
                break

        try:
            # Selector presisi: span status dari assignment-action.tsx:110
            status_span = main_tab.locator("[data-tsd-source*='assignment-action.tsx:110']").first
            if status_span.count() > 0:
                status_span.wait_for(state="visible", timeout=10000)
            else:
                main_tab.locator("text=Approved by pengawas, text=APPROVED, text=REJECTED, text=STATUS ASSIGNMENT").first.wait_for(state="visible", timeout=10000)
        except: pass
            
        print("[INFO] Tab 1: Mengecek status assignment di halaman detail...")
        
        # Cek status via selector presisi terlebih dahulu
        status_text_precise = ""
        try:
            status_span = main_tab.locator("[data-tsd-source*='assignment-action.tsx:110']").first
            if status_span.count() > 0 and status_span.is_visible():
                status_text_precise = (status_span.inner_text() or "").strip().upper()
                print(f"[INFO] Tab 1: Status terdeteksi via selector presisi: '{status_text_precise}'")
        except: pass
        
        if status_text_precise:
            # Gunakan status presisi langsung
            if "APPROVED BY PENGAWAS" in status_text_precise or "APPROVED BY" in status_text_precise:
                pass  # Lanjutkan ke Review
            elif "REJECTED" in status_text_precise:
                print("[INFO] Status saat ini sudah REJECTED. Melewati assignment ini (ALREADY_REJECTED).")
                return "ALREADY_REJECTED"
            else:
                print(f"[INFO] Status saat ini '{status_text_precise}' BUKAN 'Approved by pengawas' (UNPROCESSABLE_STATUS). Melewati...")
                return "UNPROCESSABLE_STATUS"
        else:
            # Fallback: baca seluruh innerText halaman
            try:
                page_text = main_tab.evaluate("document.body.innerText").upper()
            except:
                page_text = main_tab.content().upper()
                
            import re
            page_text_normalized = re.sub(r'\s+', ' ', page_text)
                
            if "RIWAYAT ASSIGNMENT" in page_text_normalized:
                text_before_history = page_text_normalized.split("RIWAYAT ASSIGNMENT")[0]
            else:
                text_before_history = page_text_normalized
                
            if "APPROVED BY PENGAWAS" not in text_before_history:
                fallback_check = False
                try:
                    if "APPROVED BY PENGAWAS" in page_text_normalized[:200]:
                        fallback_check = True
                    if not fallback_check:
                        idx = page_text_normalized.find("STATUS ASSIGNMENT")
                        if idx != -1:
                            status_snippet = page_text_normalized[idx:idx+100]
                            if "APPROVED BY PENGAWAS" in status_snippet:
                                fallback_check = True
                except: pass
                    
                if not fallback_check:
                    if "REJECTED BY" in page_text_normalized or "REJECTED" in page_text_normalized:
                        print("[INFO] Status saat ini sudah REJECTED. Melewati assignment ini (ALREADY_REJECTED).")
                        return "ALREADY_REJECTED"
                    else:
                        print("[INFO] Status saat ini BUKAN 'Approved by pengawas' (UNPROCESSABLE_STATUS). Melewati...")
                        return "UNPROCESSABLE_STATUS"
            
        print("[INFO] Tab 1: Menunggu tombol 'Review'...")
        # Selector presisi: data-tsd-source dari assignment-action.tsx:142, atau berdasarkan ikon telegram SVG
        review_btn = main_tab.locator("[data-tsd-source*='assignment-action.tsx:142']").first
        if review_btn.count() == 0 or not review_btn.is_visible():
            review_btn = main_tab.locator("button:has(.tabler-icon-brand-telegram)").first
        if review_btn.count() == 0 or not review_btn.is_visible():
            review_btn = main_tab.locator("button:has-text('Review')").first

        try:
            review_btn.wait_for(state="visible", timeout=15000)
        except:
            print("[WARN] Tombol Review tidak ditemukan di Tab 1. Assignment kemungkinan sudah ALREADY_REJECTED.")
            return "ALREADY_REJECTED"

        print("[INFO] Tab 1: Mengeklik tombol 'Review' (secara alami/humanizer) untuk membuka Halaman Review di Tab 2...")
        with main_tab.context.expect_page() as new_page_info:
            human_click(main_tab, review_btn)
        review_tab = new_page_info.value
        apply_stealth_to_context(review_tab.context)
        review_tab.wait_for_load_state("domcontentloaded")
        if headless_mode:
            review_tab.set_viewport_size({"width": 1366, "height": 768})

        print(f"[SUCCESS] Tab 2 (Review) berhasil dimuat. URL: {review_tab.url}")

        print("[INFO] Tab 2: Menunggu konten form review selesai dimuat...")
        for _ in range(10):
            state_preview = check_page_state(review_tab)
            if state_preview != "OK" and state_preview != "CAPTCHA_SOLVED":
                return state_preview
                
            try:
                fab_locs = review_tab.locator("button.fab-button, .ant-float-btn-menu-trigger, .ant-float-btn, button:has(svg)")
                if fab_locs.count() > 0 and fab_locs.first.is_visible():
                    print("[OK] Tab 2: FAB terdeteksi. Form Review telah selesai dimuat.")
                    break
            except: pass
            time.sleep(1)
        else:
            print("[WARN] Timeout menunggu form Review di Tab 2.")
            return "ERROR_TIMEOUT_PREVIEW"

        print("[INFO] Tab 2: Membuka panel CATATAN di Halaman Review untuk inspeksi awal...")
        catatan_loc = None
        for nav_sel in [
            "div[title='CATATAN']",
            "[title='CATATAN']",
            "nav >> text=CATATAN",
            "[class*='sidebar'] >> text=CATATAN",
            "aside >> text=CATATAN",
            "text=CATATAN"
        ]:
            try:
                loc = review_tab.locator(nav_sel)
                if loc.count() > 0 and loc.first.is_visible():
                    catatan_loc = loc.first
                    break
            except: pass

        if not catatan_loc:
            all_catatan = review_tab.locator("text=CATATAN")
            for i in range(all_catatan.count()):
                el = all_catatan.nth(i)
                if el.is_visible():
                    box = el.bounding_box()
                    if box and box["x"] < 350:
                        catatan_loc = el
                        break
                        
        if catatan_loc:
            catatan_loc.click()
            time.sleep(2)

        # Inspeksi status Switchbox di Tab 2 (Halaman Review)
        is_switch_active = check_switchbox_state(review_tab, "Tampilkan Anomali Usaha dan Keluarga")
        
        if is_switch_active:
            print("[INFO] Tab 2: Switchbox 'Tampilkan Anomali Usaha dan Keluarga' SUDAH AKTIF (ON) sejak awal di Halaman Review.")
            print("[INFO] Tab 2: Memeriksa apakah ada anomali di sidebar yang belum tercentang (✓)...")
            has_unresolved = has_unchecked_anomaly_in_sidebar(review_tab)
            
            if not has_unresolved:
                print("[INFO] Tab 2: Seluruh anomali di sidebar telah tercentang lengkap (✓). Assignment ini sudah selesai diperbaiki, dilewati!")
                try: review_tab.close()
                except: pass
                return "ALREADY_PROCESSED"
            else:
                print("[INFO] Tab 2: Terdeteksi anomali belum tercentang di sidebar. Melanjutkan proses Reject langsung dari Halaman Review...")
        else:
            print("[INFO] Tab 2: Switchbox 'Tampilkan Anomali Usaha dan Keluarga' MASIH MATI (OFF) di Halaman Review.")
            print("[INFO] Tab 2: Mengaktifkan switchbox memerlukan Mode Edit. Membuka Mode Edit via FAB...")
            
            edit_clicked = click_edit_fab_button(review_tab)
            if not edit_clicked:
                print("[INFO] Tab 2: Fallback: Navigasi URL Mode Edit secara langsung...")
                edit_url = review_tab.url.rstrip("/").replace("/edit", "") + "/edit"
                review_tab.goto(edit_url, wait_until="domcontentloaded", timeout=60000)

            print("[INFO] Tab 2: Menunggu seluruh elemen halaman Mode Edit ter-render sepenuhnya...")
            for _ in range(20):
                try:
                    body_txt = review_tab.evaluate("() => document.body ? document.body.innerText : ''")
                    if "Kirim" in body_txt or "KIRIM" in body_txt or "CATATAN" in body_txt or "Catatan" in body_txt:
                        print("[OK] Tab 2: Komponen Halaman Mode Edit terdeteksi selesai dimuat!")
                        break
                except: pass
                time.sleep(1)
            time.sleep(2)
            
            print("[INFO] Tab 2: Mencari dan mengeklik 'CATATAN' di sidebar kiri...")
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
                        loc = review_tab.locator(nav_sel)
                        for idx in range(loc.count()):
                            item = loc.nth(idx)
                            if item.is_visible():
                                box = item.bounding_box()
                                if box and box['x'] < 350:
                                    print(f"[OK] Tab 2: Menemukan 'CATATAN' di sidebar kiri (x={box['x']}, y={box['y']}). Mengeklik...")
                                    item.scroll_into_view_if_needed()
                                    item.click(force=True)
                                    catatan_clicked = True
                                    break
                        if catatan_clicked: break
                    except: pass
                if catatan_clicked: break
                time.sleep(1)

            if not catatan_clicked:
                print("[WARN] Tab 2: Mencoba JS click fallback untuk menu 'CATATAN' di sidebar...")
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
                catatan_clicked = review_tab.evaluate(js_click_catatan)

            print("[INFO] Tab 2: Menunggu form CATATAN & switchbox dimuat di layar...")
            for _ in range(15):
                try:
                    if review_tab.locator("text=Tampilkan Anomali Usaha dan Keluarga").first.is_visible():
                        print("[SUCCESS] Tab 2: Form CATATAN & Switchbox 'Tampilkan Anomali Usaha dan Keluarga' BERHASIL terlihat di layar!")
                        break
                except: pass
                time.sleep(1)

            print("[INFO] Tab 2: Mengaktifkan switchbox 'Tampilkan Anomali Usaha dan Keluarga' di Mode Edit...")
            toggle_checkbox_by_label(review_tab, "Tampilkan Anomali Usaha dan Keluarga", True)
            time.sleep(1)
            toggle_checkbox_by_label(review_tab, "Anomali diselesaikan oleh admin", True)
            time.sleep(1.5)
            toggle_checkbox_by_label(review_tab, "Anomali diselesaikan oleh admin", False)
            time.sleep(1)

            print("[INFO] Tab 2: Mengeklik tombol KIRIM...")
            # Tombol KIRIM di header edit mode: class tw:bg-primary, ikon send SVG, teks 'Kirim'
            kirim_btn = review_tab.locator("button[class*='tw:bg-primary']:has-text('Kirim')").first
            if kirim_btn.count() == 0 or not kirim_btn.is_visible():
                kirim_btn = review_tab.locator("button:has-text('Kirim')").first
            if kirim_btn.count() > 0:
                kirim_btn.click(force=True)
            time.sleep(2)

            print("[INFO] Tab 2: Konfirmasi modal KIRIM (tombol 'Kirim' di popup)...")
            # Popup KIRIM: class tw:bg-primary, teks 'Kirim' (bukan konfirmasi)
            modal_kirim1 = review_tab.locator("[role='dialog'] button[class*='tw:bg-primary']:has-text('Kirim')").first
            if modal_kirim1.count() == 0 or not modal_kirim1.is_visible():
                modal_kirim1 = review_tab.locator("[role='dialog'] button:has-text('Kirim')").first
            if modal_kirim1.count() > 0:
                modal_kirim1.click(force=True)
                time.sleep(2)

            print("[INFO] Tab 2: Konfirmasi popup kedua KIRIM (tombol 'Konfirmasi')...")
            # Popup konfirmasi: class tw:bg-primary, teks 'Konfirmasi'
            modal_kirim2 = review_tab.locator("[role='dialog'] button[class*='tw:bg-primary']:has-text('Konfirmasi')").first
            if modal_kirim2.count() == 0 or not modal_kirim2.is_visible():
                modal_kirim2 = review_tab.locator("[role='dialog'] button:has-text('Konfirmasi')").first
            if modal_kirim2.count() > 0:
                modal_kirim2.click(force=True)
                time.sleep(2)

            print("[INFO] Tab 2: Kembali ke Halaman Review pasca-Kirim...")
            try:
                # Tombol Kembali: data-tsd-source draggable-toolbar.tsx:123, ikon tabler-icon-arrow-left
                back_fab = review_tab.locator("button:has(.tabler-icon-arrow-left)").first
                if back_fab.count() == 0 or not back_fab.is_visible():
                    back_fab = review_tab.locator("[data-tsd-source*='draggable-toolbar.tsx:123']").first
                if back_fab.count() == 0 or not back_fab.is_visible():
                    back_fab = review_tab.locator("button[title*='Kembali']").first
                if back_fab.count() > 0 and back_fab.is_visible():
                    back_fab.click(force=True, timeout=5000)
                time.sleep(2)
            except: pass

            # Tombol Tinggalkan di popup: class f:bg-warning, teks 'Tinggalkan'
            leave_btn = review_tab.locator("[role='dialog'] button[class*='bg-warning']:has-text('Tinggalkan')").first
            if leave_btn.count() == 0 or not leave_btn.is_visible():
                leave_btn = review_tab.locator("[role='dialog'] button:has-text('Tinggalkan'), [role='dialog'] button:has-text('Keluar')").first
            if leave_btn.count() > 0:
                leave_btn.click(force=True)
                time.sleep(3)

            print("[INFO] Tab 2: Kembali di Halaman Review. Menyiapkan proses Reject...")

        # LANGKAH REJECT (Halaman Review)
        print("[INFO] Tab 2: Mengeklik tombol Reject pada FAB (Merah/X)...")
        reject_clicked = click_reject_fab_button(review_tab)
        if not reject_clicked:
            state_fab = check_page_state(review_tab)
            if state_fab != "OK" and state_fab != "CAPTCHA_SOLVED":
                try: review_tab.close()
                except: pass
                return state_fab
            try: review_tab.close()
            except: pass
            return "ERROR_FAB_REJECT"
        
        time.sleep(2)
        print("[INFO] Tab 2: Membaca tombol konfirmasi Reject...")
        # Tombol Konfirmasi Reject: class f:bg-destructive, teks 'Konfirmasi' (dari action-reject.tsx)
        confirm_reject_btn = review_tab.locator("[role='dialog'] button[class*='bg-destructive']:has-text('Konfirmasi')").first
        if confirm_reject_btn.count() == 0 or not confirm_reject_btn.is_visible():
            confirm_reject_btn = review_tab.locator("[data-tsd-source*='action-reject.tsx']:has-text('Konfirmasi')").first
        if confirm_reject_btn.count() == 0 or not confirm_reject_btn.is_visible():
            confirm_reject_btn = review_tab.locator("[role='dialog'] button:has-text('Konfirmasi')").first
        if confirm_reject_btn.count() == 0:
            confirm_reject_btn = review_tab.locator("text=Konfirmasi").last

        if dry_run:
            print("[DRY_RUN] Menghentikan klik KONFIRMASI reject agar assignment tetap utuh.")
            review_tab.keyboard.press("Escape")
            time.sleep(1)
        else:
            print("[LIVE] Tab 2: Mengeklik KONFIRMASI Reject...")
            confirm_reject_btn.click()
            
            print("[INFO] Tab 2: Menunggu respon dari server pasca-Reject...")
            try:
                review_tab.locator("text=Berhasil reject assignment").first.wait_for(state="visible", timeout=15000)
                print("[OK] Tab 2: Notifikasi 'Berhasil reject assignment' muncul.")
            except:
                state_after_reject = check_page_state(review_tab)
                if state_after_reject == "CAPTCHA_SOLVED":
                    print("[WARN] Terkena CAPTCHA persis saat submit Reject.")
                    try: review_tab.close()
                    except: pass
                    return "ERROR_CAPTCHA_INTERRUPT"
                if review_tab.locator("text=failed to edit assignment approval").count() > 0 or review_tab.locator("text=failed to edit").count() > 0:
                    print("[ERROR] Server menolak reject.")
                    try: review_tab.close()
                    except: pass
                    return "ERROR_SERVER_REJECT"
                print("[ERROR] Tidak mendapatkan notifikasi sukses reject.")
                try: review_tab.close()
                except: pass
                return "ERROR_SERVER_REJECT"

        time.sleep(2)
        try: review_tab.close()
        except: pass
        return "SUCCESS"


    except Exception as e:
        print(f"[ERROR] Assignment gagal diproses: {e}")
        return f"ERROR: {str(e)[:50]}"
    finally:
        # SELALU tutup Tab 2 setelah selesai memproses assignment ini!
        if review_tab:
            try:
                review_tab.close()
                print("[INFO] Tab 2 (Review) berhasil ditutup. Kembali fokus ke Tab 1.")
            except: pass


def run_automation():
    import datetime
    import csv

    cfg = load_config()
    username = cfg.get("username", "")
    password = cfg.get("password", "")
    dry_run = cfg.get("dry_run", "True").strip().lower() == "true"
    headless = cfg.get("headless", "False").strip().lower() == "true"
    headless_mode = headless or "--headless" in sys.argv

    # Siapkan logger CSV realtime di folder scrape_results dengan format nama yang urut dan presisi
    results_dir = os.path.join(parent_dir, "scrape_results")
    os.makedirs(results_dir, exist_ok=True)
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(results_dir, f"reject_batch_log_{timestamp_str}.csv")
    
    with open(log_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["No", "Timestamp", "Assignment_ID", "URL", "Status"])
        f.flush()
        
    print(f"[INFO] Log CSV realtime telah disiapkan: {log_file}")
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

    print("\n=== FASIH-SM ANOMALY & REJECT AUTOMATION (MANUAL BROWSER HYBRID MODE) ===")
    print("[INFO] Script dikonfigurasi untuk MENGGUNAKAN CHROME YANG SEDANG TERBUKA.")
    print("[INFO] Pastikan Anda telah membuka Chrome & Login secara manual di fasih-sm.bps.go.id:")
    print(r'       "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\ChromeAutomationProfile"')
    print("--------------------------------------------------------------------------------")
    
    with sync_playwright() as p:
        try:
            print("[INFO] Terhubung ke Chrome yang sedang berjalan di port 9222...")
            try:
                browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            except Exception as e:
                print(f"[ERROR] Gagal terhubung ke Chrome: {e}")
                print("\n[PETUNJUK JALANKAN CHROME]")
                print("1. Tutup SEMUA jendela Chrome yang sedang terbuka.")
                print(r'2. Jalankan perintah ini di CMD:')
                print(r'   "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\ChromeAutomationProfile" --disable-blink-features=AutomationControlled')
                print("3. Di Chrome tersebut, buka https://fasih-sm.bps.go.id/app dan login secara manual hingga masuk ke Dashboard.")
                print("4. Setelah berhasil di Dashboard, jalankan ulang skrip python ini.")
                return

            print("[SUCCESS] Berhasil terhubung ke Chrome Anda!")
            context = browser.contexts[0]
            apply_stealth_to_context(context)
            
            # Cari tab yang sudah membuka fasih-sm.bps.go.id, atau gunakan tab pertama
            sso_tab = None
            for page in context.pages:
                if "fasih-sm.bps.go.id" in page.url:
                    sso_tab = page
                    break
            
            if not sso_tab:
                if len(context.pages) > 0:
                    sso_tab = context.pages[0]
                else:
                    sso_tab = context.new_page()

            login_success = False
            for initial_attempt in range(3):
                print(f"[INFO] Menyiapkan sesi login BPS di Tab 1 (Percobaan {initial_attempt+1}/3)...")
                if login_sso_tab(sso_tab, username, password):
                    login_success = True
                    break
                else:
                    print(f"[WARN] Sesi login belum aktif. Silakan pastikan Anda sudah login manual di Chrome... (Jeda 8 detik, Percobaan {initial_attempt+1}/3)")
                    time.sleep(8)

            if not login_success:
                print("[WARN] Sesi login belum aktif. Melanjutkan ke alur pemrosesan URL (skrip akan tetap mencoba memproses)...")

            main_tab = sso_tab
            for idx_url, url in enumerate(target_urls):
                status = process_assignment(main_tab, url, headless_mode, dry_run)
 
                # Jika terdeteksi bot (ERROR_BOT_DETECTED) / Sesi Rusak, LANGSUNG BUNYIKAN ALARM DAN PAUSE TERMINAL INSTAN!
                if status in ["ERROR_BOT_DETECTED", "ERROR_SESSION", "ERROR_CAPTCHA_TIMEOUT"]:
                    print("\n" + "!"*70)
                    print(f"🔔 [ALARM TERDETEKSI BOT / SESI HABIS] ID: {url[-8:]} -> Status: '{status}'")
                    print("!"*70 + "\n")
                    
                    # 1. LANGSUNG BUNYIKAN ALARM SOUND TANPA DELAY APAPUN!
                    play_alert_sound()
                    
                    print("\n" + "="*70)
                    print("📌 TERDETEKSI BOT / CAPTCHA PERLU DITANGANI MANUSIA:")
                    print("Otomatisasi dihentikan sementara secara INSTAN.")
                    print("\nLangkah Penanganan Anda:")
                    print("1. Jika Chrome terblokir, tutup Chrome dan jalankan kembali di CMD:")
                    print(r'   "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\ChromeAutomationProfile"')
                    print("2. Akses https://fasih-sm.bps.go.id/app di Chrome tersebut dan lakukan Login SSO secara manual hingga masuk ke Dashboard.")
                    print("3. Setelah Anda berada di Dashboard, KEMBALI KE TERMINAL INI.")
                    print("="*70)
                    
                    try:
                        input("\n👉 TEKAN ENTER DI TERMINAL INI JIKA ANDA SUDAH SELESAI LOGIN/REFRESH UNTUK MELANJUTKAN AUTOMATION... ")
                    except:
                        time.sleep(15)
                        
                    print("\n[INFO] Menghubungkan kembali skrip ke Chrome yang sudah Anda perbaiki...")
                    try:
                        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
                        context = browser.contexts[0]
                        apply_stealth_to_context(context)
                        print("[SUCCESS] Berhasil terhubung kembali ke Chrome!")
                        main_tab = context.pages[0] if len(context.pages) > 0 else context.new_page()
                    except Exception as e_reconnect:
                        print(f"[ERROR] Gagal terhubung kembali ke Chrome: {e_reconnect}. Menghentikan batch.")
                        break
                        
                    print("[INFO] Memproses ulang URL setelah Anda memberikan konfirmasi...")
                    status = process_assignment(main_tab, url, headless_mode, dry_run)
                
                # Cek jika reject gagal karena interupsi server / CAPTCHA biasa
                if status in ["ERROR_CAPTCHA_INTERRUPT", "ERROR_SERVER_REJECT", "ERROR_SUBMIT_EDIT"]:
                    print(f"[WARN] Status {status}. Mencoba ulang URL ini 1 kali lagi...")
                    status = process_assignment(main_tab, url, headless_mode, dry_run)
 
                assignment_id = url.split("/")[-1] if "/" in url else url
                print(f"[RESULT] #{idx_url + 1} | ID: {assignment_id[-8:]} -> {status}")
 
                # Tulis log secara REALTIME langsung ke file CSV di disk
                with open(log_file, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        idx_url + 1,
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        assignment_id,
                        url,
                        status
                    ])
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except: pass
                print(f"[INFO] Row #{idx_url + 1} ({status}) berhasil ditulis secara realtime ke {os.path.basename(log_file)}")
                
                if idx_url < len(target_urls) - 1:
                    import random
                    sleep_time = random.randint(7, 10)
                    print(f"[INFO] Jeda manusiawi: Beristirahat {sleep_time} detik sebelum membuka URL berikutnya...")
                    time.sleep(sleep_time)

            print(f"\n[SUCCESS] Seluruh URL selesai diproses. Laporan tersimpan di: {log_file}")

        except Exception as e:
            print(f"[ERROR] Automation terhenti mendadak: {e}")
        finally:
            print("[INFO] Menutup browser...")
            try: context.close()
            except: pass
            force_kill_cdp_chrome()

if __name__ == '__main__':
    run_automation()
