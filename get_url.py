import os
import sys
import json
from google_auth_oauthlib.flow import InstalledAppFlow

def main():
    client_secrets = 'credentials.json'
    scopes = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.compose',
        'https://www.googleapis.com/auth/calendar.events'
    ]
    
    flow = InstalledAppFlow.from_client_secrets_file(client_secrets, scopes)
    flow.redirect_uri = 'http://localhost:60010/'
    auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
    
    with open('final_url.txt', 'w') as f:
        f.write(auth_url)
    
    print(f"URL saved to final_url.txt")

if __name__ == "__main__":
    main()
