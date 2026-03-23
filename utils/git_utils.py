"""Git utility functions using GitPython."""
import os
import random
import time
from pathlib import Path
from typing import List, Optional

from git import Repo, GitCommandError, Actor
from git.exc import InvalidGitRepositoryError

from config import Config


def ensure_repo_cloned(repo_info: dict, base_dir: str) -> Optional[Repo]:
    """Clone a repository if not already present, or fetch updates.

    Args:
        repo_info: Dict with repo details (full_name, clone_url, default_branch)
        base_dir: Local directory for storing repos

    Returns:
        GitPython Repo object or None if failed.
    """
    repo_name = repo_info["full_name"].replace("/", "_")
    local_path = os.path.join(base_dir, repo_name)

    try:
        if os.path.exists(local_path):
            try:
                repo = Repo(local_path)
                origin = repo.remotes.origin
                origin.fetch()
                return repo
            except InvalidGitRepositoryError:
                pass

        os.makedirs(base_dir, exist_ok=True)

        clone_url = repo_info["clone_url"]
        if repo_info.get("is_private") and "github.com" in clone_url:
            clone_url = clone_url.replace("https://", f"https://{Config.GITHUB_TOKEN}@")
        elif "github.com" in clone_url:
            clone_url = clone_url.replace("https://", f"https://{Config.GITHUB_TOKEN}@")

        repo = Repo.clone_from(clone_url, local_path)
        return repo
    except Exception as e:
        print(f"Failed to clone/fetch {repo_info['full_name']}: {e}")
        return None


def ensure_file_exists(repo: Repo, filepath: str, content: str = "") -> bool:
    """Ensure a file exists in the repo, create with content if not.

    Args:
        repo: GitPython Repo object
        filepath: Relative path to file
        content: Content to write if file doesn't exist

    Returns:
        True if file now exists (created or already present).
    """
    full_path = os.path.join(repo.working_dir, filepath)
    if os.path.exists(full_path):
        return True

    try:
        os.makedirs(os.path.dirname(full_path) if "/" in filepath else repo.working_dir, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"Failed to create file {filepath}: {e}")
        return False


def make_commit_with_date(
    repo: Repo,
    filepath: str,
    content: str,
    message: str,
    author_date: str,
    committer_date: str,
) -> bool:
    """Make a commit with specific author and committer dates.

    Args:
        repo: GitPython Repo object
        filepath: File to modify (relative to repo root)
        content: New content for the file
        message: Commit message
        author_date: Author date in ISO format (e.g., '2024-03-15T14:30:00+00:00')
        committer_date: Committer date in ISO format

    Returns:
        True if commit was successful.
    """
    try:
        full_path = os.path.join(repo.working_dir, filepath)
        # Ensure directory exists
        dir_path = os.path.dirname(full_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        repo.index.add([filepath])

        # Use git command directly with env vars - this properly sets dates
        import os as _os
        _old_env = _os.environ.copy()
        _os.environ["GIT_AUTHOR_DATE"] = author_date
        _os.environ["GIT_COMMITTER_DATE"] = committer_date
        _os.environ["GIT_AUTHOR_NAME"] = Config.COMMIT_AUTHOR_NAME
        _os.environ["GIT_AUTHOR_EMAIL"] = Config.COMMIT_AUTHOR_EMAIL
        _os.environ["GIT_COMMITTER_NAME"] = Config.COMMIT_AUTHOR_NAME
        _os.environ["GIT_COMMITTER_EMAIL"] = Config.COMMIT_AUTHOR_EMAIL
        
        try:
            repo.git.commit("-m", message, author=f"{Config.COMMIT_AUTHOR_NAME} <{Config.COMMIT_AUTHOR_EMAIL}>")
        finally:
            # Restore environment
            for key in ["GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE", "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"]:
                if key in _old_env:
                    _os.environ[key] = _old_env[key]
                elif key in _os.environ:
                    del _os.environ[key]
        return True
    except Exception as e:
        print(f"Failed to make commit: {e}")
        return False


def push_to_remote(repo: Repo, branch: str = None, max_retries: int = 1) -> bool:
    """Push current branch to remote.

    Args:
        repo: GitPython Repo object
        branch: Branch name (defaults to current branch)
        max_retries: Number of retry attempts on conflict

    Returns:
        True if push was successful.
    """
    try:
        origin = repo.remotes.origin

        if branch is None:
            branch = repo.active_branch.name

        try:
            origin.push(refspec=f"{branch}:{branch}")
            return True
        except GitCommandError as e:
            if "rejected" in str(e).lower() or "conflict" in str(e).lower():
                if max_retries > 0:
                    try:
                        repo.git.pull("origin", branch, "--rebase")
                        origin.push(refspec=f"{branch}:{branch}")
                        return True
                    except Exception as rebase_err:
                        print(f"Rebase and retry failed: {rebase_err}")
                        return False
            print(f"Push failed: {e}")
            return False
    except Exception as e:
        print(f"Push error: {e}")
        return False


def create_and_checkout_branch(repo: Repo, branch_name: str) -> bool:
    """Create and checkout a new branch.

    Args:
        repo: GitPython Repo object
        branch_name: Name for the new branch

    Returns:
        True if branch was created and checked out.
    """
    try:
        new_branch = repo.create_head(branch_name)
        new_branch.checkout()
        return True
    except Exception as e:
        print(f"Failed to create branch {branch_name}: {e}")
        return False


def checkout_branch(repo: Repo, branch_name: str) -> bool:
    """Checkout an existing branch.

    Args:
        repo: GitPython Repo object
        branch_name: Branch to checkout

    Returns:
        True if checkout was successful.
    """
    try:
        repo.git.checkout(branch_name)
        return True
    except Exception as e:
        print(f"Failed to checkout {branch_name}: {e}")
        return False


def get_random_file_in_repo(repo: Repo, extensions: List[str] = None) -> Optional[str]:
    """Get a random file from the repo matching given extensions.

    Args:
        repo: GitPython Repo object
        extensions: List of file extensions to include (e.g., ['.py', '.md'])

    Returns:
        Relative path to a random file, or None if none found.
    """
    if extensions is None:
        extensions = [".py", ".js", ".ts", ".md"]

    matching_files = []
    for root, dirs, files in os.walk(repo.working_dir):
        dirs[:] = [d for d in dirs if d != ".git"]
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, repo.working_dir)
                matching_files.append(rel_path)

    return random.choice(matching_files) if matching_files else None


def append_to_file(repo: Repo, filepath: str, content: str) -> bool:
    """Append content to a file in the repo.

    Args:
        repo: GitPython Repo object
        filepath: Relative path to file
        content: Content to append

    Returns:
        True if successful.
    """
    try:
        full_path = os.path.join(repo.working_dir, filepath)
        with open(full_path, "a", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"Failed to append to {filepath}: {e}")
        return False


def read_file(repo: Repo, filepath: str) -> str:
    """Read content from a file in the repo.

    Args:
        repo: GitPython Repo object
        filepath: Relative path to file

    Returns:
        File content as string, or empty string if error.
    """
    try:
        full_path = os.path.join(repo.working_dir, filepath)
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""
