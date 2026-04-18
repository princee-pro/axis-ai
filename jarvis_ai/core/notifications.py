"""
Notifications Module.
Handles desktop notifications with queue management and deduplication.
"""

import threading
import time
from datetime import datetime, timedelta
from collections import deque

class NotificationManager:
    """
    Manages desktop notifications with queue and deduplication.
    """
    def __init__(self, logger=None):
        self.logger = logger
        self.notification_queue = deque()
        self.recent_notifications = {}  # {goal_id: {event: timestamp}}
        self.dedup_window = 5  # seconds
        self.queue_thread = None
        self.running = False
        self.plyer_available = False
        
        # Try to import plyer
        try:
            from plyer import notification as plyer_notif
            self.plyer_notif = plyer_notif
            self.plyer_available = True
            self._log("Desktop notifications enabled (plyer available)")
        except ImportError:
            self._log("Desktop notifications disabled (plyer not installed)", "WARNING")
    
    def _log(self, message, level="INFO"):
        """Log message if logger available."""
        if self.logger:
            self.logger.log(message, level)
        else:
            print(f"[NOTIFICATIONS] {message}")
    
    def start(self):
        """Start the notification queue processor."""
        if not self.running:
            self.running = True
            self.queue_thread = threading.Thread(target=self._process_queue, daemon=True)
            self.queue_thread.start()
            self._log("Notification queue processor started")
    
    def stop(self):
        """Stop the notification queue processor."""
        self.running = False
        if self.queue_thread:
            self.queue_thread.join(timeout=2)
        self._log("Notification queue processor stopped")
    
    def notify(self, goal_id, title, message, urgency="normal"):
        """
        Queue a notification.
        
        Args:
            goal_id (int): Goal ID
            title (str): Notification title
            message (str): Notification message
            urgency (str): normal, low, critical
        """
        # Check deduplication
        if not self._should_notify(goal_id, title):
            self._log(f"Skipping duplicate notification for goal {goal_id}: {title}", "DEBUG")
            return
        
        notification = {
            "goal_id": goal_id,
            "title": title,
            "message": message,
            "urgency": urgency,
            "timestamp": datetime.now()
        }
        
        self.notification_queue.append(notification)
        self._update_recent(goal_id, title)
        self._log(f"Notification queued: {title} (Goal {goal_id})")
    
    def _should_notify(self, goal_id, event):
        """Check if notification should be sent (deduplication)."""
        if goal_id not in self.recent_notifications:
            return True
        
        if event not in self.recent_notifications[goal_id]:
            return True
        
        last_time = self.recent_notifications[goal_id][event]
        elapsed = (datetime.now() - last_time).total_seconds()
        
        return elapsed > self.dedup_window
    
    def _update_recent(self, goal_id, event):
        """Update recent notifications cache."""
        if goal_id not in self.recent_notifications:
            self.recent_notifications[goal_id] = {}
        
        self.recent_notifications[goal_id][event] = datetime.now()
        
        # Cleanup old entries
        cutoff = datetime.now() - timedelta(seconds=self.dedup_window * 2)
        for gid in list(self.recent_notifications.keys()):
            for evt in list(self.recent_notifications[gid].keys()):
                if self.recent_notifications[gid][evt] < cutoff:
                    del self.recent_notifications[gid][evt]
            if not self.recent_notifications[gid]:
                del self.recent_notifications[gid]
    
    def _process_queue(self):
        """Background thread to process notification queue."""
        while self.running:
            if self.notification_queue:
                notif = self.notification_queue.popleft()
                self._send_desktop(notif)
            time.sleep(0.5)  # Check queue every 500ms
    
    def _send_desktop(self, notif):
        """Send desktop notification."""
        if not self.plyer_available:
            # Fallback: print to console
            self._log(f"[NOTIFICATION] {notif['title']}: {notif['message']}")
            return
        
        try:
            # Map urgency to timeout
            timeout_map = {"low": 5, "normal": 10, "critical": 15}
            timeout = timeout_map.get(notif['urgency'], 10)
            
            self.plyer_notif.notify(
                title=notif['title'],
                message=notif['message'],
                app_name="Jarvis AI",
                timeout=timeout
            )
            
            self._log(f"Desktop notification sent: {notif['title']}")
            
        except Exception as e:
            self._log(f"Failed to send desktop notification: {e}", "ERROR")
