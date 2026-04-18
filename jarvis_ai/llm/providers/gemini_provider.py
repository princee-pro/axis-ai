import http.client
import json
from jarvis_ai.llm.providers.base import LLMProviderBase

class GeminiProvider(LLMProviderBase):
    def __init__(self, api_key, model="gemini-pro", timeout=30):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate(self, prompt, system_prompt=None, temperature=0.7, max_tokens=500):
        if not self.api_key:
            raise ValueError("Gemini API Key is missing.")

        url = f"/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        conn = http.client.HTTPSConnection("generativelanguage.googleapis.com", timeout=self.timeout)
        headers = {"Content-Type": "application/json"}
        
        contents = []
        if system_prompt:
            # Note: Gemini handle system instructions via specific fields in some versions, 
            # here we prepend for simplicity in a basic generateContent call.
            prompt = f"{system_prompt}\n\nUser: {prompt}"
            
        contents.append({"parts": [{"text": prompt}]})

        body = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }

        try:
            conn.request("POST", url, json.dumps(body), headers)
            response = conn.getresponse()
            data = json.loads(response.read().decode())
            
            if response.status != 200:
                raise Exception(f"Gemini API Error: {data.get('error', {}).get('message', 'Unknown Error')}")
                
            return data['candidates'][0]['content']['parts'][0]['text']
        finally:
            conn.close()
