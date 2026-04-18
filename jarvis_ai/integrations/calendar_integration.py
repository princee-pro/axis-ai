"""
Calendar Integration Module.
Manages calendar events with local JSON storage.
"""

import json
import os
from datetime import datetime, timedelta

class CalendarIntegration:
    """
    Manages calendar events with local storage.
    """
    def __init__(self, logger=None, data_dir="data"):
        self.logger = logger
        self.data_dir = data_dir
        self.calendar_file = os.path.join(data_dir, "calendar.json")
        self.events = {}
        self.next_id = 1
        
        # Create data directory if needed
        os.makedirs(data_dir, exist_ok=True)
        
        # Load existing events
        self._load_events()
        self._log("Calendar integration initialized")
    
    def _log(self, message, level="INFO", goal_id=None):
        """Log message if logger available."""
        if self.logger:
            self.logger.log(message, level, goal_id)
        else:
            print(f"[CALENDAR] {message}")
    
    def _load_events(self):
        """Load events from JSON file."""
        if os.path.exists(self.calendar_file):
            try:
                with open(self.calendar_file, 'r') as f:
                    data = json.load(f)
                    self.events = {int(k): v for k, v in data.get('events', {}).items()}
                    self.next_id = data.get('next_id', 1)
                self._log(f"Loaded {len(self.events)} calendar events")
            except Exception as e:
                self._log(f"Failed to load calendar: {e}", "ERROR")
    
    def _save_events(self):
        """Save events to JSON file."""
        try:
            with open(self.calendar_file, 'w') as f:
                json.dump({
                    'events': self.events,
                    'next_id': self.next_id
                }, f, indent=2, default=str)
        except Exception as e:
            self._log(f"Failed to save calendar: {e}", "ERROR")
    
    def create_event(self, title, start, end=None, description="", goal_id=None):
        """
        Create a calendar event.
        
        Args:
            title (str): Event title
            start (datetime or str): Start time
            end (datetime or str): End time (optional)
            description (str): Event description
            goal_id (int): Linked goal ID
        
        Returns:
            dict: Created event
        """
        # Parse datetime strings
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if end and isinstance(end, str):
            end = datetime.fromisoformat(end)
        
        # Default end time: 1 hour after start
        if not end:
            end = start + timedelta(hours=1)
        
        event = {
            'id': self.next_id,
            'title': title,
            'start': start.isoformat(),
            'end': end.isoformat(),
            'description': description,
            'goal_id': goal_id,
            'created_at': datetime.now().isoformat()
        }
        
        self.events[self.next_id] = event
        self.next_id += 1
        self._save_events()
        
        self._log(f"Created calendar event: {title} (ID: {event['id']})", goal_id=goal_id)
        return event
    
    def get_events(self, start_date=None, end_date=None):
        """
        Get events within date range.
        
        Args:
            start_date (datetime): Start of range
            end_date (datetime): End of range
        
        Returns:
            list: Events in range
        """
        if not start_date:
            start_date = datetime.now()
        if not end_date:
            end_date = start_date + timedelta(days=7)
        
        results = []
        for event in self.events.values():
            event_start = datetime.fromisoformat(event['start'])
            if start_date <= event_start <= end_date:
                results.append(event)
        
        return sorted(results, key=lambda e: e['start'])
    
    def get_upcoming(self, days=7):
        """Get upcoming events for next N days."""
        start = datetime.now()
        end = start + timedelta(days=days)
        return self.get_events(start, end)
    
    def link_to_goal(self, event_id, goal_id):
        """Link event to a goal."""
        if event_id in self.events:
            self.events[event_id]['goal_id'] = goal_id
            self._save_events()
            self._log(f"Linked event {event_id} to goal {goal_id}")
            return True
        return False
    
    def delete_event(self, event_id):
        """Delete an event."""
        if event_id in self.events:
            title = self.events[event_id]['title']
            del self.events[event_id]
            self._save_events()
            self._log(f"Deleted calendar event: {title} (ID: {event_id})")
            return True
        return False
