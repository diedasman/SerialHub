import socket
import threading

HOST = "127.0.0.1"
PORT = 5001

help_menu = [
    "AT",
    "AT+CSQ",
    "PING",
    "HELP"
]

def handle_client(conn, addr):
    print(f"Client connected: {addr}")
    conn.sendall(b"DEVICE READY\r\n")

    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break

            msg = data.decode(errors="replace").strip()
            print("RX:", msg)
                        
            if msg.upper() == "AT":
                conn.sendall(b"OK\r\n")
            elif msg.upper() == "AT+CSQ":
                conn.sendall(b"+CSQ: 15,0\r\nOK\r\n")
            elif msg.upper() == "PING":
                conn.sendall(b"PONG\r\n")
            elif msg.upper() == "HELP":
                conn.sendall(b"OK\r\n" + "\r\n".join(help_menu).encode("utf-8") + b"\r\n")
            else:
                conn.sendall(f"ECHO: {msg}\r\n".encode())
    finally:
        print(f"Client disconnected: {addr}")
        conn.close()

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
    server.bind((HOST, PORT))
    server.listen()
    print(f"Fake device listening on {HOST}:{PORT}")

    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
