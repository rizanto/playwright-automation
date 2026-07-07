import socket

hosts = ["google.com", "fasih-dashboard.bps.go.id", "sso.bps.go.id", "manajemen-ksapro.bps.go.id"]
for host in hosts:
    try:
        ip = socket.gethostbyname(host)
        print(f"{host} resolved to {ip}")
    except Exception as e:
        print(f"Failed to resolve {host}: {e}")
