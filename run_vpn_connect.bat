@echo off
title Auto Connect VPN BPS
color 0A

echo ==================================================
echo MEMULAI KONEKSI OTOMATIS VPN BPS
echo ==================================================
echo.
echo Pastikan tidak ada intervensi mouse/keyboard selama proses berlangsung
echo karena skrip menggunakan UI Automation.
echo.

python "%~dp0vpn_auto_connect.py"

echo.
echo ==================================================
echo PROSES SELESAI
echo ==================================================
pause
