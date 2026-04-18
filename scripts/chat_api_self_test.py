import os
import sys
import json
import time
import http.client
import uuid
import subprocess

# Add project root to path
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root)

def run_api_test():
    print("=== Jarvis AI Chat API Self-Test (Alternate Port) ===")
    
    # 1. Setup Environment
    token = "test_api_token_123"
    env = os.environ.copy()
    env["JARVIS_SECRET_TOKEN"] = token
    env["JARVIS_ALLOW_INSECURE_DEV"] = "1"
    env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
    
    port = 8888 # Use distinct port
    
    # Modify server.py command to take port if we want, or just rely on server.py's main.
    # Actually server.py main blocks on port 8000. I'll pass it in code if I can.
    # Wait, server.py doesn't take CLI args for port. I'll modify the test to just hope 8888 is free
    # and maybe I should modify server.py to accept a port arg.
    
    print(f"Starting server on port {port} at {root}")
    # Temporary patch to server.py in the test env for port? 
    # Better to just use a custom script in the test.
    
    server_script = f"""
from jarvis_ai.core.brain import Brain
from jarvis_ai.mobile.server import JarvisServer
import time
import os

if __name__ == "__main__":
    brain = Brain({{}})
    server = JarvisServer(brain, port={port})
    server.start()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
"""
    with open("temp_test_server.py", "w") as f:
        f.write(server_script)

    server_proc = subprocess.Popen(
        [sys.executable, "temp_test_server.py"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=root
    )
    
    # Wait for server
    print("Waiting for server to be ready...")
    ready = False
    for _ in range(15):
        if server_proc.poll() is not None:
            stdout, stderr = server_proc.communicate()
            print(f"[ERROR] Server died: {stdout} {stderr}")
            break
        time.sleep(1)
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port)
            conn.request("GET", "/health", headers={"X-Jarvis-Token": token})
            res = conn.getresponse()
            if res.status == 200:
                ready = True
                conn.close()
                break
            conn.close()
        except:
            pass
    
    if not ready:
        print(f"[ERROR] Server not ready on port {port} after 15 seconds.")
        server_proc.terminate()
        os.remove("temp_test_server.py")
        sys.exit(1)

    headers = {"X-Jarvis-Token": token, "Content-Type": "application/json"}
    
    def request(method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", port)
        conn.request(method, path, body=json.dumps(body) if body else None, headers=headers)
        res = conn.getresponse()
        data = res.read().decode()
        conn.close()
        if res.status >= 400:
            raise Exception(f"{method} {path} failed: {res.status} - {data}")
        return json.loads(data)

    try:
        # 1. Test /health
        print("Testing /health...")
        health = request("GET", "/health")
        print(f"[OK] Health check: {health}")
        
        # 2. Test /chat
        print("Testing /chat...")
        chat_data = {"message": "remember this: our secret code is 42."}
        res = request("POST", "/chat", body=chat_data)
        conv_id = res["conversation_id"]
        print(f"[OK] Chat reply received for {conv_id}")
        
        # 3. Test /conversations
        print("Testing /conversations...")
        res = request("GET", "/conversations")
        convs = res["conversations"]
        if any(c["id"] == conv_id for c in convs):
            print(f"[OK] Conversation {conv_id} listed.")
        else:
            print(f"[FAIL] Conversation {conv_id} not found.")
            sys.exit(1)
            
        # 4. Test /memories
        print("Testing /memories...")
        res = request("GET", "/memories?query=secret%20code")
        mems = res["memories"]
        if mems and "42" in mems[0]["text"]:
            print(f"[OK] Memory retrieved via API: {mems[0]['text']}")
            mem_id = mems[0]["id"]
        else:
            print(f"[FAIL] Memory retrieval failed: {mems}")
            sys.exit(1)
            
        # 5. Test DELETE /memories/<id>
        print(f"Testing DELETE /memories/{mem_id}...")
        delete_res = request("DELETE", f"/memories/{mem_id}")
        if delete_res["success"]:
            print("[OK] Memory deleted via API.")
        else:
            print("[FAIL] Deletion failed.")
            sys.exit(1)
            
        print("\n=== Chat API Self-Test PASSED ===")
        
    except Exception as e:
        print(f"[ERROR] API Test failed: {e}")
        sys.exit(1)
    finally:
        server_proc.terminate()
        server_proc.wait()
        if os.path.exists("temp_test_server.py"):
            os.remove("temp_test_server.py")

if __name__ == "__main__":
    run_api_test()
