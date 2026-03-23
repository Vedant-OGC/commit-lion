#!/usr/bin/env python3
"""Main CLI entrypoint for GitHub Contribution Graph Filler."""
import argparse
import sys
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from analyzer import analyze_contributions, format_blank_dates
from config import Config
from filler import run_filler
from repo_manager import RepoManager
from utils.date_utils import parse_date_string

console = Console()


def print_banner():
    """Print application banner."""
    banner = Text()
    banner.append("GitHub Contribution Graph Filler\n", style="bold cyan")
    banner.append("Automated activity generation for learning GitHub APIs", style="dim")
    console.print(Panel(banner, border_style="cyan"))


def validate_config() -> bool:
    """Validate required configuration."""
    missing = Config.validate()
    if missing:
        console.print("[red]Error: Missing required configuration:[/red]")
        for item in missing:
            console.print(f"  - {item}")
        console.print("\n[yellow]Please set these in your .env file[/yellow]")
        return False
    return True


def cmd_analyze(args):
    """Execute the analyze command."""
    if not validate_config():
        return 1

    console.print(f"[blue]Analyzing contributions for {Config.GITHUB_USERNAME}...[/blue]\n")

    try:
        blank_days = analyze_contributions(
            username=args.username,
            days=args.days,
            year=args.year,
        )

        if args.output == "json":
            console.print(format_blank_dates(blank_days, "json"))
        else:
            console.print(format_blank_dates(blank_days, "table"))

        return 0
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1


def cmd_fill(args):
    """Execute the fill command."""
    if not validate_config():
        return 1

    print_banner()

    try:
        if args.dates:
            from datetime import date
            blank_days = [parse_date_string(d) for d in args.dates.split(",")]
            blank_days = [d for d in blank_days if d <= date.today()]
        else:
            year = args.year
            if not year:
                from datetime import datetime
                year = datetime.now().year

            console.print(f"[blue]Analyzing {year} contributions...[/blue]")
            blank_days = analyze_contributions(year=year)

        if not blank_days:
            console.print("[green]No blank days found! Nothing to fill.[/green]")
            return 0

        activity_filter = args.activity.split(",") if args.activity else None

        if args.dry_run:
            console.print("[yellow]DRY RUN MODE - No changes will be made[/yellow]\n")

        repo_manager = RepoManager()
        repo_manager.fetch_all_repos()

        results = run_filler(
            blank_days=blank_days,
            dry_run=args.dry_run,
            max_days=args.max_days,
            activity_filter=activity_filter,
            repo_manager=repo_manager,
        )

        return 0
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1


def cmd_status(args):
    """Execute the status command."""
    if not validate_config():
        return 1

    console.print(f"[blue]Checking current status for {Config.GITHUB_USERNAME}...[/blue]\n")

    try:
        year = args.year if args.year else None
        blank_days = analyze_contributions(year=year)

        if blank_days:
            console.print(f"[yellow]There are still {len(blank_days)} blank days.[/yellow]")
        else:
            console.print("[green]No blank days! Contribution graph is filled.[/green]")

        return 0
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1


def main(argv: Optional[List[str]] = None) -> int:
    """Main entrypoint."""
    parser = argparse.ArgumentParser(
        prog="gh-contrib-filler",
        description="GitHub Contribution Graph Filler - Automated activity generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py analyze
  python main.py analyze --year 2024 --output json
  python main.py fill --year 2024 --dry-run
  python main.py fill --dates 2024-03-15,2024-04-02
  python main.py fill --activity commits,issues --max-days 10
  python main.py status
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze contribution graph and show blank days",
    )
    analyze_parser.add_argument(
        "--username",
        type=str,
        help="GitHub username (default: from .env)",
    )
    analyze_parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Number of days to look back (default: 365)",
    )
    analyze_parser.add_argument(
        "--year",
        type=int,
        help="Specific year to analyze",
    )
    analyze_parser.add_argument(
        "--output",
        choices=["json", "table"],
        default="table",
        help="Output format (default: table)",
    )

    fill_parser = subparsers.add_parser(
        "fill",
        help="Fill blank days with generated activities",
    )
    fill_parser.add_argument(
        "--dates",
        type=str,
        help="Comma-separated specific dates (e.g., 2024-03-15,2024-04-02)",
    )
    fill_parser.add_argument(
        "--year",
        type=int,
        help="Fill all blank days in a specific year",
    )
    fill_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview only, no actual changes",
    )
    fill_parser.add_argument(
        "--activity",
        type=str,
        help="Limit to specific activity types (e.g., commits,issues)",
    )
    fill_parser.add_argument(
        "--max-days",
        type=int,
        help="Maximum number of blank days to fill",
    )

    status_parser = subparsers.add_parser(
        "status",
        help="Check current contribution status",
    )
    status_parser.add_argument(
        "--year",
        type=int,
        help="Check status for specific year",
    )

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "analyze":
        return cmd_analyze(args)
    elif args.command == "fill":
        return cmd_fill(args)
    elif args.command == "status":
        return cmd_status(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
