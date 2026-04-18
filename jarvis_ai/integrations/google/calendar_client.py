"""
Google Calendar API Client.
Handles listing events and creating new ones.
"""
from datetime import datetime, timedelta
from jarvis_ai.integrations.google.auth import GoogleAuth

class CalendarClient:
    def __init__(self, auth_helper: GoogleAuth):
        self.auth = auth_helper
        self.service = self.auth.build_service('calendar', 'v3')

    def list_events(self, limit=10, time_min=None):
        """List upcoming events."""
        if not time_min:
            time_min = datetime.utcnow().isoformat() + 'Z'
            
        events_result = self.service.events().list(
            calendarId='primary', timeMin=time_min,
            maxResults=limit, singleEvents=True,
            orderBy='startTime'
        ).execute()
        return events_result.get('items', [])

    def create_event(self, title, start_time, end_time=None, description="", attendees=None, location=None):
        """Create a calendar event."""
        if not end_time:
            # Default 1 hour
            st = datetime.fromisoformat(start_time.replace('Z', ''))
            end_time = (st + timedelta(hours=1)).isoformat() + 'Z'

        event = {
            'summary': title,
            'location': location,
            'description': description,
            'start': {
                'dateTime': start_time,
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time,
                'timeZone': 'UTC',
            },
        }
        if attendees:
            event['attendees'] = [{'email': a} for a in attendees]

        event = self.service.events().insert(calendarId='primary', body=event).execute()
        return event
