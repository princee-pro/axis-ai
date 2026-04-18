import time, urllib.request, os

token = os.environ.get('AXIS_TOKEN')
req_headers = {'X-Jarvis-Token': token}

endpoints = [
    '/health',
    '/health',   # 2nd call to verify cache
    '/llm/models',
    '/llm/models', # 2nd call to verify cache
    '/whoami',
    '/goals',
    '/control/summary',
]

print('Post-Fix API Benchmarks:')
for ep in endpoints:
    start = time.perf_counter()
    req = urllib.request.Request(f'http://127.0.0.1:8001{ep}', headers=req_headers)
    try:
        urllib.request.urlopen(req)
        status = 'OK'
    except Exception as e:
        status = str(e)[:40]
    ms = (time.perf_counter() - start) * 1000
    print(f'{ep:<25} | {ms:>6.2f} ms | {status}')
