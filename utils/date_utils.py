"""Date and time utility functions."""
import random
from datetime import date, datetime, timedelta, timezone
from typing import List


def get_past_year_range(days: int = 365) -> tuple[datetime, datetime]:
    """Get date range from N days ago to now.

    Returns:
        Tuple of (from_date, to_date) as datetime objects in UTC.
    """
    now = datetime.now(timezone.utc)
    from_date = now - timedelta(days=days)
    return from_date, now


def parse_iso_date(date_str: str) -> date:
    """Parse ISO format date string to date object."""
    return date.fromisoformat(date_str.replace("Z", "+00:00").split("+")[0])


def generate_random_timestamp(target_date: date, start_hour: int = 8, end_hour: int = 23) -> datetime:
    """Generate a random timestamp on a specific date within working hours.

    Args:
        target_date: The date for the timestamp
        start_hour: Start of working hours (inclusive)
        end_hour: End of working hours (inclusive)

    Returns:
        A datetime object with random time on the target date.
    """
    hour = random.randint(start_hour, end_hour)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)

    dt = datetime.combine(target_date, datetime.min.time().replace(hour=hour, minute=minute, second=second))
    return dt.replace(tzinfo=timezone.utc)


def format_git_date(dt: datetime) -> str:
    """Format datetime for GIT_AUTHOR_DATE/GIT_COMMITTER_DATE environment variables.

    Format: ISO 8601 with timezone, e.g., '2024-03-15T14:30:00+00:00'
    """
    return dt.isoformat()


def is_future_date(target_date: date) -> bool:
    """Check if a date is in the future."""
    return target_date > date.today()


def distribute_dates_across_range(start_date: date, end_date: date, count: int) -> List[date]:
    """Distribute count number of dates randomly across a date range.

    Args:
        start_date: Start of range (inclusive)
        end_date: End of range (inclusive)
        count: Number of dates to generate

    Returns:
        List of unique dates, sorted ascending.
    """
    if count <= 0:
        return []

    total_days = (end_date - start_date).days + 1
    if count >= total_days:
        return sorted([start_date + timedelta(days=i) for i in range(total_days)])

    selected_indices = random.sample(range(total_days), count)
    return sorted([start_date + timedelta(days=i) for i in selected_indices])


def get_iso_timestamp(dt: datetime) -> str:
    """Get ISO 8601 timestamp string."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_date_string(date_str: str) -> date:
    """Parse date from various string formats.

    Supports:
    - ISO format: 2024-03-15
    - With slashes: 2024/03/15
    """
    cleaned = date_str.strip().replace("/", "-")
    return date.fromisoformat(cleaned)


def get_year_start_end(year: int) -> tuple[date, date]:
    """Get start and end dates for a specific year.

    Returns:
        Tuple of (jan_1, dec_31) for the specified year.
    """
    return date(year, 1, 1), date(year, 12, 31)
