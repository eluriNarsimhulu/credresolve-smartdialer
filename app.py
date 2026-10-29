from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json, os
from pathlib import Path
from urllib.parse import urlparse
from smartdialer.core import SmartDialer

ROOT = Path(__file__).resolve().parent
DB_PATH = os.environ.get('SMARTDIALER_DB', str(ROOT / 'smartdialer.db'))
app = SmartDialer(DB_PATH)

class Handler(BaseHTTPRequestHandler):
    def _send(self, status, payload, content_type='application/json; charset=utf-8'):
        body = payload if isinstance(payload, bytes) else (json.dumps(payload, default=str).encode() if content_type.startswith('application/json') else payload.encode())
        self.send_response(status); self.send_header('Content-Type', content_type); self.send_header('Content-Length', str(len(body))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(body)
    def _body(self):
        n = int(self.headers.get('Content-Length','0')); return json.loads(self.rfile.read(n) or b'{}')
    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/api/state': self._send(200, app.state()); return
        if path == '/api/health': self._send(200, {'ok': True, 'service':'credresolve-smartdialer'}); return
        file = ROOT / 'static' / ('index.html' if path == '/' else path.lstrip('/'))
        if file.resolve().parent != (ROOT/'static').resolve() or not file.is_file(): self._send(404, {'error':'not found'}); return
        content_type = 'text/html; charset=utf-8' if file.suffix == '.html' else 'text/plain; charset=utf-8'
        self._send(200, file.read_bytes(), content_type)
    def do_POST(self):
        try:
            path, data = urlparse(self.path).path, self._body()
            if path == '/api/dial': result = app.dial(data.get('mode','progressive'), data.get('requested'), data.get('provider','A'))
            elif path == '/api/simulate': result = app.simulate(data.get('scenario','normal'), data.get('mode','progressive'), data.get('requested'), data.get('provider'))
            elif path == '/api/event': result = app.provider_event(data['call_id'], data['event_type'], data.get('event_id'))
            elif path == '/api/seed': app.seed_demo(int(data.get('agents',5)), int(data.get('borrowers',20))); result = {'ok':True}
            elif path == '/api/agent-drop': result = app.simulate_agent_drop(int(data.get('count',1)))
            elif path == '/api/recover': result = app.recover_stale_calls(float(data.get('stale_seconds',30)))
            else: self._send(404, {'error':'not found'}); return
            self._send(200, result)
        except (ValueError, KeyError, TypeError) as e: self._send(400, {'error':str(e)})
        except Exception as e: self._send(500, {'error':'internal error','detail':str(e)})
    def log_message(self, fmt, *args): print('[http]', fmt % args)

if __name__ == '__main__':
    host, port = os.environ.get('HOST','127.0.0.1'), int(os.environ.get('PORT','8000'))
    print(f'SmartDialer running at http://{host}:{port}')
    ThreadingHTTPServer((host,port), Handler).serve_forever()
