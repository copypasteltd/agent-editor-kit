"""Bounded one-client native LAN transfer of explicitly pinned local artifacts."""
import hashlib
import http.server
import json
from pathlib import Path
import secrets
import socket
import sys
import time
import urllib.parse


ROOT = Path(__file__).resolve().parent
config = json.loads((ROOT / 'parcels.json').read_bytes())
files = {row['name']: row for row in config['files']}
token = secrets.token_urlsafe(32)
started = time.monotonic()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parts = urllib.parse.urlsplit(self.path)
        name = parts.path.removeprefix('/' + token + '/')
        if (self.client_address[0] != config['remote_ip'] or parts.query or parts.fragment
                or not parts.path.startswith('/' + token + '/') or name not in files):
            self.send_error(404)
            return
        row = files[name]
        path = Path(row['path'])
        if not path.is_file() or path.stat().st_size != row['bytes']:
            self.send_error(409)
            return
        self.send_response(200)
        self.send_header('Content-Length', str(row['bytes']))
        self.send_header('Content-Type', 'application/octet-stream')
        self.end_headers()
        with path.open('rb') as stream:
            while block := stream.read(1024**2):
                self.wfile.write(block)

    def log_message(self, format, *args):
        # No access token or request URL in process logs.
        print(json.dumps(dict(remote=self.client_address[0], event='transfer-request')), flush=True)


with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route:
    route.connect((config['remote_ip'], 8000))
    host = route.getsockname()[0]
with http.server.ThreadingHTTPServer((host, 0), Handler) as server:
    server.timeout = 1
    public = {k: v for k, v in config.items() if k != 'files'}
    public.update(base_url='http://' + host + ':' + str(server.server_port) + '/' + token,
                  files=[{k: v for k, v in row.items() if k != 'path'} for row in config['files']])
    (ROOT / 'transfer.json').write_text(json.dumps(public, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(status='serving', host=host, port=server.server_port)), flush=True)
    while time.monotonic()-started < 1800 and not (ROOT / 'stop-transfer.marker').exists():
        server.handle_request()
