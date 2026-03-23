"""Issue activity module - create backdated GitHub issues."""
import random
import time
from datetime import date, datetime
from typing import List, Optional

import requests

from config import Config
from repo_manager import RepoManager
from utils.date_utils import get_iso_timestamp, generate_random_timestamp

GITHUB_API_BASE = "https://api.github.com"

ISSUE_TEMPLATES = {
    "enhancement": [
        ("Add support for batch processing", "It would be helpful to support batch operations for better performance with large datasets."),
        ("Implement caching layer", "Adding a Redis cache would significantly improve response times for frequently accessed data."),
        ("Add export to CSV functionality", "Users have requested the ability to export reports in CSV format for external analysis."),
        ("Support for dark mode", "Implement a dark theme toggle for better user experience in low-light environments."),
        ("Add keyboard shortcuts", "Power users would benefit from keyboard navigation shortcuts for common actions."),
    ],
    "bug": [
        ("Fix memory leak in data processing", "Memory usage grows continuously during long-running batch operations."),
        ("Resolve race condition in concurrent access", "Multiple simultaneous requests occasionally cause data inconsistency."),
        ("Fix validation error on empty input", "Submitting empty form fields causes an unhandled exception."),
        ("Address timeout on slow connections", "Large file uploads fail on connections with high latency."),
        ("Correct timezone handling", "Date displays are incorrect for users in non-UTC timezones."),
    ],
    "documentation": [
        ("Update API documentation examples", "The current examples don't show the new filter parameters."),
        ("Add deployment guide", "Need step-by-step instructions for production deployment."),
        ("Document environment variables", "Missing documentation for several new configuration options."),
        ("Add troubleshooting section", "Common issues and solutions should be documented."),
        ("Improve README structure", "The README could be better organized with clear sections."),
    ],
}


class IssueActivity:
    """Handles creating backdated GitHub issues."""

    def __init__(self, repo_manager: RepoManager = None):
        self.repo_manager = repo_manager or RepoManager()
        self.headers = Config.get_github_api_headers()

    def create_issues(
        self,
        target_date: date,
        count: int = 1,
        dry_run: bool = False,
    ) -> List[dict]:
        """Create multiple backdated issues for a target date.

        Args:
            target_date: The date to backdate issues to
            count: Number of issues to create
            dry_run: If True, only log what would be done

        Returns:
            List of issue results.
        """
        results = []

        print(f"{'[DRY RUN] ' if dry_run else ''}Creating {count} issues for {target_date}...")

        for i in range(count):
            repo = self._select_repo()
            if not repo:
                print("  No available repos with issues enabled")
                break

            timestamp = generate_random_timestamp(target_date)
            label = random.choice(list(ISSUE_TEMPLATES.keys()))
            title, body_template = random.choice(ISSUE_TEMPLATES[label])

            body = f"{body_template}\n\n---\n*Reported on {timestamp.strftime('%Y-%m-%d %H:%M')}*"

            if dry_run:
                print(f"  [DRY RUN] Would create issue in {repo['full_name']}: {title}")
                results.append({
                    "repo": repo["full_name"],
                    "title": title,
                    "label": label,
                    "timestamp": timestamp.isoformat(),
                    "success": True,
                    "dry_run": True,
                })
                continue

            result = self._create_single_issue(repo, title, body, label, timestamp)
            results.append(result)

            time.sleep(random.uniform(0.5, 2.0))

        success_count = sum(1 for r in results if r["success"])
        print(f"  Created {success_count}/{len(results)} issues successfully")
        return results

    def _select_repo(self) -> Optional[dict]:
        """Select a random repo that has issues enabled.

        Returns:
            Repo dict or None.
        """
        repos = self.repo_manager.get_repos()
        candidates = [r for r in repos if r.get("has_issues", True)]
        return random.choice(candidates) if candidates else None

    def _create_single_issue(
        self,
        repo_info: dict,
        title: str,
        body: str,
        label: str,
        timestamp: datetime,
    ) -> dict:
        """Create a single issue via GitHub API.

        Args:
            repo_info: Repository information dict
            title: Issue title
            body: Issue body
            label: Issue label
            timestamp: Target creation timestamp

        Returns:
            Result dict with success status and details.
        """
        result = {
            "repo": repo_info["full_name"],
            "title": title,
            "label": label,
            "timestamp": timestamp.isoformat(),
            "success": False,
            "issue_number": None,
            "error": None,
        }

        try:
            url = f"{GITHUB_API_BASE}/repos/{repo_info['full_name']}/issues"
            payload = {
                "title": title,
                "body": body,
                "labels": [label],
            }

            response = requests.post(url, headers=self.headers, json=payload, timeout=30)

            if response.status_code == 201:
                issue_data = response.json()
                result["issue_number"] = issue_data["number"]
                result["issue_url"] = issue_data["html_url"]

                if random.random() < 0.4:
                    closed = self._close_issue(repo_info, issue_data["number"])
                    result["closed"] = closed

                result["success"] = True
            elif response.status_code == 410:
                result["error"] = "Issues are disabled for this repository"
            elif response.status_code == 404:
                result["error"] = "Repository not found or no access"
            else:
                result["error"] = f"HTTP {response.status_code}: {response.text}"

        except requests.exceptions.RequestException as e:
            result["error"] = f"Request failed: {e}"
        except Exception as e:
            result["error"] = f"Unexpected error: {e}"

        return result

    def _close_issue(self, repo_info: dict, issue_number: int) -> bool:
        """Close an issue immediately after creation.

        Args:
            repo_info: Repository information
            issue_number: Issue number to close

        Returns:
            True if successfully closed.
        """
        try:
            url = f"{GITHUB_API_BASE}/repos/{repo_info['full_name']}/issues/{issue_number}"
            payload = {"state": "closed"}

            response = requests.patch(url, headers=self.headers, json=payload, timeout=30)
            return response.status_code == 200
        except Exception:
            return False


def create_issues_for_date(
    target_date: date,
    count: int = 1,
    repo_manager: RepoManager = None,
    dry_run: bool = False,
) -> List[dict]:
    """Convenience function to create issues for a date.

    Args:
        target_date: The date to create issues for
        count: Number of issues
        repo_manager: RepoManager instance (created if None)
        dry_run: Preview mode

    Returns:
        List of issue results.
    """
    activity = IssueActivity(repo_manager)
    return activity.create_issues(target_date, count, dry_run)
