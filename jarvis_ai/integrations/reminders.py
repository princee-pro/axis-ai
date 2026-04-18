"""
Reminders Module.
Manages scheduled reminders with Supabase storage.
"""

import threading
import time
from datetime import datetime, timedelta
import os
from jarvis_ai.db.supabase_client import get_supabase

class RemindersManager:
    """
    Manages reminders with Supabase storage and scheduled notifications.
    """
    def __init__(self, logger=None, notification_manager=None, data_dir="data"):
        self.logger = logger
        self.notifications = notification_manager
        self.data_dir = data_dir
        self.check_thread = None
        self.running = False
        
        # Create data directory
        os.makedirs(data_dir, exist_ok=True)
        
        # Initialize database (schema managed in Supabase)
        self._init_db()
        self._log("Reminders manager initialized")
    
    def _log(self, message, level="INFO", goal_id=None):
        """Log message if logger available."""
        if self.logger:
            self.logger.log(message, level, goal_id)
        else:
            print(f"[REMINDERS] {message}")
    
    def _init_db(self):
        """Initialize database connections (Supabase)."""
        pass
    
    def create(self, title, reminder_datetime, goal_id=None, recurring=False, interval_days=0):
        if isinstance(reminder_datetime, str):
            reminder_datetime = datetime.fromisoformat(reminder_datetime)
            
        try:
            res = get_supabase().table("reminders").insert({
                "title": title, "datetime": reminder_datetime.isoformat(), "goal_id": goal_id,
                "recurring": recurring, "interval_days": interval_days, "created_at": datetime.now().isoformat()
            }).execute()
            reminder_id = res.data[0]['id'] if res.data else None
            self._log(f"Created reminder: {title} (ID: {reminder_id}) for {reminder_datetime}", goal_id=goal_id)
            return reminder_id
        except Exception as e:
            self._log(f"DB Error create reminder: {e}", "ERROR")
            return None
    
    def get_due(self):
        """Get reminders that are due now."""
        now = datetime.now().isoformat()
        try:
            res = get_supabase().table("reminders").select("*").lte("datetime", now).eq("triggered", False).execute()
            reminders = []
            for row in res.data:
                reminders.append({
                    'id': row['id'],
                    'title': row['title'],
                    'datetime': row['datetime'],
                    'goal_id': row.get('goal_id'),
                    'recurring': bool(row.get('recurring')),
                    'interval_days': row.get('interval_days') or 0
                })
            return reminders
        except Exception as e:
            self._log(f"DB Error get_due: {e}", "ERROR")
            return []
    
    def mark_triggered(self, reminder_id, reschedule=False, interval_days=0):
        """Mark reminder as triggered, optionally reschedule."""
        try:
            if reschedule and interval_days > 0:
                res = get_supabase().table("reminders").select("datetime").eq("id", reminder_id).execute()
                if res.data:
                    current_dt = datetime.fromisoformat(res.data[0]['datetime'])
                    next_dt = current_dt + timedelta(days=interval_days)
                    get_supabase().table("reminders").update({
                        "datetime": next_dt.isoformat(), "triggered": False
                    }).eq("id", reminder_id).execute()
                    self._log(f"Rescheduled reminder {reminder_id} for {next_dt}")
            else:
                get_supabase().table("reminders").update({"triggered": True}).eq("id", reminder_id).execute()
        except Exception as e:
            self._log(f"DB Error mark_triggered: {e}", "ERROR")
    
    def start_checking(self, interval_seconds=60):
        """Start background thread to check for due reminders."""
        if not self.running:
            self.running = True
            self.check_thread = threading.Thread(
                target=self._check_loop,
                args=(interval_seconds,),
                daemon=True
            )
            self.check_thread.start()
            self._log(f"Started reminder checking (every {interval_seconds}s)")
    
    def stop_checking(self):
        """Stop background checking."""
        self.running = False
        if self.check_thread:
            self.check_thread.join(timeout=2)
        self._log("Stopped reminder checking")
    
    def _check_loop(self, interval):
        """Background loop to check and trigger reminders."""
        while self.running:
            self._check_and_notify()
            time.sleep(interval)
    
    def _check_and_notify(self):
        """Check for due reminders and send notifications."""
        due_reminders = self.get_due()
        
        for reminder in due_reminders:
            # Send notification
            if self.notifications:
                self.notifications.notify(
                    goal_id=reminder['goal_id'] or 0,
                    title=f"Reminder: {reminder['title']}",
                    message=f"Scheduled for {reminder['datetime']}",
                    urgency="normal"
                )
            else:
                self._log(f"REMINDER: {reminder['title']}", goal_id=reminder['goal_id'])
            
            # Mark as triggered or reschedule
            self.mark_triggered(
                reminder['id'],
                reschedule=reminder['recurring'],
                interval_days=reminder['interval_days']
            )
