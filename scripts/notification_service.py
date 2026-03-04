#!/usr/bin/env python3
"""
Multi-Channel Notification Service
Sends notifications via macOS, Pushover, Telegram, ntfy.sh, and Email
"""

import os
import json
import subprocess
from typing import Optional, List
from enum import Enum
from datetime import datetime
import requests


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationService:
    """
    Multi-channel notification service.
    
    Supports:
    - macOS native notifications (osascript)
    - Pushover (iOS/Android push)
    - Telegram (via bot)
    - ntfy.sh (free push service)
    - Email (SMTP)
    """
    
    def __init__(self):
        """Initialize notification service from environment variables."""
        
        # macOS (always enabled)
        self.macos_enabled = True
        
        # Pushover (https://pushover.net) - $5 one-time purchase
        self.pushover_enabled = bool(os.getenv('PUSHOVER_TOKEN'))
        self.pushover_token = os.getenv('PUSHOVER_TOKEN')
        self.pushover_user = os.getenv('PUSHOVER_USER')
        
        # Telegram (free, create bot via @BotFather)
        self.telegram_enabled = bool(os.getenv('TELEGRAM_BOT_TOKEN'))
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        # ntfy.sh (free, no signup required)
        self.ntfy_enabled = bool(os.getenv('NTFY_TOPIC'))
        self.ntfy_topic = os.getenv('NTFY_TOPIC')
        self.ntfy_server = os.getenv('NTFY_SERVER', 'https://ntfy.sh')
        
        # Email (SMTP)
        self.email_enabled = bool(os.getenv('SMTP_HOST'))
        self.smtp_host = os.getenv('SMTP_HOST')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.email_to = os.getenv('EMAIL_TO')
        
        # Log configuration
        enabled_services = []
        if self.macos_enabled:
            enabled_services.append("macOS")
        if self.pushover_enabled:
            enabled_services.append("Pushover")
        if self.telegram_enabled:
            enabled_services.append("Telegram")
        if self.ntfy_enabled:
            enabled_services.append("ntfy.sh")
        if self.email_enabled:
            enabled_services.append("Email")
        
        self.enabled_services = enabled_services
    
    def send(self, title: str, message: str, 
             priority: NotificationPriority = NotificationPriority.NORMAL,
             url: Optional[str] = None,
             sound: Optional[str] = None) -> dict:
        """
        Send notification via all enabled channels.
        
        Args:
            title: Notification title
            message: Notification body
            priority: Priority level
            url: Optional URL to open when clicked
            sound: Optional sound name
            
        Returns:
            dict with status per channel
        """
        
        results = {}
        
        # macOS native notification
        if self.macos_enabled:
            results['macos'] = self._send_macos(title, message, sound)
        
        # Pushover
        if self.pushover_enabled:
            results['pushover'] = self._send_pushover(title, message, priority, url, sound)
        
        # Telegram
        if self.telegram_enabled:
            results['telegram'] = self._send_telegram(title, message)
        
        # ntfy.sh
        if self.ntfy_enabled:
            results['ntfy'] = self._send_ntfy(title, message, priority, url)
        
        # Email (only for HIGH/URGENT)
        if self.email_enabled and priority in [NotificationPriority.HIGH, NotificationPriority.URGENT]:
            results['email'] = self._send_email(title, message)
        
        return results
    
    def _send_macos(self, title: str, message: str, sound: Optional[str] = None) -> bool:
        """Send macOS notification via osascript."""
        try:
            sound_part = f'sound name "{sound}"' if sound else ''
            script = f'display notification "{message}" with title "{title}" {sound_part}'
            subprocess.run(['osascript', '-e', script], check=True, capture_output=True)
            return True
        except Exception as e:
            print(f"macOS notification failed: {e}")
            return False
    
    def _send_pushover(self, title: str, message: str, 
                       priority: NotificationPriority,
                       url: Optional[str] = None,
                       sound: Optional[str] = None) -> bool:
        """Send Pushover notification."""
        try:
            # Map priority to Pushover levels (-2 to 2)
            priority_map = {
                NotificationPriority.LOW: -1,
                NotificationPriority.NORMAL: 0,
                NotificationPriority.HIGH: 1,
                NotificationPriority.URGENT: 2
            }
            
            data = {
                'token': self.pushover_token,
                'user': self.pushover_user,
                'title': title,
                'message': message,
                'priority': priority_map[priority]
            }
            
            if url:
                data['url'] = url
                data['url_title'] = "Open"
            
            if sound:
                data['sound'] = sound
            
            response = requests.post('https://api.pushover.net/1/messages.json', 
                                    data=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Pushover notification failed: {e}")
            return False
    
    def _send_telegram(self, title: str, message: str) -> bool:
        """Send Telegram notification."""
        try:
            text = f"*{title}*\n\n{message}"
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            data = {
                'chat_id': self.telegram_chat_id,
                'text': text,
                'parse_mode': 'Markdown'
            }
            response = requests.post(url, data=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Telegram notification failed: {e}")
            return False
    
    def _send_ntfy(self, title: str, message: str,
                   priority: NotificationPriority,
                   url: Optional[str] = None) -> bool:
        """Send ntfy.sh notification."""
        try:
            # Map priority to ntfy levels (1-5)
            priority_map = {
                NotificationPriority.LOW: 2,
                NotificationPriority.NORMAL: 3,
                NotificationPriority.HIGH: 4,
                NotificationPriority.URGENT: 5
            }
            
            headers = {
                'Title': title,
                'Priority': str(priority_map[priority])
            }
            
            if url:
                headers['Click'] = url
            
            response = requests.post(
                f"{self.ntfy_server}/{self.ntfy_topic}",
                data=message.encode('utf-8'),
                headers=headers,
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"ntfy.sh notification failed: {e}")
            return False
    
    def _send_email(self, title: str, message: str) -> bool:
        """Send email notification via SMTP."""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            msg = MIMEMultipart()
            msg['From'] = self.smtp_user
            msg['To'] = self.email_to
            msg['Subject'] = f"[Document System] {title}"
            
            body = f"{message}\n\n---\nSent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            return True
        except Exception as e:
            print(f"Email notification failed: {e}")
            return False
    
    def get_status(self) -> dict:
        """Get notification service status."""
        return {
            'enabled_services': self.enabled_services,
            'macos': self.macos_enabled,
            'pushover': self.pushover_enabled,
            'telegram': self.telegram_enabled,
            'ntfy': self.ntfy_enabled,
            'email': self.email_enabled
        }


# Convenience functions for common notification types

def notify_new_files(count: int, location: str = "inbox"):
    """Notify about new files."""
    notifier = NotificationService()
    title = f"📥 {count} New PDF{'s' if count > 1 else ''}"
    message = f"Found {count} new PDF file{'s' if count > 1 else ''} in {location}"
    return notifier.send(title, message, NotificationPriority.NORMAL, sound="Ping")


def notify_processing_complete(count: int, staged: bool = True):
    """Notify about processing completion."""
    notifier = NotificationService()
    location = "staging area" if staged else "permanent locations"
    title = f"✅ Processing Complete"
    message = f"Successfully processed {count} file{'s' if count > 1 else ''} → {location}"
    return notifier.send(title, message, NotificationPriority.LOW, sound="Glass")


def notify_processing_error(filename: str, error: str):
    """Notify about processing error."""
    notifier = NotificationService()
    title = f"⚠️ Processing Error"
    message = f"Failed to process: {filename}\nError: {error}"
    return notifier.send(title, message, NotificationPriority.HIGH, sound="Basso")


def notify_staged_files_ready(count: int):
    """Notify about staged files ready for finalization."""
    notifier = NotificationService()
    title = f"📦 {count} File{'s' if count > 1 else ''} Staged"
    message = f"{count} processed file{'s' if count > 1 else ''} in staging, ready to finalize"
    return notifier.send(title, message, NotificationPriority.NORMAL, sound="Pop")


def notify_finalization_complete(count: int):
    """Notify about finalization completion."""
    notifier = NotificationService()
    title = f"✨ Finalization Complete"
    message = f"Moved {count} file{'s' if count > 1 else ''} to permanent locations"
    return notifier.send(title, message, NotificationPriority.LOW, sound="Hero")


def notify_duplicate_detected(filename: str, action: str = "skipped"):
    """Notify about duplicate file."""
    notifier = NotificationService()
    title = f"🔄 Duplicate Detected"
    message = f"File: {filename}\nAction: {action}"
    return notifier.send(title, message, NotificationPriority.NORMAL, sound="Tink")


def notify_system_status(message: str, is_error: bool = False):
    """Notify about system status."""
    notifier = NotificationService()
    title = f"{'⚠️ System Alert' if is_error else 'ℹ️ System Status'}"
    priority = NotificationPriority.HIGH if is_error else NotificationPriority.NORMAL
    sound = "Basso" if is_error else "Pop"
    return notifier.send(title, message, priority, sound=sound)


# CLI for testing notifications
def main():
    """Test notification service."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test notification service')
    parser.add_argument('--status', action='store_true', help='Show enabled services')
    parser.add_argument('--test', action='store_true', help='Send test notification')
    parser.add_argument('--title', type=str, default='Test Notification',
                       help='Notification title')
    parser.add_argument('--message', type=str, default='This is a test message',
                       help='Notification message')
    parser.add_argument('--priority', type=str, default='normal',
                       choices=['low', 'normal', 'high', 'urgent'],
                       help='Notification priority')
    
    args = parser.parse_args()
    
    notifier = NotificationService()
    
    if args.status:
        print("\n🔔 Notification Service Status\n")
        status = notifier.get_status()
        print(f"Enabled services: {', '.join(status['enabled_services'])}\n")
        print("Channel Status:")
        print(f"  macOS:    {'✅ Enabled' if status['macos'] else '❌ Disabled'}")
        print(f"  Pushover: {'✅ Enabled' if status['pushover'] else '❌ Disabled (set PUSHOVER_TOKEN, PUSHOVER_USER)'}")
        print(f"  Telegram: {'✅ Enabled' if status['telegram'] else '❌ Disabled (set TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)'}")
        print(f"  ntfy.sh:  {'✅ Enabled' if status['ntfy'] else '❌ Disabled (set NTFY_TOPIC)'}")
        print(f"  Email:    {'✅ Enabled' if status['email'] else '❌ Disabled (set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, EMAIL_TO)'}")
        print()
    
    if args.test:
        priority_map = {
            'low': NotificationPriority.LOW,
            'normal': NotificationPriority.NORMAL,
            'high': NotificationPriority.HIGH,
            'urgent': NotificationPriority.URGENT
        }
        
        print(f"\n📤 Sending test notification...\n")
        results = notifier.send(
            args.title,
            args.message,
            priority_map[args.priority]
        )
        
        print("Results:")
        for channel, success in results.items():
            status = "✅ Sent" if success else "❌ Failed"
            print(f"  {channel}: {status}")
        print()


if __name__ == "__main__":
    main()
