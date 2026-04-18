"""
Email Integration Module.
Handles SMTP email sending with mock mode.
"""

import smtplib
from email.message import EmailMessage
from datetime import datetime

class EmailIntegration:
    """
    Manages email sending via SMTP with mock mode.
    """
    def __init__(self, logger=None, mock_mode=True):
        self.logger = logger
        self.mock_mode = mock_mode
        self.smtp_config = {
            'host': 'smtp.gmail.com',
            'port': 587,
            'username': None,
            'password': None
        }
        self._log(f"Email integration initialized (mock_mode={mock_mode})")
    
    def _log(self, message, level="INFO", goal_id=None):
        """Log message if logger available."""
        if self.logger:
            self.logger.log(message, level, goal_id)
        else:
            print(f"[EMAIL] {message}")
    
    def configure(self, host, port, username, password):
        """Configure SMTP settings."""
        self.smtp_config = {
            'host': host,
            'port': port,
            'username': username,
            'password': password
        }
        self._log("Email configuration updated")
    
    def send(self, to, subject, body, goal_id=None):
        """
        Send an email.
        
        Args:
            to (str): Recipient email
            subject (str): Email subject
            body (str): Email body
            goal_id (int): Associated goal ID
        
        Returns:
            bool: Success status
        """
        if self.mock_mode:
            self._log(f"[MOCK EMAIL] To: {to}", goal_id=goal_id)
            self._log(f"[MOCK EMAIL] Subject: {subject}", goal_id=goal_id)
            self._log(f"[MOCK EMAIL] Body: {body[:100]}...", goal_id=goal_id)
            return True
        
        try:
            msg = EmailMessage()
            msg['From'] = self.smtp_config['username']
            msg['To'] = to
            msg['Subject'] = subject
            msg.set_content(body)
            
            with smtplib.SMTP(self.smtp_config['host'], self.smtp_config['port']) as server:
                server.starttls()
                server.login(self.smtp_config['username'], self.smtp_config['password'])
                server.send_message(msg)
            
            self._log(f"Email sent to {to}: {subject}", goal_id=goal_id)
            return True
            
        except Exception as e:
            self._log(f"Failed to send email: {e}", "ERROR", goal_id=goal_id)
            return False
    
    def send_goal_report(self, goals, recipient):
        """
        Send a goal status report.
        
        Args:
            goals (list): List of goal dicts
            recipient (str): Email recipient
        
        Returns:
            bool: Success status
        """
        subject = f"Jarvis Goal Report - {datetime.now().strftime('%Y-%m-%d')}"
        
        body = "=== Jarvis AI Goal Report ===\n\n"
        body += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        completed = [g for g in goals if g.get('status') == 'completed']
        pending = [g for g in goals if g.get('status') == 'pending']
        
        body += f"Summary:\n"
        body += f"  Total Goals: {len(goals)}\n"
        body += f"  Completed: {len(completed)}\n"
        body += f"  Pending: {len(pending)}\n\n"
        
        if completed:
            body += "Completed Goals:\n"
            for goal in completed:
                body += f"  - {goal.get('description', 'N/A')} (ID: {goal['id']}, Progress: {goal.get('progress', 0)}%)\n"
            body += "\n"
        
        if pending:
            body += "Pending Goals:\n"
            for goal in pending:
                priority = {1: 'Normal', 2: 'High', 3: 'Critical'}.get(goal.get('priority', 1), 'Normal')
                body += f"  - {goal.get('description', 'N/A')} (ID: {goal['id']}, Priority: {priority})\n"
        
        body += "\n---\nSent by Jarvis AI"
        
        return self.send(recipient, subject, body)
