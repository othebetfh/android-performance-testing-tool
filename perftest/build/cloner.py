"""Git repository cloning and checkout operations."""

import shutil
from pathlib import Path
from typing import Optional

from git import Repo
from git.exc import GitCommandError

from perftest.logger import get_logger, mask_secret
from perftest.utils.exceptions import CloneError

logger = get_logger(__name__)


def clone_repository(
    repo_url: str,
    token: str,
    target_dir: Path,
    commit: Optional[str] = None,
    branch: Optional[str] = None
) -> Repo:
    """
    Clone a git repository (full clone) and checkout a specific commit.

    Args:
        repo_url: Repository URL (https format)
        token: GitHub Personal Access Token
        target_dir: Directory to clone into
        commit: Optional commit hash to checkout
        branch: Optional branch name to clone (defaults to repo default branch)

    Returns:
        Repo: GitPython Repo object

    Raises:
        CloneError: If cloning or checkout fails
    """
    # Remove target directory if it exists
    if target_dir.exists():
        logger.debug(f"Removing existing directory: {target_dir}")
        shutil.rmtree(target_dir)

    # Create parent directory
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    # Inject token into URL for authentication
    auth_url = repo_url.replace('https://', f'https://{token}@')
    logger.info(f"Cloning repository: {repo_url}")
    if branch:
        logger.info(f"  Branch: {branch}")
    logger.debug(f"Using token: {mask_secret(token)}")
    logger.debug(f"Target directory: {target_dir}")

    try:
        # Clone repository (full clone, not shallow)
        if branch:
            # Clone specific branch
            logger.info(f"Cloning branch: {branch}")
            repo = Repo.clone_from(
                auth_url,
                target_dir,
                branch=branch,
                single_branch=True  # Only clone the specific branch
            )
        else:
            # Clone default branch
            logger.info("Cloning default branch")
            repo = Repo.clone_from(
                auth_url,
                target_dir
            )

        # Checkout specific commit if provided
        if commit:
            logger.info(f"Checking out commit: {commit}")
            repo.git.checkout(commit)

        # Log repository info
        try:
            current_commit = repo.head.commit.hexsha
            current_branch = repo.active_branch.name if not repo.head.is_detached else "detached HEAD"
            logger.info(f"Repository cloned successfully")
            logger.info(f"  Branch: {current_branch}")
            logger.info(f"  Commit: {current_commit[:8]}")
        except Exception as e:
            logger.debug(f"Could not get repository info: {e}")

        return repo

    except GitCommandError as e:
        error_msg = str(e).replace(token, '***')  # Mask token in error messages
        raise CloneError(f"Git operation failed: {error_msg}")
    except Exception as e:
        error_msg = str(e).replace(token, '***')  # Mask token in error messages
        raise CloneError(f"Failed to clone repository: {error_msg}")


def get_repository_info(repo: Repo) -> dict:
    """
    Get information about the current repository state.

    Args:
        repo: GitPython Repo object

    Returns:
        dict: Repository information
    """
    try:
        info = {
            'commit': repo.head.commit.hexsha,
            'short_commit': repo.head.commit.hexsha[:8],
            'message': repo.head.commit.message.strip(),
            'author': str(repo.head.commit.author),
            'date': repo.head.commit.committed_datetime.isoformat(),
            'is_detached': repo.head.is_detached,
        }

        if not repo.head.is_detached:
            info['branch'] = repo.active_branch.name
        else:
            info['branch'] = 'detached HEAD'

        return info
    except Exception as e:
        logger.warning(f"Could not get repository info: {e}")
        return {}


def cleanup_clone(target_dir: Path) -> None:
    """
    Clean up cloned repository directory.

    Args:
        target_dir: Directory to remove
    """
    if target_dir.exists():
        logger.debug(f"Cleaning up directory: {target_dir}")
        try:
            shutil.rmtree(target_dir)
        except Exception as e:
            logger.warning(f"Failed to cleanup directory {target_dir}: {e}")
