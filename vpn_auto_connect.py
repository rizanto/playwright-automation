import os
import sys
import time
import socket
import subprocess

def load_vpn_credentials():
    import configparser
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Coba dari automation/config.txt dulu
    auto_config = os.path.join(current_dir, "automation", "config.txt")
    if os.path.exists(auto_config):
        cfg = configparser.ConfigParser()
        cfg.read(auto_config)
        if "Automation" in cfg:
            user = cfg["Automation"].get("username", "")
            pwd = cfg["Automation"].get("password", "")
            if user and pwd:
                return user, pwd
                
    # Kalau tidak ada, coba dari scraping/config.txt
    scrape_config = os.path.join(current_dir, "scraping", "config.txt")
    if os.path.exists(scrape_config):
        cfg = configparser.ConfigParser()
        cfg.read(scrape_config)
        sections = cfg.sections()
        if sections:
            for sec in sections:
                user = cfg[sec].get("username", "")
                pwd = cfg[sec].get("password", "")
                if user and pwd:
                    return user, pwd
                    
    print("[ERROR] Kredensial VPN tidak ditemukan di automation/config.txt atau scraping/config.txt.")
    sys.exit(1)

def is_vpn_connected():
    """Memeriksa apakah VPN aktif dengan mencoba melakukan koneksi socket ke host internal BPS."""
    for attempt in range(2):
        try:
            socket.setdefaulttimeout(8)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("fasih-sm.bps.go.id", 443))
            s.close()
            return True
        except Exception:
            import time
            time.sleep(2)
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
    print("[INFO] Mengaktifkan FortiClient dan mencari tombol Connect via UI Automation...")
    fallback_script = """
    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName UIAutomationTypes
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
            Start-Sleep -Milliseconds 1500
            
            $root = [System.Windows.Automation.AutomationElement]::RootElement
            $fortiWin = $root.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition) | Where-Object { $_.Current.Name -match "FortiClient" } | Select-Object -First 1
            
            if ($fortiWin) {
                Write-Output 'Mencari tombol Connect secara programatik (UIA)...'
                try {
                    $fortiWin.SetFocus()
                } catch {
                    Write-Output "WARN: Jendela utama tidak bisa menerima SetFocus, melanjutkan..."
                }
                Start-Sleep -Milliseconds 500
                
                $buttonCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button)
                $buttons = $fortiWin.FindAll([System.Windows.Automation.TreeScope]::Descendants, $buttonCond)
                
                $connectBtn = $buttons | Where-Object { $_.Current.Name -match "(?i)Connect|SAML Login" } | Select-Object -First 1
                
                if ($connectBtn) {
                    Write-Output "Ditemukan tombol: $($connectBtn.Current.Name). Mencoba InvokePattern..."
                    try {
                        $invokePattern = $connectBtn.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern) -as [System.Windows.Automation.InvokePattern]
                        if ($null -eq $invokePattern) { throw "No InvokePattern" }
                        $invokePattern.Invoke()
                        Write-Output "SUKSES: Tombol diklik secara native via InvokePattern."
                    } catch {
                        Write-Output "WARN: InvokePattern tidak didukung. Mengirim tombol ENTER ke jendela utama."
                        [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
                    }
                } else {
                    $disconnectBtn = $buttons | Where-Object { $_.Current.Name -match "(?i)Disconnect" } | Select-Object -First 1
                    if ($disconnectBtn) {
                        Write-Output "INFO: VPN sudah terhubung (tombol Disconnect ditemukan). Tidak perlu ditekan."
                    } else {
                        Write-Output "WARN: Tombol Connect tidak ditemukan di UIA tree. Memulai navigasi keyboard (TAB 6x lalu ENTER)..."
                        for ($i=1; $i -le 6; $i++) {
                            [System.Windows.Forms.SendKeys]::SendWait("{TAB}")
                            Start-Sleep -Milliseconds 150
                        }
                        Start-Sleep -Milliseconds 200
                        [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
                        Write-Output "SUKSES: Navigasi keyboard (TAB 6x + ENTER) telah dieksekusi."
                    }
                }
            } else {
                Write-Output 'ERROR: Jendela UIA FortiClient tidak terdeteksi.'
            }
        } catch {
            Write-Output "ERROR: Gagal memanipulasi jendela: $_"
        }
    } else {
        Write-Output 'ERROR: Proses FortiClient tidak ditemukan.'
    }
    """
    res = subprocess.run(["powershell", "-Command", fallback_script], capture_output=True, text=True)
    print(f"[WIN32 UIA] {res.stdout.strip()}")

def handle_embedded_login_popup(username, password):
    """Mendeteksi jendela pop-up login SSO internal FortiClient dan mengisi kredensial secara persisten."""
    print("[INFO] Menunggu kemunculan jendela login SSO internal BPS...")
    login_script = rf"""
    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName UIAutomationTypes
    Add-Type -AssemblyName Microsoft.VisualBasic
    Add-Type -AssemblyName System.Windows.Forms
    
    $timeout = 25
    $elapsed = 0
    $found = $false
    
    $root = [System.Windows.Automation.AutomationElement]::RootElement
    
    try {{
        while (-not $found -and $elapsed -lt $timeout) {{
            $allWindows = $root.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
            
            $loginWin = $allWindows | Where-Object {{ $_.Current.Name -match "(?i)Single Sign-On BPS|FortiClient \(\d+\)|Masuk" }} | Select-Object -First 1
            
            if (-not $loginWin) {{
                $fortiWin = $allWindows | Where-Object {{ $_.Current.Name -like "*FortiClient*" }} | Select-Object -First 1
                if ($fortiWin) {{
                    $descendants = $fortiWin.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
                    $loginWin = $descendants | Where-Object {{ $_.Current.Name -match "(?i)Single Sign-On BPS|FortiClient \(\d+\)|Masuk" }} | Select-Object -First 1
                }}
            }}
        
            if ($loginWin) {{
                $found = $true
                $winTitle = $loginWin.Current.Name
                Write-Output "Jendela login terdeteksi: '$winTitle'"
                
                Write-Output "Memulai Injeksi Agresif Berulang (Mencegah Telat & Terlalu Cepat)..."
                
                $maxRetries = 15 # 15 * 5 detik = 75 detik maksimal
                $attempt = 0
                
                while ($loginWin -and $attempt -lt $maxRetries) {{
                    $attempt++
                    Write-Output "Percobaan Injeksi ke-$attempt..."
                    
                    # Bawa jendela ke depan
                    [Microsoft.VisualBasic.Interaction]::AppActivate($loginWin.Current.ProcessId)
                    Start-Sleep -Milliseconds 800
                    
                    try {{
                        $loginWin.SetFocus()
                    }} catch {{}}
                    Start-Sleep -Milliseconds 200
                    
                    # Hapus isi sebelumnya (jika ada), lalu ketik username & password
                    [System.Windows.Forms.SendKeys]::SendWait("^{{a}}{{BACKSPACE}}")
                    Start-Sleep -Milliseconds 100
                    [System.Windows.Forms.SendKeys]::SendWait("{username}")
                    Start-Sleep -Milliseconds 200
                    [System.Windows.Forms.SendKeys]::SendWait("{{TAB}}")
                    Start-Sleep -Milliseconds 200
                    [System.Windows.Forms.SendKeys]::SendWait("{password}")
                    Start-Sleep -Milliseconds 200
                    [System.Windows.Forms.SendKeys]::SendWait("{{ENTER}}")
                    
                    # Tunggu 5 detik, beri waktu login terproses atau halaman termuat
                    Start-Sleep -Seconds 5
                    
                    # Cek ulang apakah jendela SSO masih ada
                    $allWindows = $root.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
                    $loginWin = $allWindows | Where-Object {{ $_.Current.Name -match "(?i)Single Sign-On BPS|FortiClient \(\d+\)|Masuk" -and $_.Current.ProcessId -eq $loginWin.Current.ProcessId }} | Select-Object -First 1
                    
                    if (-not $loginWin) {{
                        Write-Output "SUKSES: Jendela SSO tertutup! Login berhasil diproses."
                        break
                    }}
                }}
                
                if ($loginWin) {{
                    Write-Output "WARN: Gagal login setelah $maxRetries percobaan."
                }}
            }} else {{
                Start-Sleep -Seconds 1
                $elapsed++
            }}
        }}
        if (-not $found) {{
            Write-Output "WARN: Jendela login SSO tidak terdeteksi dalam $timeout detik."
        }}
    }} catch {{
        Write-Output "ERROR: $_"
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
        
    username, password = load_vpn_credentials()
        
    # 1. Jalankan FortiClient GUI
    if not start_forticlient():
        return
        
    # 2. Picu tombol SAML Login
    trigger_forticlient_saml_login()
    
    # 3. Tangani jendela login internal yang muncul
    handle_embedded_login_popup(username, password)
    
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

