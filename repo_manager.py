"""Repository manager - auto-discover and clone user repositories."""
import json
import os
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import requests

from config import Config
from utils.git_utils import ensure_repo_cloned


REPO_CACHE_FILE = "repos_cache.json"
GITHUB_API_BASE = "https://api.github.com"


class RepoManager:
    """Manages fetching, caching, and cloning of user repositories."""

    def __init__(self, base_dir: str = None, cache_ttl_hours: int = None):
        self.base_dir = base_dir or Config.LOCAL_REPOS_BASE_DIR
        self.cache_ttl = timedelta(hours=cache_ttl_hours or Config.REPO_CACHE_TTL_HOURS)
        self.repos: List[dict] = []
        self.cache_path = os.path.join(self.base_dir, REPO_CACHE_FILE)

    def fetch_all_repos(self, include_forks: bool = None) -> List[dict]:
        """Fetch all user repositories via paginated REST API.

        Args:
            include_forks: Whether to include forked repos (default from config)

        Returns:
            List of repository dictionaries.
        """
        if include_forks is None:
            include_forks = Config.INCLUDE_FORKS

        if not Config.GITHUB_TOKEN:
            raise ValueError("GitHub token not configured")

        cached = self._load_cache()
        if cached:
            print(f"Using cached repo list ({len(cached)} repos)")
            self.repos = cached
            return self.repos

        print("Fetching repositories from GitHub API...")
        repos = []
        page = 1
        per_page = 100

        headers = Config.get_github_api_headers()

        while True:
            url = f"{GITHUB_API_BASE}/user/repos"
            params = {
                "type": "owner",
                "per_page": per_page,
                "page": page,
                "sort": "updated",
                "direction": "desc",
            }

            try:
                response = requests.get(url, headers=headers, params=params, timeout=30)
                response.raise_for_status()
                batch = response.json()

                if not batch:
                    break

                for repo in batch:
                    if not include_forks and repo.get("fork"):
                        continue

                    repo_info = {
                        "name": repo["name"],
                        "full_name": repo["full_name"],
                        "clone_url": repo["clone_url"],
                        "ssh_url": repo.get("ssh_url", ""),
                        "default_branch": repo.get("default_branch", "main"),
                        "is_private": repo.get("private", False),
                        "has_issues": repo.get("has_issues", True),
                        "html_url": repo["html_url"],
                        "fork": repo.get("fork", False),
                    }
                    repos.append(repo_info)

                print(f"  Fetched page {page}: {len(batch)} repos")

                if len(batch) < per_page:
                    break

                page += 1
                time.sleep(0.5)

            except requests.exceptions.RequestException as e:
                print(f"Failed to fetch repos page {page}: {e}")
                break

        self.repos = repos
        self._save_cache(repos)
        print(f"Total repos fetched: {len(repos)}")
        return repos

    def _load_cache(self) -> Optional[List[dict]]:
        """Load cached repo list if still valid."""
        try:
            if not os.path.exists(self.cache_path):
                return None

            with open(self.cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)

            cached_time = datetime.fromisoformat(cache.get("timestamp", "2000-01-01"))
            if datetime.now() - cached_time > self.cache_ttl:
                return None

            return cache.get("repos", [])
        except Exception:
            return None

    def _save_cache(self, repos: List[dict]):
        """Save repo list to cache file."""
        try:
            os.makedirs(os.path.dirname(self.cache_path) or self.base_dir, exist_ok=True)
            cache = {
                "timestamp": datetime.now().isoformat(),
                "repos": repos,
            }
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2)
        except Exception as e:
            print(f"Failed to save cache: {e}")

    def get_repos(self, n: int = None, shuffle: bool = True) -> List[dict]:
        """Get repositories, optionally shuffled or sampled.

        Args:
            n: Number of repos to return (None = all)
            shuffle: Whether to shuffle the list

        Returns:
            List of repository dictionaries.
        """
        if not self.repos:
            self.fetch_all_repos()

        result = self.repos.copy()

        if shuffle:
            random.shuffle(result)

        if n is not None and n < len(result):
            result = result[:n]

        return result

    def get_random_repo(self, require_issues: bool = False) -> Optional[dict]:
        """Get a single random repository.

        Args:
            require_issues: Whether repo must have issues enabled

        Returns:
            A single repo dict or None.
        """
        repos = self.get_repos()

        if require_issues:
            repos = [r for r in repos if r.get("has_issues", True)]

        return random.choice(repos) if repos else None

    def clone_repos(self, repos: List[dict] = None) -> Dict[str, bool]:
        """Clone or update repositories locally.

        Args:
            repos: List of repos to clone (None = all)

        Returns:
            Dict mapping repo full_name to success status.
        """
        if repos is None:
            repos = self.repos if self.repos else self.fetch_all_repos()

        results = {}
        print(f"\nCloning/updating {len(repos)} repositories...")

        for repo in repos:
            print(f"  {repo['full_name']}...", end=" ")
            try:
                result = ensure_repo_cloned(repo, self.base_dir)
                results[repo["full_name"]] = result is not None
                print("OK" if result else "FAILED")
            except Exception as e:
                print(f"ERROR: {e}")
                results[repo["full_name"]] = False

            time.sleep(0.3)

        success_count = sum(1 for v in results.values() if v)
        print(f"\nCloned/updated {success_count}/{len(repos)} repositories")
        return results

    def clear_cache(self):
        """Clear the repository cache."""
        try:
            if os.path.exists(self.cache_path):
                os.remove(self.cache_path)
                print("Cache cleared")
        except Exception as e:
            print(f"Failed to clear cache: {e}")

    def get_repo_by_name(self, full_name: str) -> Optional[dict]:
        """Get a specific repository by full name.

        Args:
            full_name: Repo full name (e.g., 'owner/repo')

        Returns:
            Repo dict or None if not found.
        """
        for repo in self.repos:
            if repo["full_name"] == full_name:
                return repo
        return None


def get_repo_manager() -> RepoManager:
    """Factory function to get configured RepoManager instance."""
    return RepoManager()


if __name__ == "__main__":
    manager = get_repo_manager()
    repos = manager.fetch_all_repos()
    print(f"\nFound {len(repos)} repositories:")
    for repo in repos[:10]:
        print(f"  - {repo['full_name']} ({'private' if repo['is_private'] else 'public'})")
    if len(repos) > 10:
        print(f"  ... and {len(repos) - 10} more")
