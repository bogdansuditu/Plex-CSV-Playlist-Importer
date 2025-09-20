import socket
host = "172.19.35.2"          # or whatever you want to testport = 32400
port = 32400
s = socket.socket()
s.settimeout(5)
try:
    s.connect((host, port))
    print("Connected OK")
except Exception as exc:
    print(f"Connection failed: {exc}")
finally:
    s.close()