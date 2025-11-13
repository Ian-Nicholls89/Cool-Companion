"""Service for checking and managing application updates via git delta downloads."""
import asyncio
import logging
import json
import subprocess
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Update service configuration constants
UPDATE_CHECK_CACHE_FILE = ".update_cache.json"
UPDATE_CHECK_FREQUENCY_HOURS = 24  # Default: check once per day
LAST_UPDATE_FILE = ".last_update"


class UpdateInfo:
    """Information about an available update."""

    def __init__(
        self,
        current_commit: str,
        latest_commit: str,
        commits_behind: int,
        changed_files: List[str],
        commit_messages: str,
        last_update_date: Optional[str] = None
    ):
        self.current_commit = current_commit
        self.latest_commit = latest_commit
        self.commits_behind = commits_behind
        self.changed_files = changed_files
        self.commit_messages = commit_messages
        self.last_update_date = last_update_date

    def has_updates(self) -> bool:
        """Check if there are updates available."""
        return self.commits_behind > 0

    def get_summary(self) -> str:
        """Get human-readable summary of update."""
        if not self.has_updates():
            return "Application is up to date"

        file_count = len(self.changed_files)
        return (
            f"{self.commits_behind} new commit(s) available\n"
            f"{file_count} file(s) will be updated"
        )


class UpdateService:
    """Service for checking and managing git-based delta updates."""

    def __init__(self, settings=None):
        """Initialize update service.

        Args:
            settings: Application settings (optional)
        """
        if settings is None:
            from config.settings import settings as default_settings
            self.settings = default_settings
        else:
            self.settings = settings

        self.app_dir = Path(__file__).parent.parent
        self.cache_file = self.app_dir / UPDATE_CHECK_CACHE_FILE
        self.last_update_file = self.app_dir / LAST_UPDATE_FILE
        self.is_git_repo = (self.app_dir / ".git").exists()

    async def check_for_updates(self, force: bool = False) -> Optional[UpdateInfo]:
        """Check if updates are available using git.

        Args:
            force: Force check even if cache is valid

        Returns:
            UpdateInfo if update available, None otherwise
        """
        # Check if update checking is enabled
        if not self._is_update_check_enabled():
            logger.debug("Update checking is disabled")
            return None

        # Verify this is a git repository
        if not self.is_git_repo:
            logger.warning("Not a git repository - update checking unavailable")
            return None

        # Verify git is installed
        if not await self._has_git_command():
            logger.warning("Git command not available - update checking unavailable")
            return None

        # Check cache unless forced
        if not force and self._is_cache_valid():
            logger.debug("Using cached update check result")
            cached_info = self._load_cached_update_info()
            if cached_info and not cached_info.has_updates():
                return None

        try:
            # Fetch latest changes from remote (only downloads deltas)
            logger.info("Fetching updates from remote repository...")
            fetch_result = await asyncio.to_thread(
                subprocess.run,
                ["git", "fetch", "origin", "--quiet"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=30
            )

            if fetch_result.returncode != 0:
                logger.warning(f"Git fetch failed: {fetch_result.stderr}")
                return None

            # Get current commit SHA
            current_commit = await self._get_current_commit()
            if not current_commit:
                logger.error("Could not determine current commit")
                return None

            # Get upstream commit SHA
            latest_commit = await self._get_upstream_commit()
            if not latest_commit:
                logger.warning("Could not determine upstream commit (no remote configured?)")
                return None

            # Check if we're behind
            commits_behind = await self._get_commits_behind()

            if commits_behind == 0:
                logger.info("Application is up to date")
                update_info = UpdateInfo(
                    current_commit=current_commit[:7],
                    latest_commit=latest_commit[:7],
                    commits_behind=0,
                    changed_files=[],
                    commit_messages="",
                    last_update_date=self._get_last_update_date()
                )
                self._save_cache(update_info)
                return None

            # Get list of changed files
            changed_files = await self._get_changed_files()

            # Get commit messages
            commit_messages = await self._get_commit_log()

            logger.info(f"Update available: {commits_behind} commit(s) behind, {len(changed_files)} file(s) changed")

            update_info = UpdateInfo(
                current_commit=current_commit[:7],
                latest_commit=latest_commit[:7],
                commits_behind=commits_behind,
                changed_files=changed_files,
                commit_messages=commit_messages,
                last_update_date=self._get_last_update_date()
            )

            # Save cache
            self._save_cache(update_info)

            return update_info

        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return None

    async def apply_update(self) -> Tuple[bool, str]:
        """Apply git delta update (only downloads changed files).

        Returns:
            Tuple of (success, message)
        """
        if not self.is_git_repo:
            return (False, "Not a git repository")

        try:
            logger.info("Applying git delta update...")

            # Check for uncommitted changes
            status_result = await asyncio.to_thread(
                subprocess.run,
                ["git", "status", "--porcelain"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=5
            )

            if status_result.stdout.strip():
                # There are uncommitted changes
                logger.warning("Uncommitted changes detected")
                return (
                    False,
                    "You have uncommitted local changes.\n"
                    "Please commit or stash them before updating."
                )

            # Get info before update
            files_to_update = await self._get_changed_files()
            commits_to_apply = await self._get_commits_behind()

            # Pull changes (git will only download file deltas)
            logger.info("Pulling changes from remote...")
            pull_result = await asyncio.to_thread(
                subprocess.run,
                ["git", "pull", "origin", "--rebase", "--quiet"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=60
            )

            if pull_result.returncode != 0:
                error_msg = pull_result.stderr.strip()
                logger.error(f"Git pull failed: {error_msg}")
                return (False, f"Update failed: {error_msg}")

            # Record successful update
            self._save_last_update_info(commits_to_apply, len(files_to_update))

            logger.info(f"Update successful: {commits_to_apply} commit(s), {len(files_to_update)} file(s)")

            return (
                True,
                f"Update successful!\n\n"
                f"Applied {commits_to_apply} commit(s)\n"
                f"Updated {len(files_to_update)} file(s)\n\n"
                f"Please restart the application for changes to take effect."
            )

        except Exception as e:
            logger.error(f"Error applying update: {e}")
            return (False, f"Update error: {str(e)}")

    async def get_update_statistics(self) -> Dict[str, Any]:
        """Get statistics about updates.

        Returns:
            Dictionary with update statistics
        """
        stats = {
            'is_git_repo': self.is_git_repo,
            'git_available': await self._has_git_command(),
            'last_update_date': self._get_last_update_date(),
            'last_check_date': self._get_last_check_date(),
            'current_commit': None,
            'current_branch': None
        }

        if self.is_git_repo:
            stats['current_commit'] = await self._get_current_commit()
            stats['current_branch'] = await self._get_current_branch()

        return stats

    # Private helper methods

    async def _has_git_command(self) -> bool:
        """Check if git command is available."""
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["git", "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    async def _get_current_commit(self) -> Optional[str]:
        """Get current commit SHA."""
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["git", "rev-parse", "HEAD"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.debug(f"Error getting current commit: {e}")
        return None

    async def _get_upstream_commit(self) -> Optional[str]:
        """Get upstream commit SHA."""
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["git", "rev-parse", "@{u}"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.debug(f"Error getting upstream commit: {e}")
        return None

    async def _get_current_branch(self) -> Optional[str]:
        """Get current branch name."""
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.debug(f"Error getting current branch: {e}")
        return None

    async def _get_commits_behind(self) -> int:
        """Get number of commits behind upstream."""
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["git", "rev-list", "--count", "HEAD..@{u}"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except Exception as e:
            logger.debug(f"Error getting commits behind: {e}")
        return 0

    async def _get_changed_files(self) -> List[str]:
        """Get list of files that will change in update."""
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["git", "diff", "--name-status", "HEAD..@{u}"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                return [line for line in lines if line]
        except Exception as e:
            logger.debug(f"Error getting changed files: {e}")
        return []

    async def _get_commit_log(self) -> str:
        """Get commit messages for pending updates."""
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["git", "log", "--oneline", "--decorate", "HEAD..@{u}"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip() or "No commit messages available"
        except Exception as e:
            logger.debug(f"Error getting commit log: {e}")
        return "No commit messages available"

    def _is_update_check_enabled(self) -> bool:
        """Check if update checking is enabled in settings."""
        return getattr(self.settings, 'enable_update_check', True)

    def _is_cache_valid(self) -> bool:
        """Check if update check cache is valid.

        Returns:
            True if cache is valid and recent enough
        """
        if not self.cache_file.exists():
            return False

        try:
            cache_data = self._load_cache()
            if not cache_data:
                return False

            # Check timestamp
            last_check = datetime.fromisoformat(cache_data['timestamp'])
            check_frequency = getattr(
                self.settings,
                'update_check_frequency_hours',
                UPDATE_CHECK_FREQUENCY_HOURS
            )

            if datetime.now() - last_check < timedelta(hours=check_frequency):
                return True

            return False

        except Exception as e:
            logger.debug(f"Error checking cache validity: {e}")
            return False

    def _load_cache(self) -> Optional[Dict[str, Any]]:
        """Load update check cache.

        Returns:
            Cache data dict or None if not available
        """
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.debug(f"Error loading cache: {e}")
        return None

    def _load_cached_update_info(self) -> Optional[UpdateInfo]:
        """Load UpdateInfo from cache.

        Returns:
            UpdateInfo object or None
        """
        try:
            cache_data = self._load_cache()
            if cache_data and 'update_info' in cache_data:
                info = cache_data['update_info']
                return UpdateInfo(
                    current_commit=info['current_commit'],
                    latest_commit=info['latest_commit'],
                    commits_behind=info['commits_behind'],
                    changed_files=info['changed_files'],
                    commit_messages=info['commit_messages'],
                    last_update_date=info.get('last_update_date')
                )
        except Exception as e:
            logger.debug(f"Error loading cached update info: {e}")
        return None

    def _save_cache(self, update_info: Optional[UpdateInfo]) -> None:
        """Save update check cache.

        Args:
            update_info: Update information to cache
        """
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'update_available': update_info.has_updates() if update_info else False,
            }

            if update_info:
                cache_data['update_info'] = {
                    'current_commit': update_info.current_commit,
                    'latest_commit': update_info.latest_commit,
                    'commits_behind': update_info.commits_behind,
                    'changed_files': update_info.changed_files,
                    'commit_messages': update_info.commit_messages,
                    'last_update_date': update_info.last_update_date
                }

            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)

        except Exception as e:
            logger.debug(f"Error saving cache: {e}")

    def _get_last_check_date(self) -> Optional[str]:
        """Get date of last update check."""
        try:
            cache_data = self._load_cache()
            if cache_data and 'timestamp' in cache_data:
                return cache_data['timestamp']
        except Exception:
            pass
        return None

    def _get_last_update_date(self) -> Optional[str]:
        """Get date of last successful update."""
        try:
            if self.last_update_file.exists():
                data = json.loads(self.last_update_file.read_text())
                return data.get('timestamp')
        except Exception:
            pass
        return None

    def _save_last_update_info(self, commits_applied: int, files_updated: int) -> None:
        """Save information about last successful update.

        Args:
            commits_applied: Number of commits applied
            files_updated: Number of files updated
        """
        try:
            data = {
                'timestamp': datetime.now().isoformat(),
                'commits_applied': commits_applied,
                'files_updated': files_updated
            }

            with open(self.last_update_file, 'w') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.debug(f"Error saving last update info: {e}")
