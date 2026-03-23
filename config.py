"""Configuration module for loading environment variables and constants."""
import os
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Centralized configuration management."""

    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_USERNAME: str = os.getenv("GITHUB_USERNAME", "")
    COMMIT_AUTHOR_NAME: str = os.getenv("COMMIT_AUTHOR_NAME", "")
    COMMIT_AUTHOR_EMAIL: str = os.getenv("COMMIT_AUTHOR_EMAIL", "")
    LOCAL_REPOS_BASE_DIR: str = os.getenv("LOCAL_REPOS_BASE_DIR", "./repos")

    MIN_COMMITS_PER_DAY: int = int(os.getenv("MIN_COMMITS_PER_DAY", "3"))
    MAX_COMMITS_PER_DAY: int = int(os.getenv("MAX_COMMITS_PER_DAY", "6"))

    MIN_ACTIVITIES_PER_DAY: int = 3
    MAX_ACTIVITIES_PER_DAY: int = 7

    INCLUDE_FORKS: bool = os.getenv("INCLUDE_FORKS", "false").lower() == "true"
    REPO_CACHE_TTL_HOURS: int = 6

    ACTIVITY_WEIGHTS: Dict[str, int] = {
        "commits": 50,
        "issues": 20,
        "pull_requests": 20,
        "reviews": 10,
    }

    @classmethod
    def load_activity_weights(cls) -> Dict[str, int]:
        """Load and parse activity weights from environment variable."""
        weights_str = os.getenv("ACTIVITY_WEIGHTS", "commits:50,issues:20,pull_requests:20,reviews:10")
        weights = {}
        for item in weights_str.split(","):
            if ":" in item:
                key, value = item.split(":", 1)
                weights[key.strip()] = int(value.strip())
        return weights if weights else cls.ACTIVITY_WEIGHTS

    @classmethod
    def validate(cls) -> List[str]:
        """Validate required configuration and return list of missing fields."""
        missing = []
        required = [
            ("GITHUB_TOKEN", cls.GITHUB_TOKEN),
            ("GITHUB_USERNAME", cls.GITHUB_USERNAME),
            ("COMMIT_AUTHOR_NAME", cls.COMMIT_AUTHOR_NAME),
            ("COMMIT_AUTHOR_EMAIL", cls.COMMIT_AUTHOR_EMAIL),
        ]
        for name, value in required:
            if not value:
                missing.append(name)
        return missing

    @classmethod
    def get_github_api_headers(cls) -> Dict[str, str]:
        """Get standard headers for GitHub API requests."""
        return {
            "Authorization": f"Bearer {cls.GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    @classmethod
    def get_graphql_headers(cls) -> Dict[str, str]:
        """Get headers for GraphQL API requests."""
        return {
            "Authorization": f"Bearer {cls.GITHUB_TOKEN}",
            "Content-Type": "application/json",
        }
