import json
import os
import subprocess
import sys
import time
import unittest
import urllib.request


class TestMobileServerStandalone(unittest.TestCase):
    def setUp(self):
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.port = 8000
        self.url = f"http://127.0.0.1:{self.port}"
        self.secret = 'standalone-test-secret'
        self.process = None

    def tearDown(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
            for stream_name in ('stdout', 'stderr', 'stdin'):
                stream = getattr(self.process, stream_name, None)
                if stream:
                    stream.close()
            self.process = None

    def test_server_startup_and_response(self):
        env = os.environ.copy()
        env['JARVIS_SECRET_TOKEN'] = self.secret
        env['PYTHONUNBUFFERED'] = '1'
        self.process = subprocess.Popen(
            [sys.executable, '-m', 'jarvis_ai.mobile.server'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=self.project_root,
        )

        start_time = time.time()
        connected = False
        while time.time() - start_time < 15:
            try:
                with urllib.request.urlopen(f"{self.url}/health", timeout=1) as response:
                    if response.status == 200:
                        connected = True
                        break
            except Exception:
                time.sleep(0.25)

        if not connected:
            try:
                stdout, stderr = self.process.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()
                stdout, stderr = self.process.communicate(timeout=1)
            self.fail(f"Server failed to start.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}")

        request = urllib.request.Request(
            f"{self.url}/chat",
            data=json.dumps({'message': 'hello'}).encode('utf-8'),
            method='POST',
            headers={
                'Content-Type': 'application/json',
                'X-Jarvis-Token': self.secret,
            },
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode('utf-8'))

        self.assertEqual(response.status, 200)
        self.assertIn('response', payload)
        self.assertIn('could not confidently route', payload['response'])


if __name__ == '__main__':
    unittest.main()
