import os
import sys
import time
import datetime
import csv
import pandas as pd
from playwright.sync_api import sync_playwright

# Masukkan folder parent (root) ke dalam system path agar bisa mengimpor vpn_auto_connect
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import vpn_auto_connect
import gspread
from oauth2client.service_account import ServiceAccountCredentials

LOGIN_URL = "https://manajemen-ksapro.bps.go.id/login"
EVALUASI_URL = "https://manajemen-ksapro.bps.go.id/evaluasi"
CREDS_FILE = os.path.join(parent_dir, "credentials.json")

def parse_downloaded_file(file_path):
    """Membaca file hasil download (.xlsx, .xls, .csv, atau HTML table disguise) menjadi list of list."""
    print(f"[INFO] Membaca dan memproses file: {file_path}")
    
    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
            return [df.columns.values.tolist()] + df.fillna("").values.tolist()
        else:
            try:
                dfs = pd.read_excel(file_path)
                return [dfs.columns.values.tolist()] + dfs.fillna("").values.tolist()
            except Exception:
                dfs = pd.read_html(file_path)
                if dfs:
                    df = dfs[0]
                    return [df.columns.values.tolist()] + df.fillna("").values.tolist()
    except Exception as e:
        print(f"[WARN] Parsing pandas gagal ({e}), menggunakan fallback manual...")
    
    rows = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        
    if "<table>" in content.lower():
        try:
            import re
            trs = re.findall(r'<tr[^>]*>(.*?)</tr>', content, re.DOTALL | re.IGNORECASE)
            for tr in trs:
                tds = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.DOTALL | re.IGNORECASE)
                clean_tds = [re.sub(r'<[^>]+>', '', td).strip() for td in tds]
                if clean_tds:
                    rows.append(clean_tds)
            if rows:
                return rows
        except Exception as ex:
            print(f"[WARN] HTML parsing fallback error: {ex}")

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f)
        for r in reader:
            rows.append(r)
            
    return rows

def load_config(auto_profile_idx=None):
    import configparser
    config_file = os.path.join(current_dir, "config.txt")
    if not os.path.exists(config_file):
        return {}
    config = configparser.ConfigParser()
    config.read(config_file)
    sections = config.sections()
    if not sections:
        return {}
    selected_section = None
    if auto_profile_idx is not None:
        if 1 <= auto_profile_idx <= len(sections):
            selected_section = sections[auto_profile_idx - 1]
    if not selected_section:
        print("\n=== Pilih Profil Kegiatan (KSA) ===")
        for i, sec in enumerate(sections):
            print(f"{i+1}. {sec}")
        while True:
            try:
                choice = int(input(f"Pilihan Anda (1-{len(sections)}): "))
                if 1 <= choice <= len(sections):
                    selected_section = sections[choice - 1]
                    break
            except ValueError:
                pass
            print("Pilihan tidak valid.")
    return dict(config[selected_section])

def export_to_google_sheet(data, sheet_url, sheet_tab_name):
    """Mengunggah data list of list ke Google Sheet target sebagai TEKS MURNI (RAW)."""
    if not data or len(data) < 2:
        print(f"[ERROR] Ekspor ke Google Sheets DIBATALKAN! Data tidak memiliki baris data (hanya header atau kosong, total {len(data) if data else 0} baris).")
        print("[ERROR] Mencegah perintah clear() agar data sebelumnya di Google Sheets TIDAK TERHAPUS/RUSAK.")
        return False

    if not os.path.exists(CREDS_FILE):
        print(f"[ERROR] File {CREDS_FILE} tidak ditemukan. Pengunggahan ditunda.")
        return False

    print(f"[INFO] Menghubungkan ke Google Sheets API...")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)
        client = gspread.authorize(creds)
        
        sheet = client.open_by_url(sheet_url)
        try:
            worksheet = sheet.worksheet(sheet_tab_name)
        except gspread.exceptions.WorksheetNotFound:
            print(f"[INFO] Tab '{sheet_tab_name}' tidak ditemukan, membuat tab baru...")
            worksheet = sheet.add_worksheet(title=sheet_tab_name, rows="1000", cols="30")
            
        clean_data = [[str(cell) if cell is not None else "" for cell in row] for row in data]
        print(f"[INFO] Menimpa data di sheet '{sheet_tab_name}' ({len(clean_data)} baris) sebagai TEKS MURNI (RAW)...")
        worksheet.clear()
        try:
            worksheet.update(clean_data, value_input_option='RAW')
        except TypeError:
            worksheet.update(range_name=None, values=clean_data, value_input_option='RAW')
        print("✅ SUKSES! Data berhasil diupload ke Google Sheet dengan format TEKS MURNI (RAW).")
        return True
    except Exception as e:
        print(f"[ERROR] Gagal upload ke Google Sheet: {e}")
        return False

def run_scrape_ksa(commodity="Padi", auto_profile_idx=None):
    commodity_label = commodity.strip().capitalize() # "Padi" atau "Jagung"
    default_tab = "ksa-padi" if commodity_label == "Padi" else "ksa-jagung"
    
    print("\n[INFO] Memeriksa status koneksi VPN BPS...")
    if not vpn_auto_connect.is_vpn_connected():
        print("[WARN] VPN terputus. Mencoba menghubungkan VPN otomatis...")
        vpn_auto_connect.run_auto_vpn()
        if not vpn_auto_connect.is_vpn_connected():
            print("[ERROR] Gagal menyambungkan VPN. Scraping dihentikan demi keamanan.")
            return None
    else:
        print("[SUCCESS] VPN BPS aktif/terhubung.")

    cfg = load_config(auto_profile_idx)
    username = cfg.get("username")
    password = cfg.get("password")
    sheet_url = cfg.get("sheet_url", "")
    sheet_tab_name = cfg.get("sheet_tab_name", default_tab)

    headless_mode = "--headless" in sys.argv
    results_dir = os.path.join(parent_dir, "scrape_results")
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)

    print(f"=== KSA {commodity_label.upper()} Scraping & Export Tool (UNIFIED ENGINE) ===")
    print(f"[INFO] Mode Headless: {headless_mode}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless_mode)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()        
        
        print(f"Navigasi ke {LOGIN_URL}...")
        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
        except Exception as e_goto:
            print(f"[WARN] Navigasi awal ke login lambat ({e_goto}), mencoba lanjut...")

        # Deteksi & Alur Login SSO BPS (Robust 15-cycle check)
        is_logged_in = False
        for cycle in range(15):
            curr_url = page.url
            if "sso.bps.go.id" in curr_url or page.locator('input[name="username"]').count() > 0:
                print(f"[INFO] Siklus {cycle+1}: Halaman Login SSO BPS terdeteksi. Mengisi kredensial...")
                try:
                    page.fill('input[name="username"]', username, timeout=5000)
                    page.fill('input[name="password"]', password, timeout=5000)
                    print("[INFO] Mengeklik tombol Log In...")
                    page.click('button[type="submit"], input[type="submit"], button:has-text("Log In")', no_wait_after=True, timeout=5000)
                except Exception as e_fill:
                    print(f"[WARN] Pengisian kredensial SSO: {e_fill}")
                
                print("[INFO] Menunggu login & redirect SSO BPS selesai...")
                for _ in range(25):
                    if "sso.bps.go.id" not in page.url and "manajemen-ksapro.bps.go.id" in page.url:
                        print("[SUCCESS] Login SSO BPS berhasil!")
                        is_logged_in = True
                        break
                    time.sleep(1)
                if is_logged_in:
                    break
            elif "manajemen-ksapro.bps.go.id" in curr_url and "login" not in curr_url:
                print("[SUCCESS] Sudah terautentikasi di portal KSA BPS.")
                is_logged_in = True
                break
            time.sleep(1)

        print("Navigasi ke menu Evaluasi...")
        try:
            page.locator("a:visible, button:visible").filter(has_text="Evaluasi").first.click(timeout=5000)
        except Exception:
            try:
                page.click("//a[contains(translate(text(), 'EVALUASI', 'evaluasi'), 'evaluasi')]", timeout=5000)
            except Exception:
                print("[INFO] Navigasi langsung ke URL evaluasi...")
                page.goto(EVALUASI_URL, wait_until="domcontentloaded", timeout=60000)

        time.sleep(3)
        try: page.wait_for_load_state("domcontentloaded", timeout=15000)
        except: pass

        # Pemilihan Komoditas (Padi / Jagung)
        print(f"Memilih Komoditas: {commodity_label}...")
        try:
            # Cek status komoditas di layar
            try:
                curr_val = page.evaluate("""() => {
                    const labels = Array.from(document.querySelectorAll('span, div, label, p'));
                    const kLabel = labels.find(el => el.textContent.trim().startsWith('Komoditas'));
                    return kLabel && kLabel.parentElement ? kLabel.parentElement.innerText : '';
                }""")
                if curr_val:
                    print(f"[INFO] Komoditas aktif di layar saat ini: '{curr_val.replace(chr(10), ' ')}'")
            except: pass

            # 1. Buka dropdown khusus Komoditas di samping label 'Komoditas:'
            dropdown_clicked = page.evaluate("""() => {
                const labels = Array.from(document.querySelectorAll('span, div, label, p'));
                const kLabel = labels.find(el => el.textContent.trim().startsWith('Komoditas'));
                if (kLabel) {
                    const parent = kLabel.closest('div') || kLabel.parentElement;
                    if (parent) {
                        const trigger = parent.querySelector('button, [role="combobox"], select, div[class*="select"]');
                        if (trigger) {
                            trigger.click();
                            return true;
                        }
                    }
                }
                return false;
            }""")
            
            if not dropdown_clicked:
                try:
                    page.locator("text=Komoditas: >> xpath=.. >> button, text=Komoditas: >> xpath=.. >> [role='combobox']").first.click(force=True, timeout=3000)
                except: pass

            time.sleep(1.5)

            # 2. Klik opsi komoditas target (Padi / Jagung)
            option_selected = page.evaluate(f"""(target) => {{
                const items = Array.from(document.querySelectorAll('[role="option"], [cmdk-item], li, div[cmdk-item]'));
                const matched = items.find(i => i.textContent.trim() === target || (i.textContent.includes(target) && i.children.length <= 1));
                if (matched) {{
                    matched.click();
                    return true;
                }}
                return false;
            }}""", commodity_label)

            if not option_selected:
                try:
                    page.locator("[role='option'], [cmdk-item]").filter(has_text=commodity_label).first.click(force=True, timeout=3000)
                except: pass

            time.sleep(1.5)
            
            # 3. Bersihkan sisa backdrop / overlay jika ada
            try:
                page.keyboard.press("Escape")
                page.evaluate("() => document.body.click()")
            except: pass
            print(f"[SUCCESS] Komoditas {commodity_label} berhasil dipilih!")
        except Exception as e_comm:
            print(f"[WARN] Kendala memilih Komoditas {commodity_label}: {e_comm}")

        print(f"Menunggu data {commodity_label} selesai dimuat...")
        time.sleep(5)
        try: page.wait_for_load_state("domcontentloaded", timeout=15000)
        except: pass

        print("Memulai download file...")
        try:
            with page.expect_download(timeout=60000) as download_info:
                # Gunakan JS DOM click langsung pada tombol Download Excel untuk menembus seluruh pointer interception
                js_clicked = page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('button, a'));
                    const targetBtn = btns.find(b => b.textContent.includes('Download Excel') || b.textContent.includes('Download') || b.textContent.includes('Unduh'));
                    if (targetBtn) {
                        targetBtn.click();
                        return true;
                    }
                    return false;
                }""")
                if not js_clicked:
                    page.click("button:has-text('Download Excel'), button:has-text('Download')", force=True, timeout=10000)
            
            download = download_info.value
            original_filename = download.suggested_filename
            if "." not in original_filename:
                original_filename += ".xlsx"
            file_prefix = "ksa_padi" if commodity_label == "Padi" else "ksa_jagung"
            file_name = f"{file_prefix}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{original_filename}"
            saved_path = os.path.join(results_dir, file_name)
            download.save_as(saved_path)
            print(f"✅ File berhasil diunduh ke: {saved_path}")

            # Parsing file download
            data_rows = parse_downloaded_file(saved_path)
            if data_rows and len(data_rows) > 1:
                header = data_rows[0]
                header.append("sync_time")
                sync_time_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for i in range(1, len(data_rows)):
                    if i == 1:
                        data_rows[i].append(sync_time_str)
                    else:
                        data_rows[i].append("")
                export_to_google_sheet(data_rows, sheet_url, sheet_tab_name)
            else:
                print(f"[ERROR] Gagal mengekstrak data valid dari file KSA {commodity_label} yang diunduh (hanya header atau 0 baris data).")

        except Exception as e:
            print(f"[ERROR] Proses download atau export KSA {commodity_label} gagal: {e}")
            debug_img = f"debug_ksa_{commodity_label.lower()}.png"
            page.screenshot(path=os.path.join(current_dir, debug_img))
            print(f"[INFO] Screenshot disimpan ke '{debug_img}'")

        browser.close()
