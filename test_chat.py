import sys, os, urllib.request, json
try:
    req = urllib.request.Request('http://127.0.0.1:8001/chat', data=json.dumps({"conversation_id": "test", "message": "hello"}).encode(), headers={"Content-Type": "application/json", "X-Jarvis-Token": "57d3231eca3d502f22d4e51bcfcb377d0937cc3a67b3ceb3948624d33ffe411a"})
    print(urllib.request.urlopen(req).read())
except Exception as e:
    import urllib.error
    if isinstance(e, urllib.error.HTTPError):
        print("HTTP ERROR:", e.code, e.read())
    else:
        print("ERROR:", e)
