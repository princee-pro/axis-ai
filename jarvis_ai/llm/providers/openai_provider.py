import os
import http.client
import json
from jarvis_ai.llm.providers.base import LLMProviderBase

class OpenAIProvider(LLMProviderBase):
    def __init__(self, api_key, model="gpt-4-turbo", timeout=30):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate(self, prompt, system_prompt=None, temperature=0.7, max_tokens=500):
        if not self.api_key:
            raise ValueError("OpenAI API Key is missing.")

        conn = http.client.HTTPSConnection("api.openai.com", timeout=self.timeout)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            conn.request("POST", "/v1/chat/completions", json.dumps(body), headers)
            response = conn.getresponse()
            data = json.loads(response.read().decode())
            
            if response.status != 200:
                raise Exception(f"OpenAI API Error: {data.get('error', {}).get('message', 'Unknown Error')}")
                
            return data['choices'][0]['message']['content']
        finally:
            conn.close()
