import os
import sys
import time
import socket
import subprocess

USERNAME = "ilham.rizanto"
PASSWORD = "Akun0000"

def is_vpn_connected():
    """Memeriksa apakah VPN aktif dengan mencoba melakukan koneksi socket ke host internal BPS."""
    try:
        socket.setdefaulttimeout(2)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("fasih-sm.bps.go.id", 443))
        s.close()
        return True
    except Exception:
        return False

def start_forticlient():
    """Membuka FortiClient secara bersih dengan membersihkan instance ganda agar tidak crash."""
    try:
        subprocess.run("taskkill /F /IM FortiClient.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)
    except:
        pass

    forticlient_path = r"C:\Program Files\Fortinet\FortiClient\FortiClient.exe"
    if os.path.exists(forticlient_path):
        print("[INFO] Menjalankan FortiClient GUI baru...")
        subprocess.Popen([forticlient_path], cwd=r"C:\Program Files\Fortinet\FortiClient", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(6)  # Tunggu GUI FortiClient terbuka
        return True
    else:
        print("[ERROR] FortiClient tidak ditemukan di Program Files.")
        return False

def trigger_forticlient_saml_login():
    """Memicu klik tombol SAML Login pada jendela FortiClient menggunakan UI Automation untuk fokus dan SendKeys untuk navigasi."""
    print("[INFO] Mengirim perintah fokus dan klik SAML Login (TAB, ENTER, DOWN, ENTER, TAB 3x, ENTER)...")
    fallback_script = """
    Add-Type -AssemblyName Microsoft.VisualBasic
    Add-Type -AssemblyName System.Windows.Forms
    
    $timeout = 15
    $elapsed = 0
    $process = $null
    
    while (-not $process -and $elapsed -lt $timeout) {
        $process = Get-Process | Where-Object { $_.MainWindowTitle -like '*FortiClient*' } | Select-Object -First 1
        if (-not $process) {
            Start-Sleep -Seconds 1
            $elapsed++
        }
    }
    
    if ($process) {
        try {
            [Microsoft.VisualBasic.Interaction]::AppActivate($process.Id)
            Start-Sleep -Milliseconds 800
            
            [System.Windows.Forms.SendKeys]::SendWait('{TAB}')
            Start-Sleep -Milliseconds 200
            [System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
            Start-Sleep -Milliseconds 200
            [System.Windows.Forms.SendKeys]::SendWait('{DOWN}')
            Start-Sleep -Milliseconds 200
            [System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
            Start-Sleep -Milliseconds 200
            [System.Windows.Forms.SendKeys]::SendWait('{TAB 3}')
            Start-Sleep -Milliseconds 200
            [System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
            Write-Output 'SUKSES: Fokus berhasil dan tombol navigasi terkirim.'
        } catch {
            Write-Output "ERROR: Gagal memfokuskan jendela: $_"
        }
    } else {
        Write-Output 'ERROR: Jendela FortiClient tidak ditemukan.'
    }
    """
    res = subprocess.run(["powershell", "-Command", fallback_script], capture_output=True, text=True)
    print(f"[WIN32 KEY] {res.stdout.strip()}")

def handle_embedded_login_popup():
    """Mendeteksi jendela pop-up login SSO internal FortiClient dan mengisi kredensial via SendKeys."""
    print("[INFO] Menunggu kemunculan jendela login SSO internal BPS...")
    login_script = rf"""
    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName Microsoft.VisualBasic
    Add-Type -AssemblyName System.Windows.Forms
    
    $timeout = 25
    $elapsed = 0
    $found = $false
    
    $root = [System.Windows.Automation.AutomationElement]::RootElement
    
    while (-not $found -and $elapsed -lt $timeout) {{
        $allWindows = $root.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
        
        # 1. Cari di level atas (Desktop root)
        $loginWin = $allWindows | Where-Object {{ $_.Current.Name -match "Single Sign-On BPS|FortiClient \(\d+\)" }} | Select-Object -First 1
        
        # 2. Jika tidak ditemukan, cari sebagai descendant dari jendela utama FortiClient
        if (-not $loginWin) {{
            $fortiWin = $allWindows | Where-Object {{ $_.Current.Name -like "*FortiClient*" }} | Select-Object -First 1
            if ($fortiWin) {{
                $descendants = $fortiWin.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
                $loginWin = $descendants | Where-Object {{ $_.Current.Name -match "Single Sign-On BPS|FortiClient \(\d+\)" }} | Select-Object -First 1
            }}
        }}
        
        if ($loginWin) {{
            $found = $true
            $winTitle = $loginWin.Current.Name
            Write-Output "Jendela login terdeteksi: '$winTitle'"
            
            # Berikan jeda kecil agar form input siap menerima fokus
            Start-Sleep -Seconds 2
            
            # Aktifkan jendela login
            [Microsoft.VisualBasic.Interaction]::AppActivate($loginWin.Current.ProcessId)
            $loginWin.SetFocus()
            Start-Sleep -Milliseconds 500
            
            # Kirim Username, TAB, Password, ENTER
            Write-Output "Mengirimkan kredensial login..."
            [System.Windows.Forms.SendKeys]::SendWait("{USERNAME}")
            Start-Sleep -Milliseconds 200
            [System.Windows.Forms.SendKeys]::SendWait("{{TAB}}")
            Start-Sleep -Milliseconds 200
            [System.Windows.Forms.SendKeys]::SendWait("{PASSWORD}")
            Start-Sleep -Milliseconds 200
            [System.Windows.Forms.SendKeys]::SendWait("{{ENTER}}")
            Write-Output "SUKSES: Form login disubmit."
            break
        }}
        Start-Sleep -Seconds 1
        $elapsed++
    }}
    if (-not $found) {{
        Write-Output "WARN: Jendela login SSO internal tidak terdeteksi dalam 25 detik."
    }}
    """
    
    try:
        res = subprocess.run(
            ["powershell", "-Command", login_script],
            capture_output=True,
            text=True
        )
        print(f"[LOGIN AUTOMATION] {res.stdout.strip()}")
    except Exception as e:
        print(f"[WARN] Gagal mengotomatiskan login SSO internal: {e}")

def run_auto_vpn():
    print("=== AUTO CONNECT BPS VPN (100% Hands-Free - Embedded) ===")
    
    # 0. Cek apakah VPN sudah tersambung sebelumnya
    print("[INFO] Memeriksa status koneksi VPN saat ini...")
    if is_vpn_connected():
        print("[SUCCESS] VPN BPS sudah aktif/tersambung. Tidak perlu menghubungkan ulang.")
        return
        
    # 1. Jalankan FortiClient GUI
    if not start_forticlient():
        return
        
    # 2. Picu tombol SAML Login
    trigger_forticlient_saml_login()
    
    # 3. Tangani jendela login internal yang muncul
    handle_embedded_login_popup()
    
    # 4. Tunggu deteksi koneksi VPN aktif
    print("[INFO] Memantau status koneksi VPN internal BPS...")
    timeout_seconds = 45
    start_time = time.time()
    connected = False
    
    while (time.time() - start_time) < timeout_seconds:
        if is_vpn_connected():
            print("[SUCCESS] VPN BPS berhasil terdeteksi AKTIF/TERSAMBUNG!")
            connected = True
            break
        time.sleep(1)
        
    if not connected:
        print(f"[WARN] VPN tidak tersambung dalam {timeout_seconds} detik.")
        print("[TIPS] Pastikan akun Anda aktif dan terhubung ke jaringan internet dengan lancar.")

if __name__ == "__main__":
    run_auto_vpn()
