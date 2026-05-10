"""Mock ticketing system integration."""

import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TicketingClient:
    """Mock client for external ticketing system."""

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.mock-ticketing.com"):
        self.api_key = api_key or "mock-api-key"
        self.base_url = base_url
        self.timeout = 5.0  # seconds
        self.max_retries = 3

    def create_ticket(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a support ticket in external system."""
        logger.info(f"Mock: Creating ticket for inquiry: {ticket_data.get('inquiry', '')[:50]}...")

        # Simulate API call delay
        time.sleep(0.1)

        # Mock successful response
        external_ticket_id = f"EXT-{int(time.time())}"
        response = {
            "success": True,
            "external_ticket_id": external_ticket_id,
            "status": "open",
            "created_at": datetime.now().isoformat(),
            "priority": "normal",
            "assigned_to": "support_team",
            "estimated_response_time": "24 hours"
        }

        logger.info(f"Mock: Ticket created with ID: {external_ticket_id}")
        return response

    def update_ticket_status(self, external_ticket_id: str, status: str) -> Dict[str, Any]:
        """Update ticket status in external system."""
        logger.info(f"Mock: Updating ticket {external_ticket_id} to status: {status}")

        # Simulate API call delay
        time.sleep(0.05)

        response = {
            "success": True,
            "external_ticket_id": external_ticket_id,
            "status": status,
            "updated_at": datetime.now().isoformat()
        }

        logger.info(f"Mock: Ticket {external_ticket_id} status updated to {status}")
        return response

    def get_ticket_status(self, external_ticket_id: str) -> Dict[str, Any]:
        """Get ticket status from external system."""
        logger.info(f"Mock: Fetching status for ticket {external_ticket_id}")

        # Simulate API call delay
        time.sleep(0.05)

        response = {
            "success": True,
            "external_ticket_id": external_ticket_id,
            "status": "open",  # Mock status
            "last_updated": datetime.now().isoformat(),
            "comments": []
        }

        return response