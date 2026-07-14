@echo off
title Auto Scraping (Khusus Kegiatan 1)
color 0A

echo ==================================================
echo AUTO SCRAPING KHUSUS KEGIATAN 1
echo ==================================================
echo.
echo Skrip ini akan secara otomatis:
echo 1. Mengecek dan menyambungkan VPN BPS jika terputus.
echo 2. Menjalankan proses scraping latar belakang (headless) untuk Kegiatan 1.
echo 3. Mengekspor hasil scraping ke Google Sheets sesuai konfigurasi.
echo.

cd "%~dp0scraping"
python auto_run_all.py 1

echo.
echo ==================================================
echo PROSES SELESAI
echo ==================================================
exit
