import os
import sys
import subprocess

def show_menu():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("==================================================")
    
    print("       PLAYWRIGHT AUTOMATION & SCRAPING MENU      ")
    print("==================================================")
    print("")
    print(" [ KATEGORI 1: SCRAPING ]")
    print("  1. Jalankan Semua Scraper (auto_run_all)")
    print("  2. Scrape FASIH-SM Rekap")
    print("  3. Scrape FASIH Dashboard Raw")
    print("  4. Scrape KSA Padi")
    print("  5. Scrape KSA Jagung")
    print("  6. Ekspor Data Manual ke Google Sheets")
    print("")
    print(" [ KATEGORI 2: AUTOMASI ]")
    print("  7. Automasi Tindak Lanjut Anomali & Reject")
    print("")
    print(" [ KATEGORI 3: KONEKTIVITAS ]")
    print("  8. Hubungkan / Cek Status VPN BPS (FortiClient)")
    print("")
    print("  0. Keluar")
    print("==================================================")
    print("")

def run_script(script_name, folder="."):
    print(f"\n[INFO] Menjalankan: python {script_name} di folder '{folder}'...")
    try:
        # Menjalankan script menggunakan python interpreter saat ini dan mengatur CWD
        res = subprocess.run([sys.executable, script_name], cwd=folder)
        return res.returncode == 0
    except Exception as e:
        print(f"[ERROR] Gagal menjalankan skrip: {e}")
        return False

def main():
    while True:
        show_menu()
        try:
            choice = input("Pilih menu (0-8): ").strip()
            if choice == "0":
                print("\nKeluar dari program. Sampai jumpa!")
                break
            elif choice == "1":
                run_script("auto_run_all.py", "scraping")
            elif choice == "2":
                run_script("scrape_fasihsm_rekap.py", "scraping")
            elif choice == "3":
                run_script("scrape_fasihdb_raw.py", "scraping")
            elif choice == "4":
                run_script("scrape_ksa_padi.py", "scraping")
            elif choice == "5":
                run_script("scrape_ksa_jagung.py", "scraping")
            elif choice == "6":
                run_script("export_to_sheets.py", "scraping")
            elif choice == "7":
                run_script("automate_anomaly_reject.py", "automation")
            elif choice == "8":
                run_script("vpn_auto_connect.py", ".")
            else:
                print("\n[WARN] Pilihan tidak valid. Silakan coba lagi.")
                
            print("\nTekan Enter untuk kembali ke menu utama...")
            input()
        except KeyboardInterrupt:
            print("\n\nProgram dibatalkan oleh pengguna.")
            break

if __name__ == "__main__":
    main()
