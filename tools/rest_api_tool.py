"""Generic REST API Tool for external integrations."""

import time
import logging
from typing import Dict, Any, Optional
from . import BaseSupportTool
from pydantic import BaseModel, Field

from src.aamad.config import (
    INTEGRATION_CONFIG,
    ENABLE_MOCK_INTEGRATIONS
)

logger = logging.getLogger(__name__)


class RESTApiRequest(BaseModel):
    """Request model for REST API calls."""
    method: str = Field(..., description="HTTP method (GET, POST, PUT, DELETE)")
    url: str = Field(..., description="API endpoint URL")
    headers: Optional[Dict[str, str]] = Field(default_factory=dict, description="HTTP headers")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Query parameters")
    data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Request body data")
    timeout: Optional[int] = Field(default=None, description="Request timeout in seconds")


class RESTApiTool(BaseSupportTool):
    """Generic REST API tool for external integrations."""

    name: str = "REST API Tool"
    description: str = "Generic tool for making REST API calls to external services"

    def __init__(self, api_name: str = "generic_api"):
        super().__init__()
        self.api_name = api_name
        self.retry_count = INTEGRATION_CONFIG["retry_count"]
        self.timeout_seconds = INTEGRATION_CONFIG["timeout_seconds"]
        self.rate_limit_per_minute = INTEGRATION_CONFIG["rate_limit_per_minute"]

    def _run(self, request: RESTApiRequest) -> Dict[str, Any]:
        """Execute REST API call (mock implementation)."""
        start_time = time.time()

        try:
            # Log integration attempt
            logger.info(f"Integration attempt: {self.api_name}, mode=mock, method={request.method}, url={request.url}")

            if not ENABLE_MOCK_INTEGRATIONS:
                return {
                    "success": False,
                    "error": "Mock integrations disabled",
                    "latency": time.time() - start_time,
                    "status": "disabled"
                }

            # Simulate API call with mock response
            time.sleep(0.1)  # Simulate network latency

            # Mock responses based on method
            if request.method.upper() == "GET":
                mock_response = {
                    "data": {"message": f"Mock GET response from {self.api_name}"},
                    "status_code": 200
                }
            elif request.method.upper() == "POST":
                mock_response = {
                    "data": {"id": "mock_123", "created": True, "message": f"Mock POST response from {self.api_name}"},
                    "status_code": 201
                }
            elif request.method.upper() == "PUT":
                mock_response = {
                    "data": {"updated": True, "message": f"Mock PUT response from {self.api_name}"},
                    "status_code": 200
                }
            elif request.method.upper() == "DELETE":
                mock_response = {
                    "data": {"deleted": True, "message": f"Mock DELETE response from {self.api_name}"},
                    "status_code": 204
                }
            else:
                mock_response = {
                    "data": {"error": "Method not supported"},
                    "status_code": 405
                }

            latency = time.time() - start_time

            # Log successful integration
            logger.info(f"Integration success: {self.api_name}, mode=mock, latency={latency:.2f}s, status={mock_response['status_code']}")

            return {
                "success": True,
                "response": mock_response["data"],
                "status_code": mock_response["status_code"],
                "latency": latency,
                "cached": False,
                "retries": 0
            }

        except Exception as e:
            latency = time.time() - start_time
            logger.error(f"Integration error: {self.api_name}, mode=mock, latency={latency:.2f}s, error={str(e)}")

            return {
                "success": False,
                "error": str(e),
                "latency": latency,
                "status": "error"
            }

    async def _arun(self, request: RESTApiRequest) -> Dict[str, Any]:
        """Async version of REST API call."""
        import asyncio
        # Simulate async operation
        await asyncio.sleep(0.05)
        return self._run(request)