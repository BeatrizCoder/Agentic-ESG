"""GitHub API Tool for repository and user data integration."""

import time
import logging
import random
from typing import Dict, Any, Optional
from . import BaseSupportTool
from pydantic import BaseModel, Field

from src.aamad.config import (
    INTEGRATION_CONFIG,
    ENABLE_MOCK_INTEGRATIONS
)

logger = logging.getLogger(__name__)


class GitHubRequest(BaseModel):
    """Request model for GitHub API calls."""
    action: str = Field(..., description="Action to perform (get_repo, get_user, search_repos, get_issues)")
    owner: Optional[str] = Field(default=None, description="Repository owner/organization")
    repo: Optional[str] = Field(default=None, description="Repository name")
    username: Optional[str] = Field(default=None, description="GitHub username")
    query: Optional[str] = Field(default=None, description="Search query for repositories")
    limit: int = Field(default=10, description="Maximum number of results")


class GitHubTool(BaseSupportTool):
    """GitHub API tool for retrieving repository and user data."""

    name: str = "GitHub Tool"
    description: str = "Tool for retrieving GitHub repository, user, and issue data"

    def __init__(self):
        super().__init__()
        self.api_name = "github_api"
        self.retry_count = INTEGRATION_CONFIG["retry_count"]
        self.timeout_seconds = INTEGRATION_CONFIG["timeout_seconds"]
        self.rate_limit_per_minute = INTEGRATION_CONFIG["rate_limit_per_minute"]

    def _run(self, request: GitHubRequest) -> Dict[str, Any]:
        """Execute GitHub API call (mock implementation)."""
        start_time = time.time()

        try:
            # Log integration attempt
            logger.info(f"Integration attempt: {self.api_name}, mode=mock, action={request.action}")

            if not ENABLE_MOCK_INTEGRATIONS:
                return {
                    "success": False,
                    "error": "Mock integrations disabled",
                    "latency": time.time() - start_time,
                    "status": "disabled"
                }

            # Simulate GitHub API call
            time.sleep(0.25)  # Simulate network latency

            response_data = {}

            if request.action == "get_repo" and request.owner and request.repo:
                response_data = {
                    "name": request.repo,
                    "full_name": f"{request.owner}/{request.repo}",
                    "owner": {
                        "login": request.owner,
                        "type": "Organization" if random.choice([True, False]) else "User"
                    },
                    "description": f"Mock repository: {request.repo}",
                    "language": random.choice(["Python", "JavaScript", "TypeScript", "Java", "Go"]),
                    "stars": random.randint(10, 1000),
                    "forks": random.randint(5, 200),
                    "open_issues": random.randint(0, 50),
                    "created_at": "2023-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z"
                }

            elif request.action == "get_user" and request.username:
                response_data = {
                    "login": request.username,
                    "name": f"Mock User {request.username}",
                    "company": random.choice(["Tech Corp", "Dev Inc", "Code LLC", None]),
                    "location": random.choice(["San Francisco", "New York", "London", "Berlin", None]),
                    "email": f"{request.username}@example.com",
                    "public_repos": random.randint(5, 100),
                    "followers": random.randint(10, 1000),
                    "following": random.randint(5, 500),
                    "created_at": "2020-01-01T00:00:00Z"
                }

            elif request.action == "search_repos" and request.query:
                repos = []
                for i in range(min(request.limit, 5)):
                    repos.append({
                        "name": f"mock-repo-{i+1}",
                        "full_name": f"mock-org/mock-repo-{i+1}",
                        "description": f"Mock repository {i+1} for query: {request.query}",
                        "language": random.choice(["Python", "JavaScript", "TypeScript"]),
                        "stars": random.randint(1, 500),
                        "forks": random.randint(0, 100)
                    })
                response_data = {
                    "total_count": len(repos),
                    "items": repos
                }

            elif request.action == "get_issues" and request.owner and request.repo:
                issues = []
                for i in range(min(request.limit, 3)):
                    issues.append({
                        "number": i + 1,
                        "title": f"Mock Issue #{i+1}",
                        "state": random.choice(["open", "closed"]),
                        "body": f"This is a mock issue description for {request.owner}/{request.repo}",
                        "created_at": "2024-01-01T00:00:00Z",
                        "updated_at": "2024-01-01T12:00:00Z"
                    })
                response_data = issues

            else:
                response_data = {"error": "Invalid action or missing required parameters"}

            latency = time.time() - start_time

            # Log successful integration
            logger.info(f"Integration success: {self.api_name}, mode=mock, latency={latency:.2f}s, status=200")

            return {
                "success": True,
                "data": response_data,
                "latency": latency,
                "cached": False,
                "retries": 0,
                "api_used": "mock_github_api"
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

    async def _arun(self, request: GitHubRequest) -> Dict[str, Any]:
        """Async version of GitHub API call."""
        import asyncio
        # Simulate async operation
        await asyncio.sleep(0.12)
        return self._run(request)