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

# Konfigurasi Target
LOGIN_URL = "https://ksapro-manajemen.bps.go.id/login"
USERNAME = "ilham.rizanto"
PASSWORD = "Akun0000"
PROVINSI = "Maluku Utara"
KABUPATEN = "Halmahera Utara"

SHEET_URL = "https://docs.google.com/spreadsheets/d/1gGtp8ffrOhEEgw2pR4TTRfjUH-V2PPJLieDGqvItJyk/edit?usp=sharing"
SHEET_TAB_NAME = "ksa-padi"
CREDS_FILE = os.path.join(parent_dir, "credentials.json")

def parse_downloaded_file(file_path):
    """Membaca file hasil download (.xlsx, .xls, .csv, atau HTML table disguise) menjadi list of list."""
    print(f"[INFO] Membaca dan memproses file: {file_path}")
    
    # Try reading with pandas first if available
    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
            return [df.columns.values.tolist()] + df.fillna("").values.tolist()
        else:
            # excel / html disguised as xls
            try:
                dfs = pd.read_excel(file_path)
                return [dfs.columns.values.tolist()] + dfs.fillna("").values.tolist()
            except Exception:
                # Try read_html in case it's an HTML table with .xls extension (Common BPS behavior)
                dfs = pd.read_html(file_path)
                if dfs:
                    df = dfs[0]
                    return [df.columns.values.tolist()] + df.fillna("").values.tolist()
    except Exception as e:
        print(f"[WARN] Parsing pandas gagal ({e}), menggunakan fallback manual...")
    
    # Fallback to plain text / csv parsing if pandas fails or file is raw text/HTML/csv
    rows = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        
    if "<table>" in content.lower():
        from xml.etree import ElementTree as ET
        try:
            # Basic HTML table parser fallback
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

    # Plain CSV fallback
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
        print("\n=== Pilih Profil Kegiatan (KSA Padi) ===")
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
        print("✅ SUKSES! Data berhasil diupload ke Google Sheet.")
        return True
    except Exception as e:
        print(f"[ERROR] Gagal upload ke Google Sheet: {e}")
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
    username = cfg.get("username", USERNAME)
    password = cfg.get("password", PASSWORD)
    sheet_url = cfg.get("sheet_url", SHEET_URL)
    sheet_tab_name = cfg.get("sheet_tab_name", SHEET_TAB_NAME)
    provinsi = cfg.get("provinsi", PROVINSI)
    kabupaten = cfg.get("kabupaten", KABUPATEN)

    headless_mode = "--headless" in sys.argv
    results_dir = os.path.join(parent_dir, "scrape_results")
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)

    print("=== KSA PADI Scraping & Export Tool ===")
    print(f"[INFO] Mode Headless: {headless_mode}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless_mode)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        print(f"Navigasi ke {LOGIN_URL}...")
        page.goto(LOGIN_URL, wait_until="networkidle")

        # Cek apakah ter-redirect ke SSO BPS
        time.sleep(2)
        if "sso.bps.go.id" in page.url or page.locator('input[name="username"]').is_visible():
            print("Halaman Login terdeteksi, mengisi kredensial...")
            page.fill('input[name="username"]', username)
            page.fill('input[name="password"]', password)
            page.click('button[type="submit"], input[type="submit"]')
            print("Menunggu login selesai...")
            page.wait_for_load_state("networkidle")
            time.sleep(3)

        print("Navigasi ke menu Evaluasi...")
        # Coba klik menu Evaluasi atau navigasi ke URL evaluasi jika ada
        try:
            page.locator("a:visible, button:visible").filter(has_text="Evaluasi").first.click(timeout=5000)
        except Exception:
            try:
                page.click("//a[contains(translate(text(), 'EVALUASI', 'evaluasi'), 'evaluasi')]", timeout=5000)
            except Exception:
                print("[INFO] Mencoba navigasi langsung ke URL evaluasi...")
                page.goto("https://ksapro-manajemen.bps.go.id/evaluasi", wait_until="networkidle")

        time.sleep(3)
        page.wait_for_load_state("networkidle")

        print(f"Memilih Filter Provinsi: {provinsi} dan Kabupaten: {kabupaten}...")
        try:
            # Klik container dropdown Provinsi (yang terlihat saja)
            page.locator(".v-input:visible", has_text="Provinsi").first.click(timeout=5000)
            time.sleep(1.5)
            # Pilih opsi Provinsi dari menu popup melayang (abaikan sidebar)
            page.locator(".v-menu__content:visible .v-list-item", has_text=provinsi).first.click(timeout=5000)
            
            # Tunggu server mengambil data Kabupaten (API call terpancing setelah Provinsi dipilih)
            print("Menunggu daftar Kabupaten ter-load...")
            time.sleep(3)

            # Klik container dropdown Kabupaten (yang terlihat saja)
            page.locator(".v-input:visible", has_text="Kabupaten").first.click(timeout=5000)
            time.sleep(1.5)
            # Pilih opsi Kabupaten dari menu popup melayang
            page.locator(".v-menu__content:visible .v-list-item", has_text=kabupaten).first.click(timeout=5000)
            time.sleep(2)
        except Exception as e:
            print(f"[WARN] Kendala saat memilih dropdown filter: {e}")

        print("Mencari tombol Download Data...")
        download_button = None
        for selector in [
            "button:has-text('Download Data'):visible",
            "a:has-text('Download Data'):visible",
            "text=Download Data:visible",
            "button:has-text('Download'):visible",
            "a:has-text('Download'):visible",
            "text=Download:visible",
            "text=Unduh:visible"
        ]:
            try:
                if page.locator(selector).first.is_visible():
                    download_button = page.locator(selector).first
                    break
            except Exception:
                pass

        if not download_button:
            print("[WARN] Tombol download khusus tidak terdeteksi via text biasa, mencoba mencari elemen tombol/link unduh...")
            try:
                download_button = page.locator("button:visible, a:visible").filter(has_text="Download").first
            except Exception:
                pass

        print("Memulai download file...")
        try:
            with page.expect_download(timeout=60000) as download_info:
                if download_button and download_button.is_visible():
                    download_button.click()
                else:
                    # try clicking any button with download icon or keyword
                    page.click("//*[contains(translate(text(), 'DOWNLOAD', 'download'), 'download')]", timeout=10000)
            
            download = download_info.value
            file_name = f"ksa_padi_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{download.suggested_filename}"
            saved_path = os.path.join(results_dir, file_name)
            download.save_as(saved_path)
            print(f"✅ File berhasil diunduh ke: {saved_path}")

            # Parsing file download
            data_rows = parse_downloaded_file(saved_path)
            if data_rows and len(data_rows) > 0:
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
                print("[ERROR] Gagal mengekstrak data dari file yang diunduh.")

        except Exception as e:
            print(f"[ERROR] Proses download atau export gagal: {e}")
            page.screenshot(path="debug_ksa_padi.png")
            print("[INFO] Screenshot disimpan ke 'debug_ksa_padi.png'")

        browser.close()

if __name__ == "__main__":
    run_scrape()
