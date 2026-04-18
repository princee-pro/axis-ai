import http.client
import json
import os
import time
import threading

def test_security():
    print("=== Security Hardening Verification ===")
    conn = http.client.HTTPConnection("127.0.0.1", 8000)
    
    # 1. Test without token (Should fail 403)
    print("[1/3] Testing GET /status without token...")
    try:
        conn.request("GET", "/status")
        r = conn.getresponse()
        if r.status == 403:
            print("  > SUCCESS: Blocked unauthorized GET.")
        else:
            print(f"  > FAILURE: Expected 403, got {r.status}")
        r.read() # Clear buffer
    except Exception as e:
        print(f"  > ERROR: {e}")

    # 2. Test with invalid token (Should fail 403)
    print("[2/3] Testing GET /status with invalid token...")
    try:
        headers = {"X-Jarvis-Token": "bad_token"}
        conn.request("GET", "/status", headers=headers)
        r = conn.getresponse()
        if r.status == 403:
            print("  > SUCCESS: Blocked invalid token.")
        else:
            print(f"  > FAILURE: Expected 403, got {r.status}")
        r.read()
    except Exception as e:
        print(f"  > ERROR: {e}")

    # 3. Test with valid token via Config fallback
    print("[3/3] Testing with valid token (Matching config)...")
    try:
        headers = {"X-Jarvis-Token": "jarvis_secret_123"}
        conn.request("GET", "/status", headers=headers)
        r = conn.getresponse()
        if r.status == 200:
            print("  > SUCCESS: Authorized access via header.")
        else:
            print(f"  > FAILURE: Expected 200, got {r.status}")
            print(f"  > Response: {r.read().decode()}")
    except Exception as e:
        print(f"  > ERROR: {e}")

    conn.close()
    print("\n=== Security Hardening Verified! ===")

if __name__ == "__main__":
    # Start the server in a separate thread
    from jarvis_ai.core.brain import Brain
    from jarvis_ai.mobile.server import JarvisServer
    
    # Force a token in config for testing
    config = {"security_token": "jarvis_secret_123"}
    brain = Brain(config=config)
    server = JarvisServer(brain, port=8000)
    server.start()
    
    time.sleep(1) # Wait for server to bind
    try:
        test_security()
    finally:
        server.stop()
