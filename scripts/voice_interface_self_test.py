import requests
import json
import os
import secrets
import base64
import time

# Configuration for test
BASE_URL = "http://127.0.0.1:8000"
# In a real test, we'd need an admin token. 
# For this self-test, we assume the server is running locally with a known token or we mock the request.
# If we want to run this against a LIVE server, we need the token from settings.yaml.
TOKEN = os.environ.get("JARVIS_TOKEN", "default_secret_if_any") 

def log(msg):
    print(f"[TEST] {msg}")

def test_capabilities():
    log("Testing GET /voice/capabilities...")
    headers = {"Authorization": f"Bearer {TOKEN}"}
    r = requests.get(f"{BASE_URL}/voice/capabilities", headers=headers)
    if r.status_code == 200:
        log("SUCCESS: Capabilities retrieved")
        print(json.dumps(r.json(), indent=2))
    else:
        log(f"FAILED: {r.status_code} - {r.text}")

def test_transcribe():
    log("Testing POST /voice/transcribe with mock audio...")
    # Create a tiny dummy wav file (just a header basically)
    wav_path = "test_audio.wav"
    with open(wav_path, "wb") as f:
        # RIFF header for a tiny silent wav
        f.write(b'RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00')
    
    headers = {"Authorization": f"Bearer {TOKEN}"}
    files = {'audio': ('test_audio.wav', open(wav_path, 'rb'), 'audio/wav')}
    
    r = requests.post(f"{BASE_URL}/voice/transcribe", headers=headers, files=files)
    if r.status_code == 200:
        log("SUCCESS: Audio transcribed")
        print(json.dumps(r.json(), indent=2))
    else:
        log(f"FAILED: {r.status_code} - {r.text}")
    
    os.remove(wav_path)

def test_voice_chat():
    log("Testing POST /voice/chat (text-based)...")
    headers = {"Authorization": f"Bearer {TOKEN}"}
    payload = {
        "transcript": "Hello Jarvis, this is a test.",
        "tts_reply": True
    }
    r = requests.post(f"{BASE_URL}/voice/chat", headers=headers, json=payload)
    if r.status_code == 200:
        log("SUCCESS: Voice chat (text) completed")
        res = r.json()
        print(json.dumps(res, indent=2))
        if "audio_reply" in res:
            log(f"TTS Reply generated: {res['audio_reply']['path']}")
    else:
        log(f"FAILED: {r.status_code} - {r.text}")

def test_voice_chat_audio():
    log("Testing POST /voice/chat (audio-upload)...")
    wav_path = "test_chat.wav"
    with open(wav_path, "wb") as f:
        f.write(b'RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00')
        
    headers = {"Authorization": f"Bearer {TOKEN}"}
    files = {
        'audio': ('test_chat.wav', open(wav_path, 'rb'), 'audio/wav'),
        'tts_reply': (None, 'true')
    }
    
    r = requests.post(f"{BASE_URL}/voice/chat", headers=headers, files=files)
    if r.status_code == 200:
        log("SUCCESS: Voice chat (audio) completed")
        print(json.dumps(r.json(), indent=2))
    else:
        log(f"FAILED: {r.status_code} - {r.text}")
    
    os.remove(wav_path)

def test_speak():
    log("Testing POST /voice/speak...")
    headers = {"Authorization": f"Bearer {TOKEN}"}
    payload = {
        "text": "The voice interface is now operational."
    }
    r = requests.post(f"{BASE_URL}/voice/speak", headers=headers, json=payload)
    if r.status_code == 200:
        log("SUCCESS: Speak completed")
        print(json.dumps(r.json(), indent=2))
    else:
        log(f"FAILED: {r.status_code} - {r.text}")

if __name__ == "__main__":
    log("Starting Voice Interface Self-Test...")
    log("Note: Ensure the Jarvis server is running on localhost:8000")
    try:
        test_capabilities()
        test_transcribe()
        test_voice_chat()
        test_voice_chat_audio()
        test_speak()
        log("All tests completed.")
    except Exception as e:
        log(f"Test suite error: {e}")
