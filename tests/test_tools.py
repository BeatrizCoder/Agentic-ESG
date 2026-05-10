"""Tests for external API integration tools."""

import pytest
from tools.rest_api_tool import RESTApiTool, RESTApiRequest
from tools.graphql_api_tool import GraphQLApiTool, GraphQLRequest
from tools.weather_tool import WeatherTool, WeatherRequest
from tools.github_tool import GitHubTool, GitHubRequest


class TestRESTApiTool:
    """Test REST API tool functionality."""

    def test_mock_get_request(self):
        """Test mock GET request."""
        tool = RESTApiTool("test_api")
        request = RESTApiRequest(method="GET", url="https://api.example.com/test")

        result = tool._run(request)

        assert result["success"] is True
        assert "response" in result
        assert result["status_code"] == 200
        assert result["latency"] > 0
        assert result["cached"] is False
        assert result["retries"] == 0

    def test_mock_post_request(self):
        """Test mock POST request."""
        tool = RESTApiTool("test_api")
        request = RESTApiRequest(method="POST", url="https://api.example.com/test", data={"key": "value"})

        result = tool._run(request)

        assert result["success"] is True
        assert result["status_code"] == 201
        assert "id" in result["response"]
        assert result["response"]["created"] is True

    async def test_async_request(self):
        """Test async request execution."""
        tool = RESTApiTool("test_api")
        request = RESTApiRequest(method="GET", url="https://api.example.com/test")

        result = await tool._arun(request)

        assert result["success"] is True
        assert result["status_code"] == 200


class TestGraphQLApiTool:
    """Test GraphQL API tool functionality."""

    def test_mock_user_query(self):
        """Test mock GraphQL user query."""
        tool = GraphQLApiTool("test_graphql")
        request = GraphQLRequest(
            query="query { user { id name email } }",
            url="https://api.example.com/graphql"
        )

        result = tool._run(request)

        assert result["success"] is True
        assert "data" in result
        assert "user" in result["data"]
        assert result["data"]["user"]["id"] == "user_123"
        assert result["latency"] > 0

    def test_mock_repository_query(self):
        """Test mock GraphQL repository query."""
        tool = GraphQLApiTool("test_graphql")
        request = GraphQLRequest(
            query="query { repository { name owner stars } }",
            url="https://api.example.com/graphql"
        )

        result = tool._run(request)

        assert result["success"] is True
        assert "repository" in result["data"]
        assert "stars" in result["data"]["repository"]

    async def test_async_graphql_request(self):
        """Test async GraphQL request execution."""
        tool = GraphQLApiTool("test_graphql")
        request = GraphQLRequest(
            query="query { user { id } }",
            url="https://api.example.com/graphql"
        )

        result = await tool._arun(request)

        assert result["success"] is True


class TestWeatherTool:
    """Test weather API tool functionality."""

    def test_mock_weather_request(self):
        """Test mock weather data retrieval."""
        tool = WeatherTool()
        request = WeatherRequest(location="New York", units="metric")

        result = tool._run(request)

        assert result["success"] is True
        assert "data" in result
        assert "current" in result["data"]
        assert result["data"]["current"]["location"] == "New York"
        assert result["data"]["current"]["units"] == "metric"
        assert isinstance(result["data"]["current"]["temperature"], (int, float))

    def test_mock_weather_with_forecast(self):
        """Test mock weather with forecast."""
        tool = WeatherTool()
        request = WeatherRequest(location="London", units="imperial", include_forecast=True)

        result = tool._run(request)

        assert result["success"] is True
        assert "forecast" in result["data"]
        assert len(result["data"]["forecast"]) == 5
        assert "temperature_max" in result["data"]["forecast"][0]

    async def test_async_weather_request(self):
        """Test async weather request execution."""
        tool = WeatherTool()
        request = WeatherRequest(location="Tokyo")

        result = await tool._arun(request)

        assert result["success"] is True


class TestGitHubTool:
    """Test GitHub API tool functionality."""

    def test_mock_get_repo(self):
        """Test mock repository data retrieval."""
        tool = GitHubTool()
        request = GitHubRequest(action="get_repo", owner="octocat", repo="Hello-World")

        result = tool._run(request)

        assert result["success"] is True
        assert "data" in result
        assert result["data"]["name"] == "Hello-World"
        assert result["data"]["full_name"] == "octocat/Hello-World"
        assert "stars" in result["data"]

    def test_mock_get_user(self):
        """Test mock user data retrieval."""
        tool = GitHubTool()
        request = GitHubRequest(action="get_user", username="octocat")

        result = tool._run(request)

        assert result["success"] is True
        assert result["data"]["login"] == "octocat"
        assert "public_repos" in result["data"]

    def test_mock_search_repos(self):
        """Test mock repository search."""
        tool = GitHubTool()
        request = GitHubRequest(action="search_repos", query="python", limit=3)

        result = tool._run(request)

        assert result["success"] is True
        assert "items" in result["data"]
        assert len(result["data"]["items"]) <= 3

    def test_mock_get_issues(self):
        """Test mock issues retrieval."""
        tool = GitHubTool()
        request = GitHubRequest(action="get_issues", owner="octocat", repo="Hello-World", limit=2)

        result = tool._run(request)

        assert result["success"] is True
        assert isinstance(result["data"], list)
        assert len(result["data"]) <= 2
        if result["data"]:
            assert "number" in result["data"][0]

    async def test_async_github_request(self):
        """Test async GitHub request execution."""
        tool = GitHubTool()
        request = GitHubRequest(action="get_user", username="testuser")

        result = await tool._arun(request)

        assert result["success"] is True


class TestIntegrationConfiguration:
    """Test integration configuration and logging."""

    def test_tool_configuration(self):
        """Test that tools are properly configured."""
        from src.aamad.config import INTEGRATION_CONFIG

        tool = RESTApiTool("test")

        assert tool.retry_count == INTEGRATION_CONFIG["retry_count"]
        assert tool.timeout_seconds == INTEGRATION_CONFIG["timeout_seconds"]
        assert tool.rate_limit_per_minute == INTEGRATION_CONFIG["rate_limit_per_minute"]

    def test_logging_structure(self):
        """Test that logging includes required fields."""
        import logging
        from unittest.mock import patch

        tool = RESTApiTool("test_api")
        request = RESTApiRequest(method="GET", url="https://api.example.com/test")

        with patch('tools.rest_api_tool.logger') as mock_logger:
            result = tool._run(request)

            # Check that info log was called with expected structure
            mock_logger.info.assert_called()
            log_call = mock_logger.info.call_args[0][0]
            assert "Integration attempt:" in log_call
            assert "test_api" in log_call
            assert "mode=mock" in log_call</content>
<parameter name="filePath">/home/beatriz/AAMAD/tests/test_tools.py