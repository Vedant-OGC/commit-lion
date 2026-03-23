"""Commit activity module - create backdated commits across repositories."""
import os
import random
import time
from datetime import date, datetime
from typing import List, Optional

from git import Repo

from config import Config
from repo_manager import RepoManager
from utils.date_utils import format_git_date, generate_random_timestamp
from utils.git_utils import (
    append_to_file,
    ensure_file_exists,
    ensure_repo_cloned,
    get_random_file_in_repo,
    make_commit_with_date,
    push_to_remote,
)

COMMIT_MESSAGES = [
    "refactor: clean up utility functions",
    "docs: update README with new info",
    "fix: resolve edge case in validation",
    "feat: add helper method for data processing",
    "chore: update dependencies",
    "style: format code according to standards",
    "test: add unit tests for new features",
    "perf: optimize database queries",
    "refactor: simplify error handling",
    "docs: add inline comments for clarity",
    "fix: correct typo in documentation",
    "feat: implement caching mechanism",
    "chore: remove unused imports",
    "style: consistent naming conventions",
    "test: improve test coverage",
    "refactor: extract common logic",
    "docs: update changelog",
    "fix: handle null pointer exception",
    "feat: add configuration options",
    "chore: organize project structure",
    "perf: reduce memory usage",
    "refactor: modularize components",
    "docs: add usage examples",
    "fix: address race condition",
    "feat: support multiple file formats",
    "test: fix flaky tests",
    "chore: update build scripts",
    "style: fix indentation issues",
    "refactor: improve code readability",
    "docs: document API endpoints",
]

CHANGELOG_ENTRIES = [
    "- Updated documentation and examples\n",
    "- Fixed minor bugs and edge cases\n",
    "- Improved error handling\n",
    "- Added new utility functions\n",
    "- Refactored for better maintainability\n",
    "- Optimized performance\n",
    "- Updated dependencies\n",
    "- Enhanced test coverage\n",
]


class CommitActivity:
    """Handles creating backdated commits across repositories."""

    def __init__(self, repo_manager: RepoManager = None):
        self.repo_manager = repo_manager or RepoManager()
        self.max_commits_per_repo_per_day = 2

    def create_commits(
        self,
        target_date: date,
        count: int = None,
        dry_run: bool = False,
    ) -> List[dict]:
        """Create multiple backdated commits for a target date.

        Args:
            target_date: The date to backdate commits to
            count: Number of commits to create (uses config if None)
            dry_run: If True, only log what would be done

        Returns:
            List of commit results.
        """
        if count is None:
            count = random.randint(Config.MIN_COMMITS_PER_DAY, Config.MAX_COMMITS_PER_DAY)

        results = []
        repos_used = {}

        print(f"{'[DRY RUN] ' if dry_run else ''}Creating {count} commits for {target_date}...")

        for i in range(count):
            repo = self._select_repo(repos_used)
            if not repo:
                print("  No available repos with capacity")
                break

            timestamp = generate_random_timestamp(target_date)
            repo_full_name = repo["full_name"]

            if dry_run:
                print(f"  [DRY RUN] Would commit to {repo_full_name} at {timestamp}")
                results.append({
                    "repo": repo_full_name,
                    "timestamp": timestamp.isoformat(),
                    "success": True,
                    "dry_run": True,
                })
                continue

            result = self._create_single_commit(repo, timestamp)
            results.append(result)

            if result["success"]:
                repos_used[repo_full_name] = repos_used.get(repo_full_name, 0) + 1

            time.sleep(random.uniform(0.5, 2.0))

        success_count = sum(1 for r in results if r["success"])
        print(f"  Created {success_count}/{len(results)} commits successfully")
        return results

    def _select_repo(self, repos_used: dict) -> Optional[dict]:
        """Select a repo that hasn't exceeded per-day limit.

        Args:
            repos_used: Dict tracking commits per repo today

        Returns:
            Repo dict or None if all at capacity.
        """
        repos = self.repo_manager.get_repos()
        available = [r for r in repos if repos_used.get(r["full_name"], 0) < self.max_commits_per_repo_per_day]
        return random.choice(available) if available else None

    def _create_single_commit(self, repo_info: dict, timestamp: datetime) -> dict:
        """Create a single backdated commit in a repository.

        Args:
            repo_info: Repository information dict
            timestamp: Target timestamp for the commit

        Returns:
            Result dict with success status and details.
        """
        result = {
            "repo": repo_info["full_name"],
            "timestamp": timestamp.isoformat(),
            "success": False,
            "error": None,
        }

        try:
            local_repo = ensure_repo_cloned(repo_info, self.repo_manager.base_dir)
            if not local_repo:
                result["error"] = "Failed to clone repo"
                return result

            if not self._ensure_repo_has_files(local_repo):
                result["error"] = "Repo has no files and initialization failed"
                return result

            change_type = random.choice(["changelog", "code_comment", "docs_note"])
            filepath, content = self._generate_file_change(local_repo, change_type, timestamp)

            if not filepath:
                result["error"] = "Could not generate file change"
                return result

            message = random.choice(COMMIT_MESSAGES)
            author_date = format_git_date(timestamp)
            committer_date = format_git_date(timestamp)

            committed = make_commit_with_date(
                local_repo,
                filepath,
                content,
                message,
                author_date,
                committer_date,
            )

            if not committed:
                result["error"] = "Failed to make commit"
                return result

            pushed = push_to_remote(local_repo, repo_info["default_branch"])
            if not pushed:
                result["error"] = "Failed to push"
                return result

            result["success"] = True
            result["message"] = message
            result["filepath"] = filepath

        except Exception as e:
            result["error"] = str(e)

        return result

    def _ensure_repo_has_files(self, repo: Repo) -> bool:
        """Ensure repo has at least one file, initialize if empty.

        Args:
            repo: GitPython Repo object

        Returns:
            True if repo has files (or was initialized).
        """
        try:
            files = [f for f in os.listdir(repo.working_dir) if f != ".git"]
            if files:
                return True

            readme_path = os.path.join(repo.working_dir, "README.md")
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write("# Repository\n\nAuto-initialized.\n")

            repo.index.add(["README.md"])
            repo.index.commit("Initial commit")
            push_to_remote(repo)
            return True
        except Exception:
            return False

    def _generate_file_change(self, repo: Repo, change_type: str, timestamp: datetime) -> tuple:
        """Generate a file change based on type.

        Args:
            repo: GitPython Repo object
            change_type: Type of change ('changelog', 'code_comment', 'docs_note')
            timestamp: For docs_note filename

        Returns:
            Tuple of (filepath, content).
        """
        if change_type == "changelog":
            filepath = "CHANGELOG.md"
            entry = random.choice(CHANGELOG_ENTRIES)
            existing = ""
            full_path = os.path.join(repo.working_dir, filepath)
            if os.path.exists(full_path):
                with open(full_path, "r", encoding="utf-8") as f:
                    existing = f.read()
            content = existing + entry if existing else f"# Changelog\n\n{entry}"
            return filepath, content

        elif change_type == "code_comment":
            ext = random.choice([".py", ".js", ".ts", ".md"])
            filepath = get_random_file_in_repo(repo, [ext])
            if not filepath:
                filepath = f"utils/helper{ext}"
                content = f"# Helper functions\n# Updated: {timestamp.isoformat()}\n"
            else:
                full_path = os.path.join(repo.working_dir, filepath)
                with open(full_path, "r", encoding="utf-8") as f:
                    existing = f.read()
                comment = f"\n# Note: {timestamp.strftime('%Y-%m-%d')} - maintenance update\n"
                content = existing + comment
            return filepath, content

        elif change_type == "docs_note":
            date_str = timestamp.strftime("%Y%m%d")
            filepath = f"docs/notes_{date_str}.md"
            os.makedirs(os.path.join(repo.working_dir, "docs"), exist_ok=True)
            content = f"""# Notes - {timestamp.strftime('%Y-%m-%d')}

## Daily Log

- Reviewed codebase
- Updated documentation
- Minor improvements

---
Auto-generated note.
"""
            return filepath, content

        return None, None


def create_commits_for_date(
    target_date: date,
    count: int = None,
    repo_manager: RepoManager = None,
    dry_run: bool = False,
) -> List[dict]:
    """Convenience function to create commits for a date.

    Args:
        target_date: The date to create commits for
        count: Number of commits (random if None)
        repo_manager: RepoManager instance (created if None)
        dry_run: Preview mode

    Returns:
        List of commit results.
    """
    activity = CommitActivity(repo_manager)
    return activity.create_commits(target_date, count, dry_run)
