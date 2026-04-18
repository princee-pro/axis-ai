import time, urllib.request, os, json
token = os.environ.get('AXIS_TOKEN')
req_headers = {'X-Jarvis-Token': token}

endpoints = [
    '/health',
    '/llm/models',
    '/whoami',
    '/goals',
    '/control/approvals',
    '/control/permissions',
    '/status'
]

print('Baseline API Benchmarks:')
for ep in endpoints:
    start = time.perf_counter()
    req = urllib.request.Request(f'http://127.0.0.1:8001{ep}', headers=req_headers)
    try:
        urllib.request.urlopen(req)
        status = 'OK'
    except Exception as e:
        status = str(e)
    ms = (time.perf_counter() - start) * 1000
    print(f'{ep:<25} | {ms:>6.2f} ms | {status}')
