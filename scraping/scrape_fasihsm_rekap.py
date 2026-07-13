import configparser
import csv
import json
import os
import re
import time
import subprocess
import sys
from playwright.sync_api import sync_playwright

# Masukkan folder parent (root) ke dalam system path agar bisa mengimpor vpn_auto_connect
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import vpn_auto_connect

def load_config(auto_profile_idx=None):
    config_file = os.path.join(current_dir, "config.txt")
    if not os.path.exists(config_file):
        with open(config_file, "w") as f:
            f.write("[Kegiatan_1_Sensus]\n")
            f.write("username = \n")
            f.write("password = \n")
            f.write("target_url = https://fasih-sm.bps.go.id/app/surveys/b0cb30f1-bd3b-4c46-a7b4-eb3f8cfff9e7/c3ed3362-c12c-49f0-a1ad-60ed7e273e51\n")
            f.write("target_role = Pencacah\n")
            f.write("survey_role_id = \n")
            f.write("\n[Kegiatan_2_Ubinan]\n")
            f.write("username = \n")
            f.write("password = \n")
            f.write("target_url = \n")
            f.write("target_role = Pencacah\n")
            f.write("survey_role_id = \n")
        print(f"File {config_file} dibuat. Silakan isi kredensial Anda lalu jalankan ulang script.")
        return None
        
    config = configparser.ConfigParser()
    config.read(config_file)
    sections = config.sections()
    
    if len(sections) == 0:
        print("Error: Tidak ada profil kegiatan (section) yang ditemukan di config.txt.")
        return None
    elif len(sections) == 1:
        selected_section = sections[0]
        print(f"[INFO] Hanya satu profil ditemukan, menggunakan profil: {selected_section}")
        return config[selected_section]
    else:
        if auto_profile_idx is not None:
            selected_section = sections[auto_profile_idx - 1]
            print(f"[INFO] Auto-memilih profil: {selected_section}")
            return config[selected_section]

        print("\n=== Pilih Profil Kegiatan ===")
        for i, section in enumerate(sections):
            print(f"{i+1}. {section}")
            
        while True:
            try:
                choice = int(input(f"\nMasukkan nomor kegiatan yang ingin di-scrape (1-{len(sections)}): "))
                if 1 <= choice <= len(sections):
                    selected_section = sections[choice-1]
                    print(f"[INFO] Memilih profil: {selected_section}\n")
                    return config[selected_section]
                else:
                    print(f"Harap masukkan angka antara 1 sampai {len(sections)}.")
            except ValueError:
                print("Harap masukkan angka yang valid.")

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
        print("Google Chrome asli tidak ditemukan di sistem Anda.")
        return False
        
    user_data_dir = os.path.join(os.getcwd(), "chrome_debug_data")
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
        "--disable-blink-features=AutomationControlled", # Mencegah deteksi navigator.webdriver
        "--disable-infobars"
    ]
    if headless:
        args.append("--headless=new")
        args.append("--window-position=-2400,-2400") # Pindahkan jendela kosong di luar layar (Bug Chrome 129+ Windows)
        # Set User-Agent standar agar tidak ketahuan sebagai Headless Chrome
        args.append("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    else:
        args.append("--start-maximized")
        
    try:
        # Gunakan STARTUPINFO dengan SW_HIDE agar 100% tidak ada window konsol/terminal kosong di Windows
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
        
        creation_flags = 0x08000000 if os.name == 'nt' else 0
        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, creationflags=creation_flags, startupinfo=startupinfo)
        time.sleep(3) # Wait for Chrome to initialize
        return proc
    except Exception as e:
        print(f"Gagal membuka Chrome: {e}")
        return False

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

def refresh_session(context, username, password):
    """Membuka tab baru, melakukan login ulang ke Fasih-SM untuk memperbarui session token, lalu menutup tab tersebut."""
    print("[INFO] Mencoba memperbarui session token di tab baru...")
    login_page = None
    try:
        login_page = context.new_page()
        # Set viewport standar
        login_page.set_viewport_size({"width": 1920, "height": 1080})
        
        login_page.goto("https://fasih-sm.bps.go.id/oauth_login.html", timeout=45000, wait_until="domcontentloaded")
        
        # Cari tombol Login SSO BPS
        try:
            login_page.locator("text=SSO BPS").first.click(timeout=5000)
        except:
            try:
                login_page.click("//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'sso bps')]", timeout=5000)
            except:
                pass
                
        # Jika mengarah ke SSO BPS
        if "sso.bps.go.id" in login_page.url:
            print("[INFO] Mengisi kredensial SSO di tab baru...")
            login_page.fill('input[name="username"]', username)
            login_page.fill('input[name="password"]', password)
            login_page.click('button[type="submit"], input[type="submit"]')
            
            # Tunggu redirect kembali
            login_page.wait_for_url(lambda url: "fasih-sm.bps.go.id" in url, timeout=20000)
            
        print("[SUCCESS] Session token berhasil diperbarui di tab baru!")
        return True
    except Exception as e:
        print(f"[WARN] Gagal memperbarui session token di tab baru: {e}")
        return False
    finally:
        if login_page:
            try:
                login_page.close()
            except:
                pass

def run(auto_profile_idx=None):
    force_kill_cdp_chrome()
    import sys
    headless_mode = "--headless" in sys.argv
    
    print("=== Fasih Scraping Tool (Anti-Bot Mode) ===")
    if headless_mode:
        print("[INFO] Mode Headless aktif! Chrome akan berjalan tersembunyi di background.")
    
    config = load_config(auto_profile_idx)
    if not config:
        return None
        
    username = config.get("username", "")
    password = config.get("password", "")
    target_url = config.get("target_url", "")
    target_role = config.get("target_role", "Pencacah").strip()
    survey_role_id = config.get("survey_role_id", "")
    
    # Capitalize target_role to match 'Pencacah' or 'Pengawas' exactly
    if target_role.lower() == "pengawas":
        target_role = "Pengawas"
    else:
        target_role = "Pencacah"
        
    print(f"Role target dari config: {target_role}")
    
    uuids = re.findall(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', target_url)
    if len(uuids) < 2:
        print("Error: URL target di config.txt tidak valid (harus mengandung Survey ID dan Period ID).")
        return None
        
    survey_id = uuids[0]
    survey_period_id = uuids[1]
    
    with sync_playwright() as p:
        # Hubungkan ke Chrome asli via CDP (menghindari deteksi Bot)
        chrome_process = None
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            print("Berhasil terhubung ke Chrome yang sudah berjalan.")
        except Exception:
            print("Chrome Debug belum berjalan. Menjalankan Chrome...")
            chrome_process = launch_real_chrome(headless=headless_mode)
            if chrome_process:
                try:
                    browser = p.chromium.connect_over_cdp("http://localhost:9222")
                    print("Berhasil terhubung ke Chrome.")
                except Exception as e:
                    print("Gagal terhubung ke CDP setelah Chrome dibuka:", e)
                    if headless_mode and chrome_process:
                        chrome_process.kill()
                    return None
            else:
                return None

        context = browser.contexts[0]
        
        # Membersihkan cookies agar sesi login sebelumnya tidak nyangkut (menghindari miss auth)
        try:
            context.clear_cookies()
        except:
            pass
            
        # Menutup tab-tab sisa dari run sebelumnya jika ada
        while len(context.pages) > 1:
            try:
                context.pages[-1].close()
            except:
                break
                
        page = context.pages[0] if len(context.pages) > 0 else context.new_page()
        
        # Set viewport ke ukuran desktop jika headless
        if headless_mode:
            page.set_viewport_size({"width": 1366, "height": 768})
        
        print("Navigasi ke halaman Login Fasih...")
        try:
            # Go to oauth_login.html first to avoid direct-link bot detection
            page.goto("https://fasih-sm.bps.go.id/oauth_login.html", timeout=30000, wait_until="domcontentloaded")
            
            # Click Login SSO BPS button if it's there
            print("Mencari tombol Login SSO BPS...")
            try:
                page.locator("text=SSO BPS").first.click(timeout=5000)
            except Exception:
                try:
                    page.click("//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'sso bps')]", timeout=5000)
                except Exception:
                    pass # Maybe already logged in
                
            # Now we should be on SSO BPS page
            if "sso.bps.go.id" in page.url:
                print("Berada di halaman login SSO. Melakukan pengisian kredensial otomatis...")
                if not username or not password:
                    print("Username atau password di config.txt kosong! Silakan isi terlebih dahulu.")
                    return None
                    
                page.fill('input[name="username"]', username)
                page.fill('input[name="password"]', password)
                page.click('button[type="submit"], input[type="submit"]')
                
                print("Menunggu proses login selesai...")
                try:
                    page.wait_for_url(lambda url: "fasih-sm.bps.go.id" in url, timeout=15000)
                except Exception:
                    print("Timeout menunggu redirect login. Kita coba paksa lanjut...")
                    time.sleep(3)
        except Exception as e:
            print("Terjadi sedikit masalah saat auto-login:", e)
            print("Script akan tetap memaksa lanjut ke target URL...")

        print("Menavigasi ke URL target dasbor kegiatan (menunggu hingga 4 menit)...")
        try:
            page.goto(target_url, timeout=240000, wait_until="domcontentloaded")
        except Exception as e:
            print("Peringatan saat load URL target:", e)
            
        if not survey_role_id:
            print(f"\n[Otomasi Penuh Aktif] survey_role_id tidak ditemukan di config.txt.")
            print(">>> MENCARI ROLE ID SECARA OTOMATIS (Sabar, server BPS lambat) <<<")
            
            captured_payloads = []
            def handle_api_request(request):
                if "report-progress-by-responsibility" in request.url and request.method == "POST":
                    try:
                        captured_payloads.append(json.loads(request.post_data))
                    except:
                        pass
            
            # Pasang listener dari sekarang untuk menangkap request apapun (termasuk saat default tab dimuat)
            page.on("request", handle_api_request)
            
            try:
                print("Menunggu elemen 'Rekap Petugas' muncul di layar...")
                
                # Robust JS click for Rekap Petugas
                js_click_rekap = """
                () => {
                    let els = Array.from(document.querySelectorAll('a, button, li, span, div, p'));
                    let visibleEls = els.filter(e => e.offsetWidth > 0 && e.offsetHeight > 0);
                    
                    let targets = visibleEls.filter(e => e.textContent && e.textContent.trim() === 'Rekap Petugas');
                    if (targets.length === 0) {
                        targets = visibleEls.filter(e => e.textContent && e.textContent.includes('Rekap Petugas'));
                    }
                    
                    if (targets.length > 0) {
                        // Cari elemen terkecil (paling spesifik/dalam) untuk menghindari klik container luas
                        targets.sort((a, b) => (a.offsetWidth * a.offsetHeight) - (b.offsetWidth * b.offsetHeight));
                        let target = targets[0];
                        
                        target.click();
                        let parent = target.closest('a, button, li');
                        if(parent && parent !== target) parent.click();
                        return true;
                    }
                    return false;
                }
                """
                
                # Polling for Rekap Petugas up to 2 minutes
                rekap_clicked = False
                for i in range(60):
                    if page.evaluate(js_click_rekap):
                        rekap_clicked = True
                        break
                        
                    # Deteksi halaman error 500 dari BPS
                    is_error_page = page.evaluate("() => document.body.innerText.includes(\"There's some error\") || document.body.innerText.includes(\"The server encountered an unexpected condition\")")
                    if is_error_page:
                        if not vpn_auto_connect.is_vpn_connected():
                            print("\n[!] VPN terdeteksi TERPUTUS! Menghubungkan kembali VPN...")
                            vpn_auto_connect.run_auto_vpn()
                            time.sleep(5)
                        else:
                            print("\n[!] Terdeteksi halaman error dari server BPS. Memperbarui session via login ulang di tab baru...")
                            refresh_session(context, username, password)
                        print("Merefresh halaman utama (F5)...")
                        try:
                            page.reload(timeout=120000, wait_until="domcontentloaded")
                            time.sleep(5)
                        except:
                            pass
                            
                    time.sleep(2)
                    
                if not rekap_clicked:
                    print("Peringatan: Gagal menemukan elemen 'Rekap Petugas' setelah 2 menit menunggu.")
                    try:
                        print(f"[DEBUG] URL saat ini: {page.url}")
                        print(f"[DEBUG] Title halaman: {page.title()}")
                        page.screenshot(path="debug_error.png")
                        print("[DEBUG] Screenshot halaman disimpan sebagai 'debug_error.png'.")
                    except Exception as e:
                        print(f"[DEBUG] Gagal mengambil screenshot: {e}")
                else:
                    print("✅ Berhasil mengklik 'Rekap Petugas'!")
                
                print("Menunggu tab termuat (memberi jeda 5 detik)...")
                page.wait_for_timeout(5000)
                
                print(f"Mencoba mengklik elemen '{target_role}' dan menunggu request API...")
                # Robust JS click for target role
                js_click_role = f"""
                () => {{
                    let roleStr = '{target_role}';
                    let els = Array.from(document.querySelectorAll('a, button, li, span, div, p'));
                    let visibleEls = els.filter(e => e.offsetWidth > 0 && e.offsetHeight > 0);
                    
                    let targets = visibleEls.filter(e => e.textContent && e.textContent.trim() === roleStr);
                    if (targets.length === 0) {{
                        targets = visibleEls.filter(e => e.textContent && e.textContent.includes(roleStr));
                    }}
                    
                    if (targets.length > 0) {{
                        targets.sort((a, b) => (a.offsetWidth * a.offsetHeight) - (b.offsetWidth * b.offsetHeight));
                        let target = targets[0];
                        
                        target.click();
                        let parent = target.closest('a, button, li');
                        if(parent && parent !== target) parent.click();
                        return true;
                    }}
                    return false;
                }}
                """
                
                # Coba klik target role berulang-ulang sebentar untuk memastikan request baru terpancing
                for i in range(3):
                    page.evaluate(js_click_role)
                    time.sleep(2)
                    
                print("Menunggu request jaringan stabil (3 detik)...")
                time.sleep(3)
                
                if captured_payloads:
                    # Ambil payload yang paling terakhir ditangkap
                    raw_payload = captured_payloads[-1]
                    survey_role_id = raw_payload.get('surveyRoleId', '')
                    print(f"✅ Request {target_role} tertangkap! Role ID: {survey_role_id}")
                    print(f"[DEBUG] Raw Payload ditangkap: {json.dumps(raw_payload)}")
                    
                    # Kita buat ulang base_payload yang bersih untuk memastikan tidak ada filter yang nyangkut
                    base_payload = {
                        "surveyPeriodId": survey_period_id,
                        "surveyRoleId": survey_role_id,
                        "size": 10,
                        "page": 0,
                        "search": "",
                        "target": "TARGET_ONLY",
                        "region": {
                            "region1Id": None, "region2Id": None, "region3Id": None,
                            "region4Id": None, "region5Id": None, "region6Id": None,
                            "region7Id": None, "region8Id": None, "region9Id": None, "region10Id": None
                        },
                        "regionSummaryLevel": 6
                    }
                    print(f"[DEBUG] Base Payload yang akan digunakan: {json.dumps(base_payload)}")
                else:
                    print(f"Peringatan: Tidak ada network request 'report-progress-by-responsibility' yang tertangkap.")
                    print("Mungkin halaman belum sepenuhnya dimuat atau website mengalami masalah. Script akan gagal.")
                    return None
            except Exception as e:
                print(f"Gagal mengklik otomatis atau menangkap request: {e}")
                return None
        else:
            print(f"Menggunakan Role ID dari config.txt: {survey_role_id}")
            # Create a standard payload
            base_payload = {
                "surveyPeriodId": survey_period_id,
                "surveyRoleId": survey_role_id,
                "size": 10,
                "page": 0,
                "search": "",
                "target": "TARGET_ONLY",
                "region": {
                    "region1Id": None, "region2Id": None, "region3Id": None,
                    "region4Id": None, "region5Id": None, "region6Id": None,
                    "region7Id": None, "region8Id": None, "region9Id": None, "region10Id": None
                },
                "regionSummaryLevel": 6
            }
            
        print("\nMengambil halaman data rekap secara bertahap (Sistem Anti-Lemot & Retry)...")
        # Ekstrak nama kegiatan survei setelah halaman dipastikan termuat dengan baik
        print("Mencoba mengambil nama kegiatan survei dari halaman...")
        survey_name = "SURVEI_BPS"
        try:
            # Gunakan JavaScript murni untuk mencari elemen, untuk menghindari isu parsing CSS di Playwright
            js_code = """
            () => {
                // 1. Selector persis dari user (escape backslash 4x di Python untuk hasil \\ di JS)
                let s1 = "#survey > div > header > div > div > div:nth-child(2) > div.f\\\\:flex.f\\\\:items-center.f\\\\:gap-2 > a > div.f\\\\:truncate.f\\\\:text-muted-foreground.f\\\\:text-sm";
                
                // 2. Selector yang lebih fleksibel (mengabaikan struktur parent nth-child yang mungkin berubah)
                let s2 = "header a div.f\\\\:truncate.f\\\\:text-muted-foreground.f\\\\:text-sm";
                
                let el = document.querySelector(s1) || document.querySelector(s2);
                if (el && el.innerText.trim().length > 0) {
                    return el.innerText.trim();
                }
                
                // 3. Fallback: Cari teks SENSUS atau SURVEI di dalam header
                let header = document.querySelector("header");
                if (header) {
                    let els = header.querySelectorAll("span, div, a");
                    for (let e of els) {
                        let txt = e.innerText ? e.innerText.trim() : "";
                        if (txt.length > 5 && txt.length < 50 && (txt.toUpperCase().includes("SENSUS") || txt.toUpperCase().includes("SURVEI"))) {
                            // Ambil baris pertama saja jika ada multiple lines
                            return txt.split('\\n')[0].trim();
                        }
                    }
                }
                return null;
            }
            """
            
            # Polling selama 10 detik menunggu elemen muncul di DOM (karena React render)
            text = None
            for _ in range(10):
                text = page.evaluate(js_code)
                if text:
                    break
                time.sleep(1)
                
            if text:
                survey_name = re.sub(r'[^a-zA-Z0-9 ]', '_', text).strip().replace(' ', '_')
                print(f"✅ Nama kegiatan terdeteksi: {survey_name}")
            else:
                raise Exception("Tidak ada elemen yang cocok di header")
                
        except Exception as e:
            print(f"Peringatan: Gagal mengekstrak nama survei ({e}). Menggunakan fallback title.")
            # Fallback
            js_get_title = "() => document.title"
            title = page.evaluate(js_get_title)
            title = re.sub(r'[^a-zA-Z0-9 ]', '_', title).strip().replace(' ', '_')
            if title.startswith("FASIH_"):
                title = title[6:]
            survey_name = title[:50]
            if not survey_name:
                survey_name = "SURVEI_BPS"
            print(f"Nama kegiatan terdeteksi (fallback): {survey_name}")
        
        # Logika Resume
        results_dir = os.path.join(parent_dir, "scrape_results")
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)
            
        state_file = os.path.join(results_dir, "resume_state.json")
        resume_mode = False
        all_records = []
        current_page = 0
        
        import datetime
        
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                if state.get("survey_period_id") == survey_period_id and state.get("target_role") == target_role:
                    ans = input(f"\n[INFO] Ditemukan progres sebelumnya yang terhenti di Halaman {state['current_page'] + 1}.\nApakah Anda ingin melanjutkan scraping? (y/n): ").strip().lower()
                    if ans == 'y':
                        resume_mode = True
                        current_page = state['current_page']
                        csv_file = state['filename']
                        if os.path.exists(csv_file):
                            print(f"File {csv_file} ditemukan. Melanjutkan dari Halaman {current_page + 1}...")
                            output_filename = csv_file
                            # Tidak perlu read ke all_records, nanti kita append saat saving
                        else:
                            print("File CSV tidak ditemukan, mulai dari awal.")
                            current_page = 0
                            resume_mode = False
            except Exception as e:
                print(f"Gagal membaca state resume: {e}")
        
        if not resume_mode:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            filename_only = f"{survey_name}_rekap_petugas_{target_role.lower()}_{timestamp}.csv".replace(" ", "_")
            output_filename = os.path.join(results_dir, filename_only)
        
        js_fetch_single = """
        async ([basePayload, pageIndex]) => {
            const getCookie = (name) => {
                const value = `; ${document.cookie}`;
                const parts = value.split(`; ${name}=`);
                if (parts.length === 2) return parts.pop().split(';').shift();
                return '';
            };
            
            const xsrf = decodeURIComponent(getCookie('XSRF-TOKEN'));
            const url = '/app/api/analytic/api/v2/assignment/report-progress-by-responsibility';
            const pageSize = basePayload.size || 10;
            
            let payload = { ...basePayload, page: pageIndex, size: pageSize };
            
            let response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-xsrf-token': xsrf
                },
                body: JSON.stringify(payload)
            });
            
            if (!response.ok) {
                let errText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errText.substring(0, 50)}`);
            }
            
            return await response.json();
        }
        """
        
        all_records = []
        current_page = 0
        is_last = False
        
        while not is_last:
            success = False
            retries = 5 # Ditingkatkan menjadi 5
            while retries > 0 and not success:
                try:
                    print(f"Memproses Halaman {current_page + 1}... ", end="", flush=True)
                    data = page.evaluate(js_fetch_single, [base_payload, current_page])
                    
                    if data.get("success") and data.get("data") and data.get("data").get("content") is not None:
                        content = data["data"]["content"]
                        all_records.extend(content)
                        is_last = data["data"]["last"]
                        print(f"✅ Sukses! (+{len(content)} baris. Total: {len(all_records)})")
                        success = True
                    else:
                        print("Tidak ada data. (Selesai)")
                        is_last = True
                        success = True
                except Exception as e:
                    retries -= 1
                    err_msg = str(e)
                    wait_time = (5 - retries) * 10 # 10s, 20s, 30s, 40s, 50s
                    print(f"\n⚠️ Gagal: Server Fasih lambat atau error (Sisa percobaan: {retries}).")
                    if retries > 0:
                        print(f"Menunggu {wait_time} detik sebelum mencoba lagi agar server lega...")
                        time.sleep(wait_time)
                        
                        # Refresh halaman untuk mereset koneksi dan XSRF-TOKEN
                        if not vpn_auto_connect.is_vpn_connected():
                            print("\n[!] VPN terdeteksi TERPUTUS saat penarikan data! Menghubungkan kembali VPN...")
                            vpn_auto_connect.run_auto_vpn()
                            time.sleep(5)
                        else:
                            print("Memperbarui session via login ulang di tab baru...")
                            refresh_session(context, username, password)
                        print("Mencoba merefresh halaman (F5) untuk memulihkan koneksi API...")
                        try:
                            page.reload(timeout=60000, wait_until="domcontentloaded")
                            time.sleep(5)
                        except:
                            pass
                    else:
                        print(f"❌ Error detail: {err_msg}")
            
            if not success:
                print(f"\n❌ TERHENTI di Halaman {current_page + 1} karena server Fasih terus-menerus gagal merespons.")
                print("Menyimpan data yang berhasil dikumpulkan sejauh ini...")
                # Save state for resume
                with open(state_file, 'w') as f:
                    json.dump({
                        "survey_period_id": survey_period_id,
                        "target_role": target_role,
                        "current_page": current_page,
                        "filename": output_filename
                    }, f)
                break
                
            current_page += 1
            if current_page > 500: # Infinite loop safety
                break
                
        if not all_records:
            print("Tidak ada data yang ditemukan untuk disave.")
            return None
            
        print(f"Menulis data ke {output_filename}...")
        
        # Hapus state file jika sukses sampai akhir
        if is_last and os.path.exists(state_file):
            try:
                os.remove(state_file)
            except:
                pass
                
        sync_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        write_mode = "a" if resume_mode else "w"
        with open(output_filename, write_mode, newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not resume_mode:
                writer.writerow([
                    "Email Petugas", "Total Assignment", "Nama SLS", 
                    "OPEN", "SUBMITTED BY PENCACAH", "DRAFT", 
                    "APPROVED BY PENGAWAS", "REJECTED BY PENGAWAS", "REVOKED BY PENGAWAS",
                    "RAW_BODY_TEXT", "sync_time"
                ])
                
            total_sls_rows = 0
            for officer in all_records:
                email = officer.get("email") or officer.get("username")
                total_assignment = officer.get("total", 0)
                region_summary = officer.get("regionSummary", [])
                
                if not region_summary:
                    sync_time_val = sync_time_str if total_sls_rows == 0 and not resume_mode else ""
                    writer.writerow([
                        email, total_assignment, "N/A", 
                        0, 0, 0, 0, 0, 0, "", sync_time_val
                    ])
                    total_sls_rows += 1
                else:
                    for region in region_summary:
                        sls_code = region.get("regionCode")
                        
                        stats = {
                            "OPEN": 0,
                            "SUBMITTED BY PENCACAH": 0,
                            "DRAFT": 0,
                            "APPROVED BY PENGAWAS": 0,
                            "REJECTED BY PENGAWAS": 0,
                            "REVOKED BY PENGAWAS": 0
                        }
                        
                        for bd in region.get("statusBreakdown", []):
                            status_name = bd.get("status", "").upper()
                            count = bd.get("count", 0)
                            
                            if "OPEN" in status_name:
                                stats["OPEN"] = count
                            elif "SUBMITTED" in status_name or "PENCACAH" in status_name:
                                stats["SUBMITTED BY PENCACAH"] = count
                            elif "DRAFT" in status_name:
                                stats["DRAFT"] = count
                            elif "APPROVED" in status_name or "PENGAWAS" in status_name:
                                if "APPROVED" in status_name:
                                    stats["APPROVED BY PENGAWAS"] = count
                                elif "REJECTED" in status_name:
                                    stats["REJECTED BY PENGAWAS"] = count
                                elif "REVOKED" in status_name:
                                    stats["REVOKED BY PENGAWAS"] = count
                            
                        sync_time_val = sync_time_str if total_sls_rows == 0 and not resume_mode else ""
                        writer.writerow([
                            email, total_assignment, sls_code,
                            stats["OPEN"], stats["SUBMITTED BY PENCACAH"], stats["DRAFT"],
                            stats["APPROVED BY PENGAWAS"], stats["REJECTED BY PENGAWAS"], stats["REVOKED BY PENGAWAS"],
                            json.dumps(region), sync_time_val
                        ])
                        total_sls_rows += 1
                        
        print(f"✅ Berhasil menyimpan {total_sls_rows} baris breakdown SLS ke {output_filename}!")
        print("Tugas selesai.")
        
        print("Menutup browser Chrome untuk membersihkan sesi...")
        try:
            browser.close()
        except:
            pass
            
        if chrome_process:
            try:
                chrome_process.terminate()
            except:
                pass
                
        force_kill_cdp_chrome()
        return output_filename
if __name__ == "__main__":
    run()
