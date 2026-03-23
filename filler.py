"""Filler orchestrator - dispatches activity generation per blank day."""
import json
import logging
import os
import random
import time
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

from config import Config
from repo_manager import RepoManager
from activities.commits import CommitActivity
from activities.issues import IssueActivity
from activities.pull_requests import PullRequestActivity
from activities.reviews import ReviewActivity
from utils.date_utils import is_future_date

LOGS_DIR = "logs"


class Filler:
    """Orchestrates activity generation for blank contribution days."""

    def __init__(self, repo_manager: RepoManager = None, dry_run: bool = False):
        self.repo_manager = repo_manager or RepoManager()
        self.dry_run = dry_run
        self.logger = self._setup_logger()
        self.weights = Config.load_activity_weights()

        self.commit_activity = CommitActivity(self.repo_manager)
        self.issue_activity = IssueActivity(self.repo_manager)
        self.pr_activity = PullRequestActivity(self.repo_manager)
        self.review_activity = ReviewActivity(self.repo_manager)

    def _setup_logger(self) -> logging.Logger:
        """Set up logging to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(LOGS_DIR, f"run_{timestamp}.log")

        os.makedirs(LOGS_DIR, exist_ok=True)

        logger = logging.getLogger(f"filler_{timestamp}")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.FileHandler(log_file)
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def fill_blank_days(
        self,
        blank_days: List[date],
        max_days: int = None,
        activity_filter: List[str] = None,
    ) -> Dict[str, List[dict]]:
        """Fill blank days with generated activities.

        Args:
            blank_days: List of dates with no contributions
            max_days: Maximum number of days to fill (None = all)
            activity_filter: List of activity types to use (None = all)

        Returns:
            Dict mapping dates to activity results.
        """
        if max_days and len(blank_days) > max_days:
            blank_days = blank_days[:max_days]

        self.logger.info(f"Starting fill for {len(blank_days)} blank days")
        print(f"\nFilling {len(blank_days)} blank contribution days...")
        if self.dry_run:
            print("*** DRY RUN MODE - No actual changes will be made ***\n")

        results = {}
        total_activities = 0

        for i, target_date in enumerate(blank_days, 1):
            if is_future_date(target_date):
                print(f"[{i}/{len(blank_days)}] Skipping future date: {target_date}")
                continue

            print(f"\n[{i}/{len(blank_days)}] Processing {target_date} ({target_date.strftime('%A')})")
            self.logger.info(f"Processing date: {target_date}")

            day_results = self._process_single_date(target_date, activity_filter)
            results[target_date.isoformat()] = day_results

            activities_count = sum(len(v) for v in day_results.values())
            total_activities += activities_count
            self.logger.info(f"Created {activities_count} activities for {target_date}")

            if i < len(blank_days):
                sleep_time = random.uniform(1.0, 3.0)
                print(f"  Sleeping {sleep_time:.1f}s before next date...")
                time.sleep(sleep_time)

        self._print_summary(results, total_activities)
        self.logger.info(f"Completed. Total activities: {total_activities}")

        return results

    def _process_single_date(
        self,
        target_date: date,
        activity_filter: List[str] = None,
    ) -> Dict[str, List[dict]]:
        """Process a single date - create activities.

        Args:
            target_date: The date to create activities for
            activity_filter: Optional filter for activity types

        Returns:
            Dict of activity type to results.
        """
        results = {
            "commits": [],
            "issues": [],
            "pull_requests": [],
            "reviews": [],
        }

        min_activities = Config.MIN_ACTIVITIES_PER_DAY
        max_activities = Config.MAX_ACTIVITIES_PER_DAY
        total_count = random.randint(min_activities, max_activities)

        distribution = self._distribute_activities(total_count, activity_filter)

        for activity_type, count in distribution.items():
            if count <= 0:
                continue

            print(f"  Creating {count} {activity_type}...")

            if activity_type == "commits":
                results["commits"] = self.commit_activity.create_commits(
                    target_date, count, self.dry_run
                )
            elif activity_type == "issues":
                results["issues"] = self.issue_activity.create_issues(
                    target_date, count, self.dry_run
                )
            elif activity_type == "pull_requests":
                results["pull_requests"] = self.pr_activity.create_pull_requests(
                    target_date, count, self.dry_run
                )
            elif activity_type == "reviews":
                results["reviews"] = self.review_activity.submit_reviews(
                    target_date, count, self.dry_run
                )

            time.sleep(random.uniform(0.5, 1.5))

        return results

    def _distribute_activities(
        self,
        total: int,
        activity_filter: List[str] = None,
    ) -> Dict[str, int]:
        """Distribute total activities across types using weights.

        Args:
            total: Total number of activities to distribute
            activity_filter: Optional list of allowed activity types

        Returns:
            Dict mapping activity type to count.
        """
        weights = self.weights.copy()

        if activity_filter:
            weights = {k: v for k, v in weights.items() if k in activity_filter}

        if not weights:
            weights = {"commits": 100}

        total_weight = sum(weights.values())
        distribution = {}

        remaining = total
        items = list(weights.items())

        for i, (activity_type, weight) in enumerate(items):
            if i == len(items) - 1:
                distribution[activity_type] = remaining
            else:
                count = max(1, round(total * weight / total_weight))
                count = min(count, remaining)
                distribution[activity_type] = count
                remaining -= count

        if "commits" not in distribution or distribution["commits"] == 0:
            if not activity_filter or "commits" in activity_filter:
                distribution["commits"] = 1
                max_key = max(distribution, key=distribution.get)
                if max_key != "commits":
                    distribution[max_key] = max(0, distribution[max_key] - 1)

        return distribution

    def _print_summary(self, results: Dict[str, List[dict]], total_activities: int):
        """Print final summary of activities created."""
        print("\n" + "=" * 60)
        print("FILL OPERATION SUMMARY")
        print("=" * 60)

        dates_processed = len(results)
        total_success = 0
        total_failed = 0

        activity_totals = {
            "commits": {"success": 0, "failed": 0},
            "issues": {"success": 0, "failed": 0},
            "pull_requests": {"success": 0, "failed": 0},
            "reviews": {"success": 0, "failed": 0},
        }

        for date_str, day_results in results.items():
            for activity_type, items in day_results.items():
                for item in items:
                    if item.get("success"):
                        total_success += 1
                        activity_totals[activity_type]["success"] += 1
                    else:
                        total_failed += 1
                        activity_totals[activity_type]["failed"] += 1

        print(f"\nDates processed: {dates_processed}")
        print(f"Total activities attempted: {total_success + total_failed}")
        print(f"Successful: {total_success}")
        print(f"Failed: {total_failed}")

        print("\nBy activity type:")
        for activity_type, counts in activity_totals.items():
            total_type = counts["success"] + counts["failed"]
            if total_type > 0:
                print(f"  {activity_type:15} | Success: {counts['success']:3} | Failed: {counts['failed']:3}")

        if self.dry_run:
            print("\n*** This was a DRY RUN - No actual changes were made ***")

        print("=" * 60)


def run_filler(
    blank_days: List[date],
    dry_run: bool = False,
    max_days: int = None,
    activity_filter: List[str] = None,
    repo_manager: RepoManager = None,
) -> Dict[str, List[dict]]:
    """Convenience function to run the filler.

    Args:
        blank_days: List of blank dates to fill
        dry_run: Preview mode
        max_days: Maximum days to process
        activity_filter: List of allowed activity types
        repo_manager: RepoManager instance

    Returns:
        Results dict.
    """
    filler = Filler(repo_manager, dry_run)
    return filler.fill_blank_days(blank_days, max_days, activity_filter)
