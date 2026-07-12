import os
import sys
import time
import datetime
import csv
from playwright.sync_api import sync_playwright

# Masukkan folder parent (root) ke dalam system path agar bisa mengimpor vpn_auto_connect
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import vpn_auto_connect
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Konfigurasi Default
LOGIN_URL = "https://fasih-dashboard.bps.go.id/"
CREDS_FILE = os.path.join(parent_dir, "credentials.json")

# Default fallback values jika tidak diisi di config.txt

TARGET_URL = "https://fasih-dashboard.bps.go.id/superset/dashboard/ubinan26s/"
SUBROUND = "2"
SHEET_URL = "https://docs.google.com/spreadsheets/d/1gGtp8ffrOhEEgw2pR4TTRfjUH-V2PPJLieDGqvItJyk/edit?usp=sharing"
SHEET_TAB_NAME = "ubinan26-s2"

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
        print("\n=== Pilih Profil Kegiatan (FASIH DB RAW) ===")
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
    """Mengunggah data list of list ke Google Sheet target."""
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
            
        print(f"[INFO] Menimpa data di sheet '{sheet_tab_name}' ({len(data)} baris)...")
        worksheet.clear()
        worksheet.update(data)
        print("[OK] SUKSES! Data berhasil diupload ke Google Sheet.")
        return True
    except Exception as e:
        print(f"[ERROR] Gagal upload ke Google Sheet: {e}")
        return False

def parse_downloaded_file(file_path):
    """Membaca file CSV yang diunduh dan mengubahnya menjadi list of list."""
    if not os.path.exists(file_path):
        print(f"[ERROR] File {file_path} tidak ditemukan.")
        return None
    try:
        data = []
        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            for row in reader:
                data.append(row)
        return data
    except Exception as e:
        print(f"[ERROR] Gagal membaca CSV: {e}")
        return None

def set_dropdown_filter(page, filter_name, value):
    """Mengeset filter dropdown Antd berdasarkan label nama filter di Superset."""
    if not value:
        return True
    print(f"Mengatur filter {filter_name} ke: {value}...")
    try:
        # Cari pembungkus filter berdasarkan label nama
        wrapper = page.locator(".ant-form-item").filter(has_text=filter_name).first
        wrapper.wait_for(state="visible", timeout=10000)
        select_trigger = wrapper.locator(".ant-select-selector, [role='combobox']").first
        
        # Loop verifikasi
        for attempt in range(5):
            print(f"Membuka dropdown {filter_name} (Percobaan {attempt + 1}/5)...")
            select_trigger.click(timeout=5000, no_wait_after=True)
            time.sleep(2)
            
            # Cek apakah dropdown list antd sudah muncul di DOM
            if page.locator(".ant-select-dropdown:visible").count() > 0:
                # Bersihkan pencarian lama jika ada
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                time.sleep(0.5)
                # Masukkan nilai filter via keyboard
                page.keyboard.type(value)
                time.sleep(1.5)
                page.keyboard.press("Enter")
                time.sleep(2)
                
                # Verifikasi apakah nilai sudah terpasang
                current_vals = [el.inner_text().strip().lower() for el in wrapper.locator(".ant-select-selection-item, .ant-select-selection-overflow-item").all()]
                if any(value.lower() in cv for cv in current_vals if cv):
                    print(f"[OK] Filter {filter_name} set ke {value} (Terverifikasi)")
                    return True
                # Alternatif check
                try:
                    current_val = select_trigger.locator(".ant-select-selection-item").first.inner_text().strip().lower()
                    if value.lower() in current_val:
                        print(f"[OK] Filter {filter_name} set ke {value} (Terverifikasi)")
                        return True
                except Exception:
                    pass
            print(f"[WARN] Dropdown {filter_name} gagal diset, mencoba klik ulang...")
            time.sleep(1)
        print(f"[WARN] Gagal memverifikasi filter {filter_name} terpasang, tetap melanjutkan...")
        return False
    except Exception as e:
        print(f"[WARN] Kendala saat menerapkan filter {filter_name}: {e}")
        return False

def run_scrape(auto_profile_idx=None):
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
    target_url = cfg.get("target_url", TARGET_URL)
    sheet_url = cfg.get("sheet_url", SHEET_URL)
    sheet_tab_name = cfg.get("sheet_tab_name", SHEET_TAB_NAME)
    # Mengumpulkan semua filter dinamis yang berawalan "filter_"
    dynamic_filters = {}
    for key, value in cfg.items():
        key_lower = key.lower()
        if key_lower.startswith("filter_"):
            # Karena configparser membuat key menjadi lowercase,
            # kita ubah underscore menjadi spasi agar cocok dengan label UI
            filter_name = key_lower[7:].replace("_", " ").strip()
            dynamic_filters[filter_name] = value.strip()

    headless_mode = "--headless" in sys.argv
    results_dir = os.path.join(parent_dir, "scrape_results")
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)

    print("=== FASIH Dashboard RAW Scraping & Export Tool ===")
    print(f"[INFO] Mode Headless: {headless_mode}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless_mode)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # Navigasi awal dengan retry untuk mengatasi masalah ketidakstabilan DNS/jaringan BPS
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"Navigasi ke {LOGIN_URL} (Percobaan {attempt + 1}/{max_retries})...")
                page.goto(LOGIN_URL, wait_until="load", timeout=60000)
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                print(f"[WARN] Navigasi gagal, mencoba lagi dalam 3 detik: {e}")
                time.sleep(3)

        # Step 1: Halaman Pemilihan Portal Login (Klik GO!)
        try:
            print("Mencari tombol GO! untuk masuk ke login SSO BPS...")
            page.locator("button, input[type='button'], input[type='submit']").filter(has_text="GO").first.click(timeout=10000)
            time.sleep(2)
        except Exception as e:
            print(f"[INFO] Tombol GO tidak ditemukan atau langsung diredirect: {e}")

        # Step 2: Halaman Login BPS SSO
        try:
            page.wait_for_load_state("load", timeout=10000)
        except Exception:
            pass

        if "sso.bps.go.id" in page.url or page.locator('input[name="username"]').is_visible():
            print("Halaman Login BPS SSO terdeteksi, mengisi kredensial...")
            page.fill('input[name="username"]', username)
            page.fill('input[name="password"]', password)
            page.click('button[type="submit"], input[type="submit"]')
            print("Menunggu login selesai...")
            
            # Loop tunggu sso.bps.go.id selesai redirect
            for _ in range(30):
                if "sso.bps.go.id" not in page.url:
                    break
                time.sleep(1)
            time.sleep(5)

        # Step 3: Navigasi ke URL Target Dashboard dengan retry
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"Navigasi ke URL target dashboard: {target_url} (Percobaan {attempt + 1}/{max_retries})...")
                page.goto(target_url, wait_until="load", timeout=60000)
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                print(f"[WARN] Navigasi dashboard gagal, mencoba lagi dalam 3 detik: {e}")
                time.sleep(3)
        time.sleep(5)

        # Step 4: Klik Tab "RAW"
        print("Mencoba membuka Tab 'RAW'...")
        try:
            # Tunggu salah satu selector tab RAW visible terlebih dahulu sebelum lanjut klik
            page.locator("div.ant-tabs-tab:has-text('RAW'), div[role='tab']:has-text('RAW')").first.wait_for(state="visible", timeout=20000)
            # Mencari elemen tab dengan teks RAW (case-sensitive)
            # Superset menggunakan kelas tab ant-tabs-tab atau elemen div/span dengan teks RAW
            raw_tab_selectors = [
                "div.ant-tabs-tab:has-text('RAW')",
                "div[role='tab']:has-text('RAW')",
                "text=RAW",
                "xpath=//div[contains(@class, 'ant-tabs-tab') and contains(., 'RAW')]"
            ]
            
            clicked = False
            for selector in raw_tab_selectors:
                try:
                    loc = page.locator(selector).first
                    if loc.is_visible():
                        loc.click(timeout=5000, no_wait_after=True)
                        clicked = True
                        print(f"[OK] Berhasil klik tab RAW menggunakan selector: {selector}")
                        break
                except Exception:
                    continue
            
            if not clicked:
                print("[WARN] Tidak dapat mengklik tab RAW dengan selector standar, mencoba klik teks RAW langsung...")
                page.locator("div:visible, span:visible, a:visible").filter(has_text="RAW").first.click(timeout=5000, no_wait_after=True)
            
            time.sleep(3)
        except Exception as e:
            print(f"[ERROR] Gagal membuka Tab RAW: {e}")
            page.screenshot(path="debug_raw_tab_error.png")
            print("[INFO] Screenshot disimpan ke 'debug_raw_tab_error.png'")
            browser.close()
            return

        # Step 5 & 6: Set Filter dropdowns dinamis dan APPLY FILTERS
        try:
            # Set semua filter dinamis yang ada di config.txt
            for filter_name, filter_value in dynamic_filters.items():
                set_dropdown_filter(page, filter_name, filter_value)

            # Klik tombol APPLY FILTERS
            print("Mengeklik tombol APPLY FILTERS...")
            page.locator("[data-test='filter-bar__apply-button'], button:visible").filter(has_text="APPLY FILTERS").first.click(timeout=5000, no_wait_after=True)
            print("[OK] Berhasil mengeklik APPLY FILTERS")
            time.sleep(5)
        except Exception as e:
            print(f"[WARN] Kendala saat menerapkan filter dropdown: {e}")
            page.screenshot(path="debug_filter_warning.png")

        # Step 7: Menunggu data selesai ter-load (spinner loading menghilang)
        print("Menunggu data tabel ter-load...")
        time.sleep(5)
        try:
            # Tunggu spinner superset/antd menghilang (120 detik)
            page.locator("img.loading, .ant-spin-spinning, .loading, svg.spin").first.wait_for(state="hidden", timeout=120000)
            print("[OK] Spinner loading selesai")
        except Exception as e:
            print(f"[INFO] Timeout menunggu spinner ({e}), melanjutkan proses...")

        # Step 8, 9 & 10: Cari Tombol 3 Titik -> Download -> Export to .CSV
        print("Mencari tombol 3 titik (actions menu) pada tabel...")
        try:
            # Kita buat pemilih (selectors) yang secara khusus mengincar kartu tabel "Raw Data Ubinan"
            # Jangan gunakan pemilih generik agar tidak salah mengeklik kartu KPI/Ringkasan lain
            three_dots_selectors = [
                # 1. Mengincar berdasarkan data-test-chart-name yang unik untuk tabel raw data
                "xpath=//div[contains(@data-test-chart-name, 'data.tab')]//span[@aria-label='More Options']",
                # 2. Mengincar berdasarkan class chart-slice dan teks judul "Raw Data Ubinan" (menggunakan contains(., ...))
                "xpath=//div[contains(@class, 'chart-slice') and .//span[contains(., 'Raw Data Ubinan')]]//span[@aria-label='More Options']",
                # 3. Alternatif jika tag controls-nya berupa element lain dengan ellipsis
                "xpath=//div[contains(@class, 'chart-slice') and .//span[contains(., 'Raw Data Ubinan')]]//*[contains(@class, 'anticon-ellipsis') or @aria-label='More Options']",
                # 4. Fallback dengan data-test-chart-id jika id-nya konstan
                "xpath=//div[@data-test-chart-id='9868']//span[@aria-label='More Options']"
            ]

            clicked_menu = False
            for selector in three_dots_selectors:
                try:
                    loc = page.locator(selector).first
                    if loc.is_visible():
                        loc.click(timeout=5000, no_wait_after=True)
                        clicked_menu = True
                        print(f"[OK] Berhasil klik menu 3 titik menggunakan selector: {selector}")
                        break
                except Exception:
                    continue

            if not clicked_menu:
                raise Exception("Tidak menemukan menu 3 titik (actions menu) yang spesifik untuk tabel Raw Data!")

            time.sleep(2)

            # Mengeklik submenu "Download" untuk membuka flyout secara permanen
            # Menggunakan .ant-dropdown:not(.ant-dropdown-hidden) agar hanya mendeteksi menu yang saat ini aktif terbuka
            print("Mengeklik menu 'Download'...")
            download_menu = page.locator(".ant-dropdown:not(.ant-dropdown-hidden) .ant-dropdown-menu-submenu-title").filter(has_text="Download").first
            download_menu.click(timeout=5000, no_wait_after=True)
            time.sleep(2)

            # Mencegat unduhan CSV
            # Menggunakan force=True agar klik terkirim langsung meskipun ada transisi atau kendala layout
            print("Mengeklik 'Export to .CSV'...")
            with page.expect_download(timeout=120000) as download_info:
                page.locator(".ant-dropdown-menu-submenu-popup .ant-dropdown-menu-item").filter(has_text="Export to .CSV").first.click(timeout=5000, force=True, no_wait_after=True)

            download = download_info.value
            file_name = f"fasihdb_raw_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{download.suggested_filename}"
            saved_path = os.path.join(results_dir, file_name)
            download.save_as(saved_path)
            print(f"[OK] File berhasil diunduh ke: {saved_path}")

            # Step 11: Parsing CSV dan menambahkan sync_time di paling kanan
            data_rows = parse_downloaded_file(saved_path)
            if data_rows and len(data_rows) > 0:
                header = data_rows[0]
                
                # Petakan indeks kolom untuk setiap filter dinamis (berdasarkan kecocokan nama kolom di header CSV)
                filter_col_indices = {}
                for f_name, f_val in dynamic_filters.items():
                    for col_idx, col_name in enumerate(header):
                        if col_name.strip().lower() == f_name.strip().lower():
                            filter_col_indices[f_name] = (col_idx, f_val)
                            break
                
                # Lakukan pemfilteran data (hanya jika filter dikonfigurasi & kolomnya ada di CSV)
                filtered_rows = [header]
                for row in data_rows[1:]:
                    match_all_filters = True
                    for f_name, (col_idx, f_val) in filter_col_indices.items():
                        if col_idx < len(row) and f_val.lower() not in row[col_idx].lower():
                            match_all_filters = False
                            break
                    if match_all_filters:
                        filtered_rows.append(row)
                
                print(f"[INFO] Menyaring data dari {len(data_rows)} baris menjadi {len(filtered_rows)} baris.")
                data_rows = filtered_rows
                
                # Tambahkan kolom sync_time di header dan baris pertama data
                header = data_rows[0]
                header.append("sync_time")
                sync_time_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for i in range(1, len(data_rows)):
                    if i == 1:
                        data_rows[i].append(sync_time_str)
                    else:
                        data_rows[i].append("")
                
                # Step 12: Upload ke Google Sheets
                export_to_google_sheet(data_rows, sheet_url, sheet_tab_name)
            else:
                print("[ERROR] Gagal mengekstrak data dari file CSV yang diunduh.")

        except Exception as e:
            print(f"[ERROR] Proses download atau export gagal: {e}")
            page.screenshot(path="debug_download_error.png")
            print("[INFO] Screenshot disimpan ke 'debug_download_error.png'")

        browser.close()

if __name__ == "__main__":
    run_scrape()
