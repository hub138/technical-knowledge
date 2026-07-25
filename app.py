#!/usr/bin/env python3
"""Technical knowledge site server."""
import http.server
import os
import socket
import socketserver
import webbrowser
from pathlib import Path

PORT = 8080
DIRECTORY = str(Path(__file__).parent)
ENTRY = "index.html"


def get_lan_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        sock.close()


class Handler(http.server.SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Connection", "close")
        super().end_headers()


class ThreadingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    os.chdir(DIRECTORY)
    lan_ip = get_lan_ip()
    url = f"http://{lan_ip}:{PORT}/{ENTRY}"
    with ThreadingServer(("0.0.0.0", PORT), Handler) as server:
        print(f"服务已启动: {url}", flush=True)
        print(f"本机备用地址: http://127.0.0.1:{PORT}/{ENTRY}", flush=True)
        webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n服务已停止")


if __name__ == "__main__":
    main()
