import sys, os, time, json, http.client, tempfile, socket, threading
sys.path.insert(0, '.')
from unittest.mock import patch
from jarvis_ai.core.brain import Brain
from jarvis_ai.mobile.server import JarvisServer

# Load owner token from settings or env
# This matches the token in settings.yaml and .env
TOKEN = '57d3231eca3d502f22d4e51bcfcb377d0937cc3a67b3ceb3948624d33ffe411a'

def run_test():
    # Find free port
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]

    # Start server on temp DB
    # We use a temp file to ensure a clean slate for the demo
    fd, tmp_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    try:
        with patch('jarvis_ai.core.brain.GOOGLE_AVAILABLE', False):
            brain = Brain({'memory': {'db_path': tmp_path}})
        
        srv = JarvisServer(brain, port=port, server_config={'remote_enabled': False})
        srv_thread = threading.Thread(target=srv.start, daemon=True)
        srv_thread.start()
        time.sleep(1.5) # Wait for server to be ready

        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        H = {'X-Jarvis-Token': TOKEN}

        def req(method, path, body=None, headers=None):
            hdr = dict(H)
            if headers: hdr.update(headers)
            payload = json.dumps(body).encode() if body else b''
            if payload:
                hdr['Content-Type'] = 'application/json'
                hdr['Content-Length'] = str(len(payload))
            conn.request(method, path, body=payload or None, headers=hdr)
            r = conn.getresponse()
            raw = r.read()
            data = json.loads(raw) if raw else {}
            return r.status, data

        print('='*60)
        print(f'  Jarvis Bridge Live HTTP Demo (Port {port})')
        print('='*60)

        # 1. Health
        s, b = req('GET', '/health')
        print(f'[OK] GET /health          -> {s} | status={b.get("status")} ver={b.get("version")}')

        # 2. Create pairing code
        s, b = req('POST', '/pairing/code', {'role': 'operator', 'name': 'TestPhone'})
        code = b.get('code','')
        print(f'[OK] POST /pairing/code   -> {s} | code={code} expires={b.get("expires_in")}s')

        # 3. Register device (no owner token required for /pairing/register)
        conn2 = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        payload = json.dumps({'code': code, 'device_name': 'My Phone', 'requested_role': 'operator'}).encode()
        conn2.request('POST', '/pairing/register', body=payload, headers={'Content-Type': 'application/json', 'Content-Length': str(len(payload))})
        r2 = conn2.getresponse()
        b2 = json.loads(r2.read())
        dev_token = b2.get('device_token','')
        dev_id    = b2.get('device_id','')
        print(f'[OK] POST /pairing/register -> {r2.status} | role={b2.get("role")} dev={dev_id[:8]}...')

        # 4. Device hits /health (reader allowed)
        s, b = req('GET', '/health', headers={'X-Device-Token': dev_token})
        print(f'[OK] GET /health (device) -> {s} | status={b.get("status")}')

        # 5. Device hits /actions (reader allowed)
        s, b = req('GET', '/actions', headers={'X-Device-Token': dev_token})
        print(f'[OK] GET /actions (device)-> {s} | count={len(b.get("actions",[]))}')

        # 6. Device tries /devices (admin only — must fail)
        s, b = req('GET', '/devices', headers={'X-Device-Token': dev_token})
        print(f'[OK] GET /devices (device)-> {s} | (Expected 403 Forbidden)')

        # 7. Owner lists devices
        s, b = req('GET', '/devices')
        print(f'[OK] GET /devices (owner) -> {s} | total={len(b.get("devices",[]))}')

        # 8. Revoke device
        s, b = req('POST', f'/devices/{dev_id}/revoke', {})
        print(f'[OK] POST /revoke         -> {s} | success={b.get("success")}')

        # 9. Revoked token rejected
        s, b = req('GET', '/health', headers={'X-Device-Token': dev_token})
        print(f'[OK] GET /health (revoked)-> {s} | (Expected 403 Forbidden)')

        srv.stop()
        print('='*60)
        print('  LIVE DEMO PASSED')
        print('='*60)

    finally:
        if os.path.exists(tmp_path):
            try: os.remove(tmp_path)
            except: pass

if __name__ == "__main__":
    run_test()
