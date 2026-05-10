"""Mock notification system integration."""

import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class NotificationClient:
    """Mock client for notification system (email, SMS, etc.)."""

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.mock-notifications.com"):
        self.api_key = api_key or "mock-notification-key"
        self.base_url = base_url
        self.timeout = 5.0  # seconds
        self.max_retries = 3

    def send_email(self, to_email: str, subject: str, body: str, priority: str = "normal") -> Dict[str, Any]:
        """Send email notification."""
        logger.info(f"Mock: Sending email to {to_email} with subject: {subject}")

        # Simulate API call delay
        time.sleep(0.1)

        response = {
            "success": True,
            "message_id": f"MSG-{int(time.time())}",
            "recipient": to_email,
            "subject": subject,
            "priority": priority,
            "sent_at": datetime.now().isoformat(),
            "status": "sent"
        }

        logger.info(f"Mock: Email sent successfully to {to_email}")
        return response

    def send_support_notification(self, support_email: str, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send notification to human support team."""
        subject = f"Escalated Support Ticket: {ticket_data.get('reference_id', 'Unknown')}"
        body = f"""
        A support ticket has been escalated and requires human review.

        Reference ID: {ticket_data.get('reference_id', 'Unknown')}
        Category: {ticket_data.get('category', 'Unknown')}
        Urgency: {ticket_data.get('urgency', 'Unknown')}
        Escalation Reason: {ticket_data.get('escalation_reason', 'Unknown')}

        Customer Inquiry: {ticket_data.get('inquiry', '')[:200]}...

        Please review and respond within 24 hours.
        """

        return self.send_email(support_email, subject, body, "high")

    def send_customer_notification(self, customer_email: str, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send notification to customer about ticket status."""
        subject = f"Support Ticket Update: {ticket_data.get('reference_id', 'Unknown')}"
        body = f"""
        Your support inquiry has been received and is being processed.

        Reference ID: {ticket_data.get('reference_id', 'Unknown')}
        Status: {ticket_data.get('status', 'Processing')}

        We will respond within 24 hours. If this is urgent, please call our support line.

        Original Inquiry: {ticket_data.get('inquiry', '')[:200]}...
        """

        return self.send_email(customer_email, subject, body, "normal")

    def send_sms(self, phone_number: str, message: str) -> Dict[str, Any]:
        """Send SMS notification (mock)."""
        logger.info(f"Mock: Sending SMS to {phone_number}")

        # Simulate API call delay
        time.sleep(0.05)

        response = {
            "success": True,
            "message_id": f"SMS-{int(time.time())}",
            "recipient": phone_number,
            "message_length": len(message),
            "sent_at": datetime.now().isoformat(),
            "status": "delivered"
        }

        logger.info(f"Mock: SMS sent successfully to {phone_number}")
        return response

    def get_delivery_status(self, message_id: str) -> Dict[str, Any]:
        """Get delivery status of a notification."""
        logger.info(f"Mock: Checking delivery status for message {message_id}")

        # Simulate API call delay
        time.sleep(0.02)

        response = {
            "success": True,
            "message_id": message_id,
            "status": "delivered",
            "delivered_at": datetime.now().isoformat()
        }

        return response