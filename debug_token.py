import os
from dotenv import load_dotenv

load_dotenv()
token = os.environ.get('JARVIS_SECRET_TOKEN')
print(f"Token: '{token}'")
print(f"Length: {len(token)}")
print(f"Hex: {token.encode().hex()}")
