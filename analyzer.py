"""GitHub contribution graph analyzer - detects blank contribution days."""
from datetime import date, datetime, timezone
from typing import List, Optional

import requests
from tabulate import tabulate

from config import Config
from utils.date_utils import get_past_year_range, parse_iso_date


GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"

CONTRIBUTION_QUERY = """
query($username: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $username) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
            color
          }
        }
      }
    }
  }
}
"""


def fetch_contributions(
    username: str,
    from_date: datetime,
    to_date: datetime,
) -> Optional[dict]:
    """Fetch contribution calendar data from GitHub GraphQL API.

    Args:
        username: GitHub username to query
        from_date: Start of date range
        to_date: End of date range

    Returns:
        Raw GraphQL response data or None if failed.
    """
    headers = Config.get_graphql_headers()

    variables = {
        "username": username,
        "from": from_date.isoformat(),
        "to": to_date.isoformat(),
    }

    try:
        response = requests.post(
            GITHUB_GRAPHQL_URL,
            json={"query": CONTRIBUTION_QUERY, "variables": variables},
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            print(f"GraphQL errors: {data['errors']}")
            return None

        return data.get("data")
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch contributions: {e}")
        return None


def parse_contribution_days(data: dict) -> List[dict]:
    """Parse GraphQL response into flat list of contribution days.

    Args:
        data: Raw GraphQL response data

    Returns:
        List of dicts with date and contributionCount.
    """
    days = []
    try:
        calendar = data["user"]["contributionsCollection"]["contributionCalendar"]
        for week in calendar.get("weeks", []):
            for day in week.get("contributionDays", []):
                days.append({
                    "date": parse_iso_date(day["date"]),
                    "count": day["contributionCount"],
                    "color": day.get("color", ""),
                })
    except (KeyError, TypeError) as e:
        print(f"Failed to parse contribution data: {e}")
        return []

    return days


def get_blank_days(days: List[dict]) -> List[date]:
    """Filter for days with zero contributions.

    Args:
        days: List of contribution day dicts

    Returns:
        Sorted list of dates with contributionCount == 0.
    """
    today = date.today()
    blank_days = [day["date"] for day in days if day["count"] == 0 and day["date"] <= today]
    return sorted(blank_days)


def analyze_contributions(
    username: Optional[str] = None,
    days: int = 365,
    year: Optional[int] = None,
) -> List[date]:
    """Main analyzer function - returns blank contribution days.

    Args:
        username: GitHub username (defaults to config)
        days: Number of days to look back (default 365)
        year: Specific year to analyze (overrides days if provided)

    Returns:
        Sorted list of blank dates.
    """
    if username is None:
        username = Config.GITHUB_USERNAME

    if not username:
        raise ValueError("GitHub username not configured")

    if year:
        from_date = datetime(year, 1, 1, tzinfo=timezone.utc)
        to_date = datetime(year, 12, 31, tzinfo=timezone.utc)
    else:
        from_date, to_date = get_past_year_range(days)

    print(f"Fetching contributions for {username} from {from_date.date()} to {to_date.date()}...")

    data = fetch_contributions(username, from_date, to_date)
    if not data:
        return []

    all_days = parse_contribution_days(data)
    if not all_days:
        return []

    total_contributions = sum(day["count"] for day in all_days)
    blank_days = get_blank_days(all_days)

    print_summary(all_days, blank_days, total_contributions, from_date.date(), to_date.date())

    return blank_days


def print_summary(
    all_days: List[dict],
    blank_days: List[date],
    total_contributions: int,
    start_date: date,
    end_date: date,
):
    """Print formatted summary table of contribution analysis."""
    total_days = len(all_days)
    blank_count = len(blank_days)
    active_count = total_days - blank_count

    summary_data = [
        ["Date Range", f"{start_date} to {end_date}"],
        ["Total Days Scanned", total_days],
        ["Active Days", active_count],
        ["Blank Days Found", blank_count],
        ["Total Contributions", total_contributions],
        ["Contribution Rate", f"{active_count / total_days * 100:.1f}%" if total_days > 0 else "0%"],
    ]

    print("\n" + "=" * 50)
    print("CONTRIBUTION ANALYSIS SUMMARY")
    print("=" * 50)
    print(tabulate(summary_data, headers=["Metric", "Value"], tablefmt="grid"))
    print()


def format_blank_dates(blank_days: List[date], output_format: str = "table") -> str:
    """Format blank days for output.

    Args:
        blank_days: List of blank dates
        output_format: 'json' or 'table'

    Returns:
        Formatted string.
    """
    if output_format == "json":
        import json
        return json.dumps([d.isoformat() for d in blank_days], indent=2)

    if not blank_days:
        return "No blank days found!"

    data = [[i + 1, d.isoformat(), d.strftime("%A")] for i, d in enumerate(blank_days)]
    return tabulate(data, headers=["#", "Date", "Day"], tablefmt="grid")


if __name__ == "__main__":
    blank_days = analyze_contributions()
    if blank_days:
        print("\nBlank days (sorted ascending):")
        print(format_blank_dates(blank_days))
