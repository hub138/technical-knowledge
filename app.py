#!/usr/bin/env python3
"""Live server for the technical-knowledge site.

The site is static, so a source save is immediately served.  The browser also
polls ``/api/status`` and reloads itself when index.html changes.
"""
import argparse
import hashlib
import http.server
import json
import os
import signal
import socket
import socketserver
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

PORT = 8080
DIRECTORY = Path(__file__).parent.resolve()
ENTRY = "index.html"
PID_FILE = DIRECTORY / ".technical-knowledge.pid"
LOG_FILE = DIRECTORY / ".technical-knowledge.log"


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
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)

    def send_status(self, include_body):
        content = (DIRECTORY / ENTRY).read_bytes()
        payload = json.dumps(
            {
                "version": hashlib.sha256(content).hexdigest()[:16],
                "updated_at": int((DIRECTORY / ENTRY).stat().st_mtime),
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if include_body:
            self.wfile.write(payload)

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/api/status":
            self.send_status(include_body=True)
            return
        return super().do_GET()

    def do_HEAD(self):
        if self.path.split("?", 1)[0] == "/api/status":
            self.send_status(include_body=False)
            return
        return super().do_HEAD()

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Connection", "close")
        super().end_headers()


class ThreadingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def parse_args():
    parser = argparse.ArgumentParser(description="Serve the Agent knowledge site with live refresh.")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: all interfaces)")
    parser.add_argument("--port", type=int, default=PORT, help=f"TCP port (default: {PORT})")
    parser.add_argument("--no-browser", action="store_true", help="Do not try to open a browser")
    parser.add_argument("--daemon", action="store_true", help="Start a detached server and return")
    parser.add_argument("--stop", action="store_true", help="Stop the detached server")
    return parser.parse_args()


def read_pid():
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return None


def pid_is_running(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def stop_daemon():
    pid = read_pid()
    if not pid or not pid_is_running(pid):
        PID_FILE.unlink(missing_ok=True)
        print("没有正在运行的守护进程。")
        return
    os.kill(pid, signal.SIGTERM)
    PID_FILE.unlink(missing_ok=True)
    print(f"已停止守护进程 (PID {pid})。")


def start_daemon(args):
    existing = read_pid()
    if existing and pid_is_running(existing):
        print(f"守护进程已在运行 (PID {existing})。")
        return
    PID_FILE.unlink(missing_ok=True)
    command = [sys.executable, str(Path(__file__).resolve()), "--host", args.host, "--port", str(args.port), "--no-browser"]
    with LOG_FILE.open("a", encoding="utf-8") as log:
        log.write(f"\n--- started {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    PID_FILE.write_text(str(process.pid), encoding="utf-8")
    print(f"守护进程已启动 (PID {process.pid})。")
    print(f"局域网地址: http://{get_lan_ip()}:{args.port}/{ENTRY}")
    print(f"日志: {LOG_FILE}")


def serve(args):
    os.chdir(DIRECTORY)
    lan_ip = get_lan_ip()
    url = f"http://{lan_ip}:{args.port}/{ENTRY}"
    with ThreadingServer((args.host, args.port), Handler) as server:
        print(f"服务已启动: {url}", flush=True)
        print(f"本机备用地址: http://127.0.0.1:{args.port}/{ENTRY}", flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n服务已停止")


if __name__ == "__main__":
    arguments = parse_args()
    if arguments.stop:
        stop_daemon()
    elif arguments.daemon:
        start_daemon(arguments)
    else:
        serve(arguments)
