import configparser
import os
import sys

# Masukkan folder parent (root) ke dalam system path agar bisa mengimpor vpn_auto_connect
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Import the main modules
import scrape_fasihsm_rekap
import export_to_sheets
import scrape_ksa_padi
import scrape_ksa_jagung
import scrape_fasihdb_raw
import vpn_auto_connect

def main():
    print("=== Auto Run All Kegiatan ===")
    config_file = os.path.join(current_dir, "config.txt")
    if not os.path.exists(config_file):
        print("[ERROR] config.txt tidak ditemukan.")
        return
        
    config = configparser.ConfigParser()
    config.read(config_file)
    sections = config.sections()
    
    if not sections:
        print("[ERROR] Tidak ada kegiatan di config.txt.")
        return
        
    print("\n=== Daftar Kegiatan ===")
    for i, section in enumerate(sections):
        print(f"{i+1}. {section}")
        
    # Mendeteksi pilihan profil dari argumen CLI (jika ada) untuk mendukung otomatisasi non-interaktif
    # Kita menyaring argumen yang bukan flag (tidak diawali dengan '-')
    non_flag_args = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    if non_flag_args:
        pilihan = non_flag_args[0].strip().lower()
        print(f"Pilihan Anda (via argumen): {pilihan}")
    else:
        print("\nMasukkan nomor profil yang ingin dijalankan (pisahkan dengan koma, misal 1,3,4).")
        print("Atau tekan Enter langsung (atau ketik 'all') untuk menjalankan semua.")
        pilihan = input("Pilihan Anda: ").strip().lower()
    
    selected_indices = []
    if not pilihan or pilihan == 'all':
        selected_indices = list(range(1, len(sections) + 1))
    else:
        parts = pilihan.replace(" ", "").split(",")
        for p in parts:
            if p.isdigit():
                val = int(p)
                if 1 <= val <= len(sections) and val not in selected_indices:
                    selected_indices.append(val)
                    
    if not selected_indices:
        print("[ERROR] Tidak ada profil valid yang dipilih. Dibatalkan.")
        return
        
    print(f"\n[INFO] Akan memproses profil nomor: {', '.join(map(str, selected_indices))}")

    # Memastikan flag --headless ada di sys.argv agar proses berjalan di latar belakang
    if "--headless" not in sys.argv:
        sys.argv.append("--headless")
        
    # Memastikan VPN BPS terhubung sebelum memulai scraping
    print("\n[INFO] Memeriksa status koneksi VPN BPS sebelum scraping...")
    if not vpn_auto_connect.is_vpn_connected():
        print("[WARN] VPN terputus. Mencoba menghubungkan VPN otomatis...")
        vpn_auto_connect.run_auto_vpn()
        if not vpn_auto_connect.is_vpn_connected():
            print("[ERROR] Gagal menyambungkan VPN. Scraping dihentikan demi keamanan.")
            return
    else:
        print("[SUCCESS] VPN BPS aktif/terhubung.")
        
    for idx in selected_indices:
        section = sections[idx - 1]
        profile = config[section]
        scrape_type = profile.get("type", "scrape_fasihsm_rekap").strip().lower()
        
        print(f"\n\n{'='*50}")
        print(f"[RUNNING] Memproses Kegiatan: {section} (Tipe: {scrape_type.upper()}) (Profil ke-{idx} dari {len(sections)})")
        print(f"{'='*50}")
        
        try:
            # Pastikan chrome dari sesi sebelumnya sudah mati (khusus CDP)
            scrape_fasihsm_rekap.force_kill_cdp_chrome()
            
            if scrape_type == "scrape_fasihsm_rekap":
                print(f"\n--- Tahap 1: Scraping Data BPS Fasih ({section}) ---")
                csv_filename = scrape_fasihsm_rekap.run(auto_profile_idx=idx)
                
                if not csv_filename or not os.path.exists(csv_filename):
                    print(f"[WARN] Scraping gagal atau tidak menghasilkan file CSV untuk {section}. Melewati export...")
                    continue
                    
                print(f"\n--- Tahap 2: Export ke Google Sheets ({section}) ---")
                export_to_sheets.main(auto_profile_idx=idx, auto_csv_path=csv_filename)
                
            elif scrape_type == "scrape_ksa_padi":
                print(f"\n--- Scraping & Export KSA PADI ({section}) ---")
                scrape_ksa_padi.run_scrape(auto_profile_idx=idx)
                
            elif scrape_type == "scrape_ksa_jagung":
                print(f"\n--- Scraping & Export KSA JAGUNG ({section}) ---")
                scrape_ksa_jagung.run_scrape(auto_profile_idx=idx)
                
            elif scrape_type == "scrape_fasihdb_raw":
                print(f"\n--- Scraping & Export FASIH DB RAW ({section}) ---")
                scrape_fasihdb_raw.run_scrape(auto_profile_idx=idx)
                
            else:
                print(f"[ERROR] Tipe scraping '{scrape_type}' tidak dikenal. Melewati...")
            
        except Exception as e:
            print(f"[ERROR] Terjadi kesalahan saat memproses {section}: {e}")
        finally:
            # Pastikan chrome mati di akhir setiap iterasi
            scrape_fasihsm_rekap.force_kill_cdp_chrome()
            
    print("\n[SUCCESS] Semua kegiatan telah selesai diproses secara otomatis!")

if __name__ == "__main__":
    main()
