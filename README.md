# Playwright Automation (Fasih Scrape & Anomaly Automation)

Proyek ini berisi kumpulan skrip otomatisasi browser menggunakan Playwright untuk mempermudah kegiatan operasional pengumpulan dan pengolahan data BPS (Badan Pusat Statistik).

## Struktur Repositori

Repositori ini ditata ke dalam kategori yang rapi agar modul yang bersifat umum tidak bercampur dengan skrip khusus:

```text
playwright-automation/
│
├── scraping/                   # Kategori skrip khusus untuk Scraping data
│   ├── config.txt              # Konfigurasi target scraping & credentials akun
│   ├── scrape_fasihsm_rekap.py # Scraper Rekap Petugas FASIH-SM
│   ├── scrape_fasihdb_raw.py   # Scraper FASIH Dashboard Raw Data
│   ├── scrape_ksa_padi.py      # Scraper KSA Padi
│   ├── scrape_ksa_jagung.py    # Scraper KSA Jagung
│   ├── export_to_sheets.py     # Modul ekspor CSV ke Google Sheets
│   ├── auto_run_all.py         # Orkestrator untuk menjalankan semua scraper sekaligus
│   └── START_SCRAPER.bat       # Menu interaktif sekali klik untuk Windows (Scraping)
│
├── automation/                 # Kategori skrip khusus untuk Automasi operasional web
│   ├── config.txt              # Konfigurasi akun BPS & Target URL anomali
│   ├── automate_anomaly_reject.py # Skrip automasi tindak lanjut anomali & reject
│   └── START_AUTOMATION.bat    # Batch file sekali klik untuk memicu automasi
│
├── vpn_auto_connect.py         # [UMUM] Skrip otomatisasi VPN FortiClient hands-free (di root)
├── credentials.json            # [UMUM] Akses Google API (di root)
├── scrape_results/             # [UMUM] Folder output file CSV hasil scraping
├── requirements.txt            # Dependensi Python
└── README.md                   # Dokumentasi proyek
```

---

## Fitur Utama

1. **Otomatisasi VPN Hands-Free (`vpn_auto_connect.py`)**:
   Membuka, memfokuskan, dan mengotomatiskan penekanan tombol login SAML FortiClient secara otomatis (mengatasi kendala integrasi Windows API & UI Automation).
2. **Kategori Scraping (`scraping/`)**:
   Mengambil data "Rekap Petugas" atau data mentah dasbor dari berbagai survei BPS (FASIH-SM, KSA, Dashboard Superset) secara berkala dan mengekspor hasilnya langsung ke Google Sheets.
3. **Kategori Automasi (`automation/`)**:
   Menindaklanjuti data anomali pada tugas petugas, mengisi form catatan anomali secara terprogram, menyembuhkan bug UI form, dan melakukan penolakan (Reject) tugas petugas yang salah.
4. **Keamanan & Ketahanan Sesi (Resiliency)**:
   * Menggunakan *Chrome asli* via CDP port 9222 untuk menghindari proteksi anti-bot.
   * Auto-login ulang secara otomatis di tab baru ketika sesi/cookies web kedaluwarsa di tengah jalan.
   * Terintegrasi dengan VPN: jika koneksi internet terputus di tengah jalan, skrip akan mendeteksinya dan memicu penyambungan VPN kembali secara dinamis.

---

## Prasyarat (Prerequisites)

Pastikan Anda sudah menginstal aplikasi berikut di komputer Anda:
- **Python 3.8+**
- **Google Chrome** (yang asli, terinstal di OS)
- **FortiClient** (untuk kebutuhan VPN BPS)

---

## Cara Instalasi & Setup

1. Buka terminal atau Command Prompt di folder proyek ini.
2. Instal semua dependensi Python:
   ```bash
   pip install -r requirements.txt
   ```
3. Unduh browser khusus driver Playwright:
   ```bash
   playwright install chromium
   ```
4. Taruh file **`credentials.json`** Google Service Account Anda di folder root.

---

## Cara Penggunaan

### 1. Untuk Scraping Data
* Buka folder **`scraping/`**.
* Sesuaikan target unduhan Anda pada file `scraping/config.txt`.
* Klik ganda (double-click) **`START_SCRAPER.bat`** untuk membuka menu interaktif.

### 2. Untuk Automasi Tindak Lanjut Anomali
* Buka folder **`automation/`**.
* Sesuaikan kredensial dan URL target detail assignment Anda pada file `automation/config.txt`.
* Klik ganda (double-click) **`START_AUTOMATION.bat`** untuk menjalankan automasi.

---

## Catatan Penting Pengambangan
File-file kredensial seperti `config.txt` dan `credentials.json` sudah diabaikan lewat `.gitignore` agar aman dari resiko kebocoran data saat Anda membagikan kode ini ke Github.
