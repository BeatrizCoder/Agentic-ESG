"""Pending-action lookup tool — detects order numbers and returns awaiting context."""

import re
import time
import logging

logger = logging.getLogger(__name__)

_ORDER_PATTERNS = [
    r'pedido\s*[:#]?\s*(\d{4,8})',
    r'order\s*[:#]?\s*(\d{4,8})',
    r'n[uú]mero\s+(?:do\s+)?pedido\s*[:#]?\s*(\d{4,8})',
    r'#(\d{4,8})',
    r'\border\s+#?(\d{4,8})\b',
]


class PendingActionTool:
    """
    Looks up pending actions for order numbers.
    Detects if a customer's order has an open case requiring their action.
    """

    name = "Pending Action Tool"

    def _extract_order_number(self, text: str) -> str | None:
        clean = re.sub(
            r'\nPhone:.*|\nEmail:.*|\nName:.*|\n---.*$',
            '', text, flags=re.IGNORECASE | re.DOTALL
        )
        for pattern in _ORDER_PATTERNS:
            match = re.search(pattern, clean, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def run(self, inquiry: str) -> dict:
        start_time = time.time()
        order_number = self._extract_order_number(inquiry)

        if not order_number:
            return {"found": False, "reason": "no_order_number", "latency_ms": 0}

        logger.info("PendingActionTool: checking order %s", order_number)

        try:
            from aamad.data_store import data_store
            result = data_store.get_pending_action(order_number)
        except Exception as e:
            logger.error("PendingActionTool: DB lookup failed: %s", e)
            latency_ms = round((time.time() - start_time) * 1000, 2)
            return {"found": False, "order_number": order_number, "reason": "db_error", "latency_ms": latency_ms}

        latency_ms = round((time.time() - start_time) * 1000, 2)

        if not result:
            logger.info("PendingActionTool: no pending action for %s", order_number)
            return {"found": False, "order_number": order_number, "latency_ms": latency_ms}

        logger.info(
            "PendingActionTool: found %s → %s",
            order_number, result.get("status"),
        )
        result["latency_ms"] = latency_ms
        return result


pending_action_tool = PendingActionTool()
