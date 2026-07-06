# Fasih Scrape & Auto-Export Google Sheets

Proyek ini adalah *tool* otomatisasi untuk mengambil data "Rekap Petugas" dari web aplikasi FASIH BPS (Badan Pusat Statistik) dan langsung mengekspor hasilnya ke dalam Google Sheets secara otomatis.

## Fitur
1. **Scraping Anti-Bot**: Menggunakan Chromium lewat Playwright dengan mode CDP untuk membypass deteksi bot.
2. **Auto Run All**: Bisa menjalankan proses scraping dan *export* secara berurutan untuk banyak kegiatan sekaligus.
3. **Pembersihan Sesi (Clean Session)**: Setiap iterasi dipastikan berjalan dari nol tanpa ada _cookies_ atau _session_ yang menyangkut dari tugas sebelumnya.

## Prasyarat (Prerequisites)
Pastikan Anda sudah menginstal aplikasi berikut di komputer Anda:
- **Python 3.8+**
- **Google Chrome** (yang asli, terinstal di OS)

## Cara Instalasi

1. **Klon atau unduh (Download) repositori ini** ke komputer Anda.
2. Buka terminal atau Command Prompt di folder proyek ini.
3. Instal semua _library_ Python yang dibutuhkan:
   ```bash
   pip install -r requirements.txt
   ```
4. Unduh browser khusus (_headless_ driver) bawaan Playwright:
   ```bash
   playwright install chromium
   ```

## Persiapan Konfigurasi (Setup)

### 1. `config.txt` (Kredensial Akun BPS & Target URL)
- Buat sebuah file bernama `config.txt` (Anda bisa menyalin dari `config.example.txt` jika tersedia).
- Isi dengan struktur seperti di bawah ini untuk setiap kegiatan yang mau ditarik datanya:
```ini
[Nama Kegiatan Bebas]
username = username.bps.anda
password = password.bps.anda
target_url = https://fasih-sm.bps.go.id/app/surveys/xxxxxxxx-xxxx.../yyyyyyyy-yyyy...
target_role = Pencacah
sheet_url = https://docs.google.com/spreadsheets/d/xxxxxxxxxxxxxx/edit?usp=sharing
sheet_tab_name = namatab
```

### 2. `credentials.json` (Akses Google Sheets)
Agar skrip bisa menulis ke Google Sheets, Anda butuh Google Service Account:
1. Pergi ke [Google Cloud Console](https://console.cloud.google.com/).
2. Buat _Project_ baru.
3. Aktifkan (Enable) **Google Sheets API** dan **Google Drive API**.
4. Buat kredensial baru melalui menu **Credentials** -> **Create Credentials** -> **Service Account**.
5. Buka tab **Keys** pada _Service Account_ tersebut -> **Add Key** -> **Create new key** -> pilih format **JSON**.
6. Simpan file yang terunduh tersebut ke folder proyek ini dengan nama persis **`credentials.json`**.
7. Buka Google Sheet target Anda, klik **Share**, lalu tambahkan *email service account* (akhiran `@...iam.gserviceaccount.com` yang ada di dalam `credentials.json`) sebagai **Editor**.

## Cara Penggunaan

Terdapat tiga skrip utama yang bisa dijalankan:

### Menjalankan Seluruh Proses Sekaligus (Direkomendasikan)
Menjalankan _scraping_ dan _export_ secara estafet untuk seluruh _section_ profil yang ada di dalam `config.txt`:
```bash
python auto_run_all.py
```
*(Proses akan berjalan di _background_ secara _headless_ dan senyap).*

### Menjalankan Secara Manual 
Jika Anda hanya ingin menjalankan per bagian, Anda bisa menjalankannya mandiri dan akan muncul menu interaktif di layar:

1. Scraping data ke file CSV lokal (menyala otomatis / GUI Mode):
   ```bash
   python scrape_fasihsm_rekap.py
   ```
   Atau jika ingin _headless_:
   ```bash
   python scrape_fasihsm_rekap.py --headless
   ```

2. Mengirim file CSV lokal ke Google Sheets:
   ```bash
   python export_to_sheets.py
   ```

## Catatan Keamanan
- File **`config.txt`** dan **`credentials.json`** memuat rahasia (password & private key). File-file ini sudah dimasukkan ke dalam `.gitignore` agar tidak bocor dan tidak terunggah ke repositori Github (jika Anda mem-push). Jangan pernah mengirim file tersebut ke publik!
