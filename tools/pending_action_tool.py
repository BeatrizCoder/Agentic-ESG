"""Pending-action lookup tool — detects order numbers and returns awaiting context."""

import re
import logging
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_ORDER_PATTERN = re.compile(r"\b(PA\d{3}|\d{5})\b")


class PendingActionInput(BaseModel):
    inquiry: str = Field(
        description="Full customer inquiry text. The tool will extract any order "
                    "number present and look up whether there is a pending action "
                    "awaiting the customer for that order."
    )


class PendingActionTool(BaseTool):
    name: str = "Pending Action Tool"
    description: str = (
        "Looks up whether a customer order has a pending action awaiting the "
        "customer's response (e.g. photos of damaged product, return label "
        "confirmation, billing dispute evidence). "
        "Input: customer inquiry text. "
        "Output: pending action details or not-found result."
    )
    args_schema: type[BaseModel] = PendingActionInput

    def _run(self, inquiry: str) -> dict:
        match = _ORDER_PATTERN.search(inquiry)
        if not match:
            return {"found": False, "reason": "no_order_number"}

        order_number = match.group(1)
        logger.info("PendingActionTool: looking up order %s", order_number)

        try:
            from aamad.data_store import data_store
            result = data_store.get_pending_action(order_number)
        except Exception as e:
            logger.error("PendingActionTool: DB lookup failed: %s", e)
            return {"found": False, "order_number": order_number, "reason": "db_error", "error": str(e)}

        if result:
            logger.info(
                "PendingActionTool: found pending action type=%s for order %s",
                result.get("action_type"), order_number,
            )
            return result

        return {"found": False, "order_number": order_number, "reason": "no_pending_action"}


pending_action_tool = PendingActionTool()
