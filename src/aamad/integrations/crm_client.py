"""Mock CRM system integration."""

import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CRMClient:
    """Mock client for Customer Relationship Management system."""

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.mock-crm.com"):
        self.api_key = api_key or "mock-crm-key"
        self.base_url = base_url
        self.timeout = 5.0  # seconds
        self.max_retries = 3

    def get_customer_profile(self, identifier: str) -> Dict[str, Any]:
        """Get customer profile by email or order ID."""
        logger.info(f"Mock: Fetching customer profile for identifier: {identifier}")

        # Simulate API call delay
        time.sleep(0.1)

        # Mock customer data based on identifier
        if "@" in identifier:  # Email
            customer_data = {
                "customer_id": f"CUST-{hash(identifier) % 10000}",
                "email": identifier,
                "name": "John Doe",
                "account_status": "active",
                "loyalty_tier": "gold",
                "total_orders": 15,
                "last_order_date": "2024-01-15",
                "support_tickets_count": 2,
                "preferred_contact_method": "email"
            }
        else:  # Order ID
            customer_data = {
                "customer_id": f"CUST-{hash(identifier) % 10000}",
                "order_id": identifier,
                "email": "customer@example.com",
                "name": "Jane Smith",
                "account_status": "active",
                "order_status": "shipped",
                "order_date": "2024-01-10",
                "support_tickets_count": 1
            }

        response = {
            "success": True,
            "customer": customer_data,
            "last_updated": datetime.now().isoformat()
        }

        logger.info(f"Mock: Retrieved profile for customer {customer_data.get('customer_id')}")
        return response

    def update_customer_notes(self, customer_id: str, notes: str) -> Dict[str, Any]:
        """Update customer notes in CRM."""
        logger.info(f"Mock: Updating notes for customer {customer_id}")

        # Simulate API call delay
        time.sleep(0.05)

        response = {
            "success": True,
            "customer_id": customer_id,
            "notes_updated": True,
            "updated_at": datetime.now().isoformat()
        }

        logger.info(f"Mock: Notes updated for customer {customer_id}")
        return response

    def log_interaction(self, customer_id: str, interaction_type: str, details: Dict[str, Any]) -> Dict[str, Any]:
        """Log customer interaction in CRM."""
        logger.info(f"Mock: Logging {interaction_type} interaction for customer {customer_id}")

        # Simulate API call delay
        time.sleep(0.05)

        response = {
            "success": True,
            "customer_id": customer_id,
            "interaction_id": f"INT-{int(time.time())}",
            "interaction_type": interaction_type,
            "logged_at": datetime.now().isoformat()
        }

        logger.info(f"Mock: Interaction logged for customer {customer_id}")
        return response