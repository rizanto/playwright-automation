import os
import csv
import configparser
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def main(auto_profile_idx=None, auto_csv_path=None):
    print("=== Fasih Scraping - Export to Google Sheets ===")
    
    # 1. Cek credentials.json
    creds_file = "credentials.json"
    if not os.path.exists(creds_file):
        print("\n[ERROR] File credentials.json tidak ditemukan!")
        print("\nLangkah-langkah mendapatkan credentials.json:")
        print("1. Buka Google Cloud Console (https://console.cloud.google.com/)")
        print("2. Buat Project baru (atau gunakan yang sudah ada).")
        print("3. Cari dan Aktifkan 'Google Sheets API' dan 'Google Drive API'.")
        print("4. Buka menu 'Credentials' -> 'Create Credentials' -> 'Service Account'.")
        print("5. Isi nama bebas, lalu klik Done.")
        print("6. Klik akun service yang baru dibuat, masuk ke tab 'Keys' -> 'Add Key' -> 'Create new key' -> Pilih JSON.")
        print("7. Simpan file yang terunduh ke folder proyek ini dan ganti namanya menjadi 'credentials.json'.")
        print("8. Buka Google Sheet target Anda, klik tombol 'Share', dan tambahkan email Service Account (ada di dalam file JSON) sebagai Editor.")
        return

    # 2. Baca config.txt
    config_file = "config.txt"
    if not os.path.exists(config_file):
        print("[ERROR] config.txt tidak ditemukan.")
        return
        
    config = configparser.ConfigParser()
    config.read(config_file)
    sections = config.sections()
    
    if len(sections) == 0:
        print("[ERROR] Tidak ada profil kegiatan di config.txt.")
        return
        
    selected_section = None
    if auto_profile_idx is not None:
        selected_section = sections[auto_profile_idx - 1]
    else:
        print("\n=== Pilih Profil Kegiatan untuk Target Google Sheets ===")
        for i, section in enumerate(sections):
            print(f"{i+1}. {section}")
            
        while True:
            try:
                choice = int(input(f"\nMasukkan nomor profil (1-{len(sections)}): "))
                if 1 <= choice <= len(sections):
                    selected_section = sections[choice-1]
                    break
            except ValueError:
                pass
            print("Pilihan tidak valid.")
            
    profile = config[selected_section]
    sheet_url = profile.get("sheet_url", "").strip()
    sheet_tab = profile.get("sheet_tab_name", "Sheet1").strip()
    
    if not sheet_url:
        print(f"\n[ERROR] Anda belum mengisi 'sheet_url' untuk profil [{selected_section}] di config.txt!")
        print("Silakan buka config.txt, paste link Google Sheet Anda di bagian sheet_url, lalu jalankan ulang.")
        return

    # 3. Pilih file CSV
    selected_csv = None
    if auto_csv_path is not None:
        selected_csv = auto_csv_path
    else:
        results_dir = "scrape_results"
        if not os.path.exists(results_dir):
            print(f"\n[ERROR] Folder {results_dir} tidak ditemukan.")
            return
            
        csv_files = [f for f in os.listdir(results_dir) if f.endswith('.csv')]
        if not csv_files:
            print(f"\n[ERROR] Tidak ada file CSV di dalam folder {results_dir}.")
            return
            
        print("\n=== Pilih File CSV yang ingin diekspor ===")
        for i, f in enumerate(csv_files):
            print(f"{i+1}. {f}")
            
        while True:
            try:
                choice = int(input(f"\nMasukkan nomor file CSV (1-{len(csv_files)}): "))
                if 1 <= choice <= len(csv_files):
                    selected_csv = os.path.join(results_dir, csv_files[choice-1])
                    break
            except ValueError:
                pass
            print("Pilihan tidak valid.")
        
    print(f"\n[INFO] Membaca file {selected_csv}...")
    
    # Baca data CSV
    try:
        with open(selected_csv, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            data = list(reader)
    except Exception as e:
        print(f"[ERROR] Gagal membaca CSV: {e}")
        return
        
    if not data:
        print("[ERROR] File CSV kosong.")
        return

    # 4. Hubungkan ke Google Sheets
    print("[INFO] Menghubungkan ke Google Sheets API...")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_file, scope)
        client = gspread.authorize(creds)
        
        # Buka berdasarkan URL
        sheet = client.open_by_url(sheet_url)
        worksheet = sheet.worksheet(sheet_tab)
    except gspread.exceptions.SpreadsheetNotFound:
        print("\n[ERROR] Google Sheet tidak ditemukan. Pastikan URL benar dan Anda sudah men-Share file tersebut ke email Service Account (lihat langkah 8 di atas).")
        return
    except gspread.exceptions.WorksheetNotFound:
        print(f"\n[ERROR] Tab bernama '{sheet_tab}' tidak ditemukan di Google Sheet tersebut.")
        return
    except Exception as e:
        print(f"\n[ERROR] Gagal terhubung ke Google Sheets: {e}")
        return
        
    # 5. Overwrite data
    print(f"[INFO] Menimpa ulang (overwrite) data di tab '{sheet_tab}' dengan {len(data)} baris (termasuk header)...")
    try:
        worksheet.clear()
        
        # Update in batches if very large, but update() usually handles it
        # However, passing a list of lists works perfectly for reasonable sizes
        worksheet.update(data)
        print("\n✅ SUKSES! Data berhasil diekspor ke Google Sheets.")
    except Exception as e:
        print(f"\n[ERROR] Gagal mengupdate data: {e}")

if __name__ == "__main__":
    import sys
    
    auto_profile_idx = None
    auto_csv_path = None
    
    for arg in sys.argv:
        if arg.startswith("--profile-idx="):
            auto_profile_idx = int(arg.split("=")[1])
        elif arg.startswith("--csv-path="):
            auto_csv_path = arg.split("=", 1)[1]
            
    main(auto_profile_idx, auto_csv_path)
