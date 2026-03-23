"""Review activity module - submit PR reviews."""
import random
import time
from datetime import date
from typing import List, Optional

import requests

from config import Config
from repo_manager import RepoManager
from activities.pull_requests import PullRequestActivity

GITHUB_API_BASE = "https://api.github.com"

REVIEW_TEMPLATES = [
    "LGTM! Clean and well-structured changes.",
    "Looks good, nice cleanup of the logic.",
    "Approved - the refactoring makes this much clearer.",
    "Good work! The error handling is much improved.",
    "Nice optimization, should improve performance significantly.",
    "Approved. The documentation updates are helpful.",
    "LGTM, thanks for adding the tests.",
    "Looks good to me. The code is more maintainable now.",
    "Approved - good catch on that edge case.",
    "Clean implementation, approved.",
    "Good refactoring, makes the code more readable.",
    "Nice work on the performance improvements.",
    "LGTM. The additional test coverage is appreciated.",
    "Approved, solid changes overall.",
    "Looks good, well-documented changes.",
]

COMMENT_TEMPLATES = [
    "Looks good! Consider adding a comment here to explain the logic.",
    "Nice changes. One small suggestion - could we add a type hint here?",
    "Good work overall. Left one minor inline comment.",
    "Looks good! Consider updating the changelog for this change.",
    "Nice refactoring. The function is much cleaner now.",
    "Good improvement. Would be nice to see a test for this case.",
    "Clean implementation! One small nitpick in the comments.",
    "Looks good. The error handling covers the main scenarios well.",
]


class ReviewActivity:
    """Handles submitting PR reviews."""

    def __init__(self, repo_manager: RepoManager = None):
        self.repo_manager = repo_manager or RepoManager()
        self.headers = Config.get_github_api_headers()

    def submit_reviews(
        self,
        target_date: date,
        count: int = 1,
        dry_run: bool = False,
    ) -> List[dict]:
        """Submit multiple PR reviews for a target date.

        Args:
            target_date: The date reviews were submitted (for logging)
            count: Number of reviews to submit
            dry_run: If True, only log what would be done

        Returns:
            List of review results.
        """
        results = []

        print(f"{'[DRY RUN] ' if dry_run else ''}Submitting {count} PR reviews...")

        open_prs = self._find_open_prs()

        for i in range(count):
            if not open_prs:
                if dry_run:
                    print("  [DRY RUN] No open PRs found, would create dummy PR")
                    results.append({
                        "repo": "N/A",
                        "pr_number": None,
                        "event": "COMMENT",
                        "timestamp": target_date.isoformat(),
                        "success": True,
                        "dry_run": True,
                        "note": "Would create dummy PR",
                    })
                    continue

                print("  No open PRs found, creating dummy PR to review...")
                dummy_pr = self._create_dummy_pr(target_date)
                if dummy_pr and dummy_pr.get("pr_number"):
                    open_prs.append({
                        "repo": dummy_pr["repo"],
                        "number": dummy_pr["pr_number"],
                    })
                else:
                    results.append({
                        "success": False,
                        "error": "Failed to create dummy PR",
                    })
                    continue

            pr_info = random.choice(open_prs)
            event = "APPROVE" if random.random() < 0.6 else "COMMENT"

            if dry_run:
                print(f"  [DRY RUN] Would submit {event} review on PR #{pr_info['number']} in {pr_info['repo']}")
                results.append({
                    "repo": pr_info["repo"],
                    "pr_number": pr_info["number"],
                    "event": event,
                    "timestamp": target_date.isoformat(),
                    "success": True,
                    "dry_run": True,
                })
                continue

            result = self._submit_single_review(pr_info["repo"], pr_info["number"], event)
            results.append(result)

            time.sleep(random.uniform(0.5, 2.0))

        success_count = sum(1 for r in results if r["success"])
        print(f"  Submitted {success_count}/{len(results)} reviews successfully")
        return results

    def _find_open_prs(self) -> List[dict]:
        """Find open pull requests across user's repos.

        Returns:
            List of dicts with repo and PR number.
        """
        open_prs = []
        repos = self.repo_manager.get_repos(n=10)

        for repo in repos:
            try:
                url = f"{GITHUB_API_BASE}/repos/{repo['full_name']}/pulls"
                params = {"state": "open", "per_page": 10}

                response = requests.get(url, headers=self.headers, params=params, timeout=30)

                if response.status_code == 200:
                    prs = response.json()
                    for pr in prs:
                        open_prs.append({
                            "repo": repo["full_name"],
                            "number": pr["number"],
                            "title": pr["title"],
                        })
            except Exception:
                continue

        return open_prs

    def _submit_single_review(self, repo_full_name: str, pr_number: int, event: str) -> dict:
        """Submit a single PR review.

        Args:
            repo_full_name: Repository full name
            pr_number: PR number
            event: Review event (APPROVE or COMMENT)

        Returns:
            Result dict with success status.
        """
        result = {
            "repo": repo_full_name,
            "pr_number": pr_number,
            "event": event,
            "success": False,
            "error": None,
        }

        try:
            url = f"{GITHUB_API_BASE}/repos/{repo_full_name}/pulls/{pr_number}/reviews"

            if event == "APPROVE":
                body = random.choice(REVIEW_TEMPLATES)
            else:
                body = random.choice(COMMENT_TEMPLATES)

            payload = {
                "body": body,
                "event": event,
            }

            response = requests.post(url, headers=self.headers, json=payload, timeout=30)

            if response.status_code == 200:
                review_data = response.json()
                result["review_id"] = review_data["id"]
                result["success"] = True
            elif response.status_code == 422:
                result["error"] = "Cannot review own PR or PR not reviewable"
            elif response.status_code == 404:
                result["error"] = "PR not found"
            else:
                result["error"] = f"HTTP {response.status_code}: {response.text}"

        except requests.exceptions.RequestException as e:
            result["error"] = f"Request failed: {e}"
        except Exception as e:
            result["error"] = f"Unexpected error: {e}"

        return result

    def _create_dummy_pr(self, target_date: date) -> dict:
        """Create a dummy PR to review when none exist.

        Args:
            target_date: Date for the PR

        Returns:
            Dict with PR info or None if failed.
        """
        pr_activity = PullRequestActivity(self.repo_manager)
        results = pr_activity.create_pull_requests(target_date, count=1, dry_run=False)
        return results[0] if results else None


def submit_reviews_for_date(
    target_date: date,
    count: int = 1,
    repo_manager: RepoManager = None,
    dry_run: bool = False,
) -> List[dict]:
    """Convenience function to submit reviews for a date.

    Args:
        target_date: The date for context
        count: Number of reviews
        repo_manager: RepoManager instance (created if None)
        dry_run: Preview mode

    Returns:
        List of review results.
    """
    activity = ReviewActivity(repo_manager)
    return activity.submit_reviews(target_date, count, dry_run)
