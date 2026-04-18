import os
import datetime

class Logger:
    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        self.log_file = os.path.join(log_dir, "brain.log")
        self.recent_logs = []
        self.max_recent = 100  # Increased for better tracking

    def log(self, message, level="INFO", goal_id=None):
        """
        Log a message with optional goal_id for filtering.
        
        Args:
            message (str): Log message
            level (str): Log level (INFO, WARNING, ERROR)
            goal_id (int): Optional goal ID for filtering
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create structured log entry
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message,
            "goal_id": goal_id
        }
        
        # Format for file and console
        goal_tag = f" [Goal:{goal_id}]" if goal_id else ""
        formatted_message = f"[{timestamp}] [{level}]{goal_tag} {message}"
        
        # Print to console
        print(formatted_message)
        
        # Save to file
        with open(self.log_file, "a") as f:
            f.write(formatted_message + "\n")
            
        # Keep in memory as structured data
        self.recent_logs.append(log_entry)
        if len(self.recent_logs) > self.max_recent:
            self.recent_logs.pop(0)

    def get_recent(self, limit=50):
        """Get recent log messages (formatted strings)."""
        logs = self.recent_logs[-limit:]
        return [self._format_log(log) for log in logs]
    
    def get_logs_by_goal(self, goal_id, limit=50):
        """Get logs filtered by goal ID."""
        filtered = [log for log in self.recent_logs if log["goal_id"] == goal_id]
        return [self._format_log(log) for log in filtered[-limit:]]
    
    def get_logs_by_level(self, level, limit=50):
        """Get logs filtered by level."""
        filtered = [log for log in self.recent_logs if log["level"] == level]
        return [self._format_log(log) for log in filtered[-limit:]]
    
    def _format_log(self, log_entry):
        """Format a structured log entry as a string."""
        goal_tag = f" [Goal:{log_entry['goal_id']}]" if log_entry['goal_id'] else ""
        return f"[{log_entry['timestamp']}] [{log_entry['level']}]{goal_tag} {log_entry['message']}"
