"""Generic GraphQL API Tool for external integrations."""

import time
import logging
from typing import Dict, Any, Optional
from . import BaseSupportTool
from pydantic import BaseModel, Field

from src.aamad.config import (
    EXTERNAL_API_KEY, INTEGRATION_CONFIG,
    ENABLE_EXTERNAL_APIS, ENABLE_MOCK_INTEGRATIONS
)

logger = logging.getLogger(__name__)


class GraphQLRequest(BaseModel):
    """Request model for GraphQL API calls."""
    query: str = Field(..., description="GraphQL query string")
    variables: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Query variables")
    url: str = Field(..., description="GraphQL endpoint URL")
    headers: Optional[Dict[str, str]] = Field(default_factory=dict, description="HTTP headers")
    operation_name: Optional[str] = Field(default=None, description="Operation name for the query")


class GraphQLApiTool(BaseSupportTool):
    """Generic GraphQL API tool for external integrations."""

    name: str = "GraphQL API Tool"
    description: str = "Generic tool for making GraphQL API calls to external services"

    def __init__(self, api_name: str = "graphql_api"):
        super().__init__()
        self.api_name = api_name
        self.retry_count = INTEGRATION_CONFIG["retry_count"]
        self.timeout_seconds = INTEGRATION_CONFIG["timeout_seconds"]
        self.rate_limit_per_minute = INTEGRATION_CONFIG["rate_limit_per_minute"]

    def _run(self, request: GraphQLRequest) -> Dict[str, Any]:
        """Execute GraphQL API call (mock implementation)."""
        start_time = time.time()

        try:
            # Log integration attempt
            logger.info(f"Integration attempt: {self.api_name}, mode=mock, operation={request.operation_name or 'query'}, url={request.url}")

            if not ENABLE_MOCK_INTEGRATIONS:
                return {
                    "success": False,
                    "error": "Mock integrations disabled",
                    "latency": time.time() - start_time,
                    "status": "disabled"
                }

            # Simulate GraphQL call with mock response
            time.sleep(0.15)  # Simulate network latency

            # Mock GraphQL response based on query content
            if "user" in request.query.lower():
                mock_data = {
                    "user": {
                        "id": "user_123",
                        "name": "John Doe",
                        "email": "john@example.com"
                    }
                }
            elif "repository" in request.query.lower() or "repo" in request.query.lower():
                mock_data = {
                    "repository": {
                        "name": "example-repo",
                        "owner": "example-org",
                        "stars": 42,
                        "forks": 10
                    }
                }
            elif "weather" in request.query.lower():
                mock_data = {
                    "weather": {
                        "temperature": 22,
                        "condition": "sunny",
                        "location": "New York"
                    }
                }
            else:
                mock_data = {
                    "genericResponse": {
                        "message": f"Mock GraphQL response from {self.api_name}",
                        "timestamp": "2024-01-01T00:00:00Z"
                    }
                }

            latency = time.time() - start_time

            # Log successful integration
            logger.info(f"Integration success: {self.api_name}, mode=mock, latency={latency:.2f}s, status=200")

            return {
                "success": True,
                "data": mock_data,
                "latency": latency,
                "cached": False,
                "retries": 0,
                "extensions": {
                    "mock": True,
                    "api_name": self.api_name
                }
            }

        except Exception as e:
            latency = time.time() - start_time
            logger.error(f"Integration error: {self.api_name}, mode=mock, latency={latency:.2f}s, error={str(e)}")

            return {
                "success": False,
                "errors": [{"message": str(e)}],
                "latency": latency,
                "status": "error"
            }

    async def _arun(self, request: GraphQLRequest) -> Dict[str, Any]:
        """Async version of GraphQL API call."""
        import asyncio
        # Simulate async operation
        await asyncio.sleep(0.08)
        return self._run(request)