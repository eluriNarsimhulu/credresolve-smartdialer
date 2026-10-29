"""Tiny local API load smoke test; server must already be running."""
import json, time, urllib.request
BASE = 'http://127.0.0.1:8000'
def call(path, body=None):
    req = urllib.request.Request(BASE+path, data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type':'application/json'}, method='POST' if body is not None else 'GET')
    with urllib.request.urlopen(req, timeout=5) as r: return json.loads(r.read())
N=100; start=time.perf_counter(); ok=0
for _ in range(N):
    try: call('/api/health'); ok += 1
    except Exception as e: print('request failed:', e)
elapsed=time.perf_counter()-start
print(f'health requests: {ok}/{N}; elapsed={elapsed:.3f}s; throughput={ok/elapsed:.1f} req/s')
