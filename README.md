# GitHub Contribution Graph Filler

An open-source Python toolchain for learning GitHub API integrations. This project demonstrates how to interact with GitHub's REST API v3 and GraphQL API v4 to analyze contribution activity and generate backdated contributions programmatically.

> **Purpose**: Educational tool for understanding GitHub API authentication, GraphQL queries, repository management, and git operations automation.

## ⚠️ Disclaimer

This tool is intended **for demo and educational use only**. It demonstrates GitHub API integration patterns and is designed for use on repositories you own. Using this tool to misrepresent your contributions or deceive others violates GitHub's Terms of Service and the spirit of open source collaboration. Use responsibly.

## 📋 Prerequisites

- Python 3.11+
- Git installed locally
- GitHub account with at least one repository
- GitHub Personal Access Token (PAT) with appropriate scopes

## 🔧 Setup

### 1. Clone and Install

```bash
git clone <repository-url>
cd gh-contrib-filler
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```env
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
GITHUB_USERNAME=your_username
COMMIT_AUTHOR_NAME=Your Name
COMMIT_AUTHOR_EMAIL=your@email.com
LOCAL_REPOS_BASE_DIR=./repos
```

### 3. Get a GitHub Personal Access Token

1. Go to **GitHub Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens**
2. Click **Generate new token**
3. Set the token name and expiration
4. Select **All repositories** or specific repositories
5. Grant the following permissions:
   - **Repository permissions**:
     - Contents: Read and write
     - Issues: Read and write
     - Pull requests: Read and write
     - Metadata: Read (mandatory)
   - **Account permissions**:
     - Read user profile data

Copy the generated token to your `.env` file.

## 🚀 Usage

### Analyze Contribution Graph

Find all days in the past year with zero contributions:

```bash
python main.py analyze
```

Analyze a specific year:

```bash
python main.py analyze --year 2024
```

Output as JSON:

```bash
python main.py analyze --output json
```

### Fill Blank Days (Dry Run)

Preview what activities would be created without making changes:

```bash
python main.py fill --year 2024 --dry-run
```

### Fill Blank Days (Actual)

Generate activities for all blank days in a year:

```bash
python main.py fill --year 2024
```

Fill specific dates only:

```bash
python main.py fill --dates 2024-03-15,2024-04-02
```

Limit to specific activity types:

```bash
python main.py fill --activity commits,issues --max-days 10
```

### Check Status

Verify how many days are still blank:

```bash
python main.py status
```

## 📁 Project Structure

```
gh-contrib-filler/
├── main.py                  # CLI entrypoint
├── analyzer.py              # GraphQL contribution analyzer
├── filler.py                # Activity orchestrator
├── repo_manager.py          # Auto repo discovery and cloning
├── config.py                # Configuration management
├── activities/
│   ├── commits.py           # Backdated commit generator
│   ├── issues.py            # Issue creator
│   ├── pull_requests.py     # PR creator
│   └── reviews.py           # PR review submitter
├── utils/
│   ├── date_utils.py        # Date/time helpers
│   └── git_utils.py         # GitPython wrappers
├── logs/                    # Operation logs
├── requirements.txt
├── .env.example
└── README.md
```

## 🔧 Configuration

All configuration is managed via environment variables in `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_TOKEN` | Fine-grained PAT | Required |
| `GITHUB_USERNAME` | Your GitHub username | Required |
| `COMMIT_AUTHOR_NAME` | Git author name | Required |
| `COMMIT_AUTHOR_EMAIL` | Git author email | Required |
| `LOCAL_REPOS_BASE_DIR` | Local repo storage | `./repos` |
| `MIN_COMMITS_PER_DAY` | Min commits per day | `3` |
| `MAX_COMMITS_PER_DAY` | Max commits per day | `6` |
| `ACTIVITY_WEIGHTS` | Activity distribution | `commits:50,issues:20,pull_requests:20,reviews:10` |
| `INCLUDE_FORKS` | Include forked repos | `false` |

## 🧩 How Activity Types Contribute to the Graph

GitHub's contribution graph counts various activities:

| Activity | Counts as Contribution | Notes |
|----------|------------------------|-------|
| **Commits** | ✅ Yes | On default branch or gh-pages |
| **Issues** | ✅ Yes | Created or assigned |
| **Pull Requests** | ✅ Yes | Opened, merged, or reviewed |
| **PR Reviews** | ✅ Yes | Comments, approvals |

## 🔒 Rate Limiting & Safety

The tool implements several safety measures:

- **Rate limit checking**: Monitors `X-RateLimit-Remaining` and sleeps when low
- **Graceful failures**: API errors are logged but don't crash the tool
- **Configurable delays**: Random sleeps between operations (0.5-2s)
- **Dry-run mode**: Preview all actions without making changes
- **Future date protection**: Automatically skips dates in the future
- **Repository limits**: Max 2 commits per repo per day to avoid spam patterns

## 🛠️ API Implementation Details

### GraphQL Contribution Query

The analyzer uses this GraphQL query to fetch contribution data:

```graphql
query($username: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $username) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
```

### REST API Endpoints Used

- `GET /user/repos` - List all repositories
- `POST /repos/{owner}/{repo}/issues` - Create issues
- `POST /repos/{owner}/{repo}/pulls` - Create PRs
- `PUT /repos/{owner}/{repo}/pulls/{number}/merge` - Merge PRs
- `POST /repos/{owner}/{repo}/pulls/{number}/reviews` - Submit reviews

## 📊 Sample Output

### Analyze Command

```
Fetching contributions for username from 2023-03-22 to 2024-03-22...

==================================================
CONTRIBUTION ANALYSIS SUMMARY
==================================================
+----------------------+------------------------+
| Metric               | Value                  |
+----------------------+------------------------+
| Date Range           | 2023-03-22 to 2024-03-22
| Total Days Scanned   | 366                    |
| Active Days          | 298                    |
| Blank Days Found     | 68                     |
| Total Contributions  | 1247                   |
| Contribution Rate      | 81.4%                  |
+----------------------+------------------------+
```

### Fill Command (Dry Run)

```
Filling 68 blank contribution days...
*** DRY RUN MODE - No actual changes will be made ***

[1/68] Processing 2024-01-15 (Monday)
  Creating 3 commits...
  [DRY RUN] Would commit to owner/repo1 at 2024-01-15 14:32:00+00:00
  ...
```

## 🐛 Troubleshooting

### "Repository not found" errors
- Ensure your token has access to the repository
- Check if the repository is private (needs `repo` scope)

### "Issues are disabled"
- Some repositories may have issues disabled
- The tool will skip these automatically

### "Branch protection" errors
- Some repos may have protected default branches
- PR creation will fail gracefully, commits may still work

### Rate limit exceeded
- The tool will automatically sleep when rate limits are approached
- For large operations, consider running over multiple sessions

## 📚 Learning Resources

This project demonstrates:

1. **GitHub GraphQL API** - Querying user contribution data
2. **GitHub REST API** - Creating issues, PRs, and reviews
3. **GitPython** - Programmatic git operations
4. **Backdated commits** - Using `GIT_AUTHOR_DATE` and `GIT_COMMITTER_DATE`
5. **API rate limiting** - Handling HTTP 429 responses
6. **Configuration management** - Environment-based config
7. **CLI design** - argparse with subcommands

## 🤝 Contributing

This is an educational project. Feel free to fork and experiment with the code to learn more about GitHub APIs and git automation.

## 📄 License

MIT License - See LICENSE file for details.

## ⚠️ Important Notes

1. **Token Security**: Never commit your `.env` file or expose your PAT
2. **Repository Ownership**: Only use on repositories you own
3. **Rate Limits**: GitHub API has hourly rate limits - the tool respects these
4. **Contribution Graph Updates**: Changes may take a few minutes to appear on your profile
5. **Git History**: Backdated commits will appear in git history with the specified dates

# Note: 2026-04-07 - maintenance update
