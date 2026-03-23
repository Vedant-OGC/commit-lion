"""Pull request activity module - create backdated PRs."""
import os
import random
import time
from datetime import date, datetime
from typing import List, Optional

import requests
from git import Repo

from config import Config
from repo_manager import RepoManager
from utils.date_utils import format_git_date, generate_random_timestamp
from utils.git_utils import (
    create_and_checkout_branch,
    ensure_repo_cloned,
    get_random_file_in_repo,
    make_commit_with_date,
    push_to_remote,
)

GITHUB_API_BASE = "https://api.github.com"

PR_TEMPLATES = [
    ("feat: add utility helpers", "This PR adds helper functions for common operations.\n\n## Changes\n- Added utility modules\n- Improved code organization\n- Added documentation"),
    ("chore: update dependencies", "Updating project dependencies to latest compatible versions.\n\n## Updates\n- Security patches\n- Performance improvements\n- Bug fixes from upstream"),
    ("refactor: simplify data processing", "Refactoring the data layer for better maintainability.\n\n## Improvements\n- Reduced complexity\n- Better error handling\n- More testable code"),
    ("docs: update README and examples", "Improving documentation clarity and adding more examples.\n\n## Changes\n- Updated README\n- Added code examples\n- Fixed typos"),
    ("fix: resolve edge cases in validation", "Addressing edge cases discovered in production.\n\n## Fixes\n- Better input validation\n- Improved error messages\n- Added test coverage"),
    ("perf: optimize database queries", "Optimizing slow queries identified in profiling.\n\n## Optimizations\n- Added indexes\n- Reduced N+1 queries\n- Better caching"),
    ("style: consistent code formatting", "Applying consistent formatting across the codebase.\n\n## Changes\n- Standardized indentation\n- Consistent naming\n- Import organization"),
    ("test: improve test coverage", "Adding tests for previously uncovered code paths.\n\n## Coverage\n- Unit tests\n- Integration tests\n- Edge case handling"),
    ("feat: add configuration options", "Making the application more configurable.\n\n## Features\n- Environment-based config\n- Runtime configuration\n- Better defaults"),
    ("chore: clean up unused code", "Removing deprecated and unused code.\n\n## Cleanup\n- Removed dead code\n- Deleted unused imports\n- Simplified structure"),
    ("refactor: extract common logic", "Extracting shared code into reusable modules.\n\n## Refactoring\n- Created shared utilities\n- Reduced duplication\n- Better separation of concerns"),
    ("fix: handle null pointer exceptions", "Adding null checks to prevent runtime errors.\n\n## Safety\n- Added null guards\n- Better error handling\n- Defensive programming"),
    ("feat: support multiple file formats", "Extending support for additional file types.\n\n## Formats\n- CSV support\n- JSON support\n- XML support"),
    ("docs: add API documentation", "Documenting the REST API endpoints.\n\n## Documentation\n- Endpoint descriptions\n- Request/response examples\n- Authentication details"),
    ("chore: update build scripts", "Improving build and deployment automation.\n\n## Build\n- Updated CI/CD\n- Better error reporting\n- Faster builds"),
    ("perf: reduce memory usage", "Optimizing memory consumption for large datasets.\n\n## Memory\n- Streaming processing\n- Better garbage collection\n- Resource cleanup"),
    ("refactor: improve error handling", "Centralizing and improving error handling.\n\n## Errors\n- Consistent error types\n- Better logging\n- User-friendly messages"),
    ("test: add integration tests", "Adding tests for component interactions.\n\n## Tests\n- API integration\n- Database integration\n- External service mocks"),
    ("fix: correct timezone handling", "Fixing timezone-related bugs in date processing.\n\n## Timezones\n- UTC normalization\n- User timezone display\n- DST handling"),
    ("feat: implement batch operations", "Adding support for batch processing.\n\n## Batch\n- Bulk create\n- Bulk update\n- Progress tracking"),
]


class PullRequestActivity:
    """Handles creating backdated pull requests."""

    def __init__(self, repo_manager: RepoManager = None):
        self.repo_manager = repo_manager or RepoManager()
        self.headers = Config.get_github_api_headers()

    def create_pull_requests(
        self,
        target_date: date,
        count: int = 1,
        dry_run: bool = False,
    ) -> List[dict]:
        """Create multiple backdated pull requests for a target date.

        Args:
            target_date: The date to backdate PRs to
            count: Number of PRs to create
            dry_run: If True, only log what would be done

        Returns:
            List of PR results.
        """
        results = []

        print(f"{'[DRY RUN] ' if dry_run else ''}Creating {count} pull requests for {target_date}...")

        for i in range(count):
            repo = self._select_repo()
            if not repo:
                print("  No available repos")
                break

            timestamp = generate_random_timestamp(target_date)
            title, body = random.choice(PR_TEMPLATES)
            suffix = f"auto-{timestamp.strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
            branch_name = f"contrib/{suffix}"

            if dry_run:
                print(f"  [DRY RUN] Would create PR in {repo['full_name']}: {title}")
                results.append({
                    "repo": repo["full_name"],
                    "title": title,
                    "branch": branch_name,
                    "timestamp": timestamp.isoformat(),
                    "success": True,
                    "dry_run": True,
                })
                continue

            result = self._create_single_pr(repo, title, body, branch_name, timestamp)
            results.append(result)

            time.sleep(random.uniform(0.5, 2.0))

        success_count = sum(1 for r in results if r["success"])
        print(f"  Created {success_count}/{len(results)} pull requests successfully")
        return results

    def _select_repo(self) -> Optional[dict]:
        """Select a random repo.

        Returns:
            Repo dict or None.
        """
        repos = self.repo_manager.get_repos()
        return random.choice(repos) if repos else None

    def _create_single_pr(
        self,
        repo_info: dict,
        title: str,
        body: str,
        branch_name: str,
        timestamp: datetime,
    ) -> dict:
        """Create a single pull request via GitHub API.

        Args:
            repo_info: Repository information dict
            title: PR title
            body: PR body
            branch_name: Feature branch name
            timestamp: Target timestamp

        Returns:
            Result dict with success status and details.
        """
        result = {
            "repo": repo_info["full_name"],
            "title": title,
            "branch": branch_name,
            "timestamp": timestamp.isoformat(),
            "success": False,
            "pr_number": None,
            "merged": False,
            "error": None,
        }

        local_repo = None
        try:
            local_repo = ensure_repo_cloned(repo_info, self.repo_manager.base_dir)
            if not local_repo:
                result["error"] = "Failed to clone repo"
                return result

            default_branch = repo_info["default_branch"]
            local_repo.git.checkout(default_branch)

            if not create_and_checkout_branch(local_repo, branch_name):
                result["error"] = "Failed to create branch"
                return result

            if not self._make_change_and_commit(local_repo, timestamp):
                result["error"] = "Failed to make commit"
                return result

            if not push_to_remote(local_repo, branch_name):
                result["error"] = "Failed to push branch"
                return result

            url = f"{GITHUB_API_BASE}/repos/{repo_info['full_name']}/pulls"
            payload = {
                "title": title,
                "body": body,
                "head": branch_name,
                "base": default_branch,
            }

            response = requests.post(url, headers=self.headers, json=payload, timeout=30)

            if response.status_code == 201:
                pr_data = response.json()
                result["pr_number"] = pr_data["number"]
                result["pr_url"] = pr_data["html_url"]
                result["success"] = True

                if random.random() < 0.5:
                    merged = self._merge_pr(repo_info, pr_data["number"])
                    result["merged"] = merged
                    if merged:
                        self._delete_branch(repo_info, branch_name)

            elif response.status_code == 422:
                error_msg = response.json().get("message", "")
                if "No commits" in error_msg:
                    result["error"] = "No commits between branches"
                else:
                    result["error"] = f"Validation failed: {error_msg}"
            elif response.status_code == 409:
                result["error"] = "Merge conflict or branch protection"
            else:
                result["error"] = f"HTTP {response.status_code}: {response.text}"

        except requests.exceptions.RequestException as e:
            result["error"] = f"Request failed: {e}"
        except Exception as e:
            result["error"] = f"Unexpected error: {e}"
        finally:
            if local_repo:
                try:
                    local_repo.git.checkout(repo_info["default_branch"])
                except Exception:
                    pass

        return result

    def _make_change_and_commit(self, repo: Repo, timestamp: datetime) -> bool:
        """Make a small file change and commit it.

        Args:
            repo: GitPython Repo object
            timestamp: Commit timestamp

        Returns:
            True if successful.
        """
        try:
            change_type = random.choice(["comment", "docs", "config"])

            if change_type == "comment":
                filepath = get_random_file_in_repo(repo, [".py", ".js", ".ts"])
                if not filepath:
                    filepath = "update.py"
                    content = f"# Update {timestamp.isoformat()}\n"
                else:
                    full_path = os.path.join(repo.working_dir, filepath)
                    with open(full_path, "r", encoding="utf-8") as f:
                        existing = f.read()
                    content = existing + f"\n# Updated: {timestamp.strftime('%Y-%m-%d')}\n"
            elif change_type == "docs":
                filepath = "CONTRIBUTING.md"
                full_path = os.path.join(repo.working_dir, filepath)
                if os.path.exists(full_path):
                    with open(full_path, "r", encoding="utf-8") as f:
                        existing = f.read()
                    content = existing + f"\n## Update {timestamp.strftime('%Y-%m-%d')}\n\nRegular maintenance update.\n"
                else:
                    content = f"# Contributing\n\nLast updated: {timestamp.strftime('%Y-%m-%d')}\n"
            else:
                filepath = ".github/config.yml"
                os.makedirs(os.path.join(repo.working_dir, ".github"), exist_ok=True)
                content = f"# Configuration\nlast_updated: {timestamp.strftime('%Y-%m-%d')}\n"

            author_date = format_git_date(timestamp)
            committer_date = format_git_date(timestamp)

            return make_commit_with_date(
                repo,
                filepath,
                content,
                f"Update: {timestamp.strftime('%Y-%m-%d')}",
                author_date,
                committer_date,
            )
        except Exception as e:
            print(f"Failed to make change: {e}")
            return False

    def _merge_pr(self, repo_info: dict, pr_number: int) -> bool:
        """Merge a pull request.

        Args:
            repo_info: Repository information
            pr_number: PR number to merge

        Returns:
            True if successfully merged.
        """
        try:
            url = f"{GITHUB_API_BASE}/repos/{repo_info['full_name']}/pulls/{pr_number}/merge"
            payload = {"merge_method": "squash"}

            response = requests.put(url, headers=self.headers, json=payload, timeout=30)
            return response.status_code == 200
        except Exception:
            return False

    def _delete_branch(self, repo_info: dict, branch_name: str) -> bool:
        """Delete a remote branch.

        Args:
            repo_info: Repository information
            branch_name: Branch to delete

        Returns:
            True if successfully deleted.
        """
        try:
            url = f"{GITHUB_API_BASE}/repos/{repo_info['full_name']}/git/refs/heads/{branch_name}"
            response = requests.delete(url, headers=self.headers, timeout=30)
            return response.status_code == 204
        except Exception:
            return False


def create_pull_requests_for_date(
    target_date: date,
    count: int = 1,
    repo_manager: RepoManager = None,
    dry_run: bool = False,
) -> List[dict]:
    """Convenience function to create PRs for a date.

    Args:
        target_date: The date to create PRs for
        count: Number of PRs
        repo_manager: RepoManager instance (created if None)
        dry_run: Preview mode

    Returns:
        List of PR results.
    """
    activity = PullRequestActivity(repo_manager)
    return activity.create_pull_requests(target_date, count, dry_run)
