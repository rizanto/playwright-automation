# Playwright Automation (Fasih Scrape & Anomaly Automation)

Proyek ini berisi sekumpulan skrip otomasi browser berbasis **Playwright** yang dirancang untuk mempermudah kegiatan operasional pengumpulan dan pengolahan data BPS (Badan Pusat Statistik) secara *hands-free* dan *error-proof*.

## Struktur Repositori Terkini

Semua modul telah diorganisir ke dalam subfolder, dengan eksekusi sentral melalui satu file `.bat` di *root* untuk kemudahan penggunaan di PC mana pun.

```text
playwright-automation/
│
├── scraping/                   # Skrip khusus untuk ekstraksi (Scraping) data
│   ├── scrape_fasihsm_rekap.py # Scraper Rekap Petugas FASIH-SM
│   ├── scrape_fasihdb_raw.py   # Scraper FASIH Dashboard Raw Data
│   ├── scrape_ksa_padi.py      # Scraper KSA Padi
│   ├── scrape_ksa_jagung.py    # Scraper KSA Jagung
│   ├── export_to_sheets.py     # Modul ekspor CSV ke Google Sheets
│   ├── auto_run_all.py         # Orkestrator untuk menjalankan semua scraper
│   └── credentials.json        # [DIABAIKAN GIT] Kredensial akun Google Sheets
│
├── automation/                 # Skrip khusus untuk automasi aksi di web
│   ├── automate_anomaly_reject.py # Tindak lanjut anomali & reject form
│   └── config.txt              # [DIABAIKAN GIT] Target URL & konfigurasi lokal
│
├── autorun.bat                 # MENU INTERAKTIF UTAMA (Klik ganda untuk menjalankan)
├── autorun.py                  # CLI Menu engine
├── vpn_auto_connect.py         # Skrip otomatisasi VPN FortiClient hands-free (UIA & Win32)
├── requirements.txt            # Dependensi Python
└── README.md                   # Dokumentasi proyek
```

---

## Fitur Utama & Keunggulan

1. **Sentralisasi Menu Interaktif (`autorun.bat`)**
   Seluruh operasi (Scraping berbagai survei, Automasi Anomali, dan VPN) kini digabung ke dalam satu menu CLI interaktif. Pengguna hanya perlu mengeklik ganda `autorun.bat` tanpa perlu membuka terminal atau mengingat sintaks perintah.
2. **Otomatisasi VPN Tingkat Lanjut (*Bulletproof*)**
   Skrip `vpn_auto_connect.py` telah diperbarui dengan integrasi *Windows Native API (user32.dll)* dan UI Automation. Skrip ini akan melakukan **Window Normalization** (memaksa resolusi FortiClient ke 900x800) untuk menjamin akurasi klik SSO VPN 100% di **berbagai resolusi layar dan skala DPI (125%, 150%)**.
3. **Kategori Scraping (`scraping/`)**
   Mengambil data "Rekap Petugas" atau data mentah dasbor secara *headless/non-headless* dan mengekspor hasilnya langsung ke Google Sheets yang dituju berkat dukungan *pandas* dan *gspread*.
4. **Keamanan Anti-Bot & Ketahanan Sesi**
   * Membajak *Chrome Asli* (*Local Chrome Instance*) via *Chrome DevTools Protocol (CDP)* port 9222. Ini membuat aktivitas automasi tidak terdeteksi sebagai bot.
   * Auto-login yang bisa pulih (*recover*) sendiri saat sesi BPS terputus atau *expired*.

---

## Prasyarat (Prerequisites)

Pastikan komputer yang akan menjalankan script ini telah terpasang:
- **Python 3.8+** (Pastikan opsi "Add Python to PATH" dicentang saat instalasi)
- **Google Chrome** versi terbaru
- **FortiClient VPN** (Untuk akses internal BPS)

---

## Cara Instalasi di PC Baru

1. *Clone* atau ekstrak repositori ini ke dalam direktori PC baru.
2. Buka Terminal / Command Prompt di dalam folder proyek, lalu jalankan instalasi dependensi:
   ```bash
   pip install -r requirements.txt
   ```
3. Unduh instans chromium internal milik Playwright:
   ```bash
   playwright install chromium
   ```
4. Pindahkan file konfigurasi sensitif milik Anda (yang tidak ikut terunggah di Github) ke posisinya masing-masing:
   * **`scraping/credentials.json`** (Service Account Google Sheets)
   * **`automation/config.txt`** (Data anomali dan kredensial SSO)

---

## Cara Penggunaan Sehari-Hari

Sangat mudah! Anda tidak perlu membuka Command Prompt.
1. Masuk ke folder proyek `playwright-automation`.
2. Klik ganda pada file **`autorun.bat`**.
3. Akan muncul antarmuka menu berbasis teks (CLI).
4. Ketik angka menu yang ingin Anda jalankan (0-8) dan tekan `ENTER`.

---

## Keamanan Data (Git Security)
Proyek ini sudah dikonfigurasi dengan file `.gitignore` yang sangat ketat. File-file rahasia seperti `credentials.json`, `config.txt`, serta semua *cache* sesi peramban di dalam folder `chrome_debug_data/` tidak akan pernah terunggah ke repositori GitHub. Anda dapat melakukan `git push` dengan aman!
