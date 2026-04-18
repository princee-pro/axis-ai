"""
Gmail API Client.
Handles reading messages and creating drafts.
"""
import base64
from email.message import EmailMessage
from jarvis_ai.integrations.google.auth import GoogleAuth

class GmailClient:
    def __init__(self, auth_helper: GoogleAuth):
        self.auth = auth_helper
        self.service = self.auth.build_service('gmail', 'v1')

    def list_messages(self, limit=10, query=None):
        """List recent messages."""
        results = self.service.users().messages().list(userId='me', maxResults=limit, q=query).execute()
        messages = results.get('messages', [])
        
        output = []
        for msg in messages:
            detail = self.service.users().messages().get(userId='me', id=msg['id'], format='metadata', 
                                                       metadataHeaders=['Subject', 'From', 'Date']).execute()
            headers = detail.get('payload', {}).get('headers', [])
            meta = {'id': msg['id'], 'snippet': detail.get('snippet')}
            for h in headers:
                meta[h['name'].lower()] = h['value']
            output.append(meta)
        return output

    def get_message(self, message_id, body_limit=2000):
        """Fetch message details with bounded body."""
        msg = self.service.users().messages().get(userId='me', id=message_id, format='full').execute()
        
        # Extract body text from parts
        body = ""
        payload = msg.get('payload', {})
        parts = payload.get('parts', [])
        
        def find_body(parts_list):
            for part in parts_list:
                if part.get('mimeType') == 'text/plain':
                    data = part.get('body', {}).get('data', '')
                    return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                if 'parts' in part:
                    res = find_body(part['parts'])
                    if res: return res
            return ""

        body = find_body(parts) if parts else ""
        if not body and payload.get('mimeType') == 'text/plain':
            data = payload.get('body', {}).get('data', '')
            body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            
        return {
            'id': message_id,
            'snippet': msg.get('snippet'),
            'body': body[:body_limit],
            'subject': next((h['value'] for h in msg['payload']['headers'] if h['name'].lower() == 'subject'), 'No Subject'),
            'from': next((h['value'] for h in msg['payload']['headers'] if h['name'].lower() == 'from'), 'Unknown'),
            'date': next((h['value'] for h in msg['payload']['headers'] if h['name'].lower() == 'date'), 'Unknown')
        }

    def create_draft(self, to, subject, body, thread_id=None):
        """Create an email draft."""
        message = EmailMessage()
        message.set_content(body)
        message['To'] = to
        message['From'] = 'me'
        message['Subject'] = subject

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        create_message = {
            'message': {
                'raw': encoded_message
            }
        }
        if thread_id:
            create_message['message']['threadId'] = thread_id

        draft = self.service.users().drafts().create(userId='me', body=create_message).execute()
        return draft

    def send_draft(self, draft_id):
        """Send a previously created draft."""
        sent = self.service.users().drafts().send(userId='me', body={'id': draft_id}).execute()
        return sent
