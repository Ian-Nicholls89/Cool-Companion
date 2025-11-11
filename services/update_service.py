"""Service for checking and managing application updates."""
import asyncio
import logging
import os
import json
import subprocess
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, TYPE_CHECKING
from pathlib import Path
import requests

if TYPE_CHECKING:
    from config.settings import Settings

logger = logging.getLogger(__name__)

# Update service configuration constants
UPDATE_CHECK_CACHE_FILE = ".update_cache.json"
UPDATE_CHECK_FREQUENCY_HOURS = 24  # Default: check once per day
GITHUB_API_RELEASES_URL = "https://api.github.com/repos/{owner}/{repo}/releases/latest"
GITHUB_REPO_OWNER = "anthropics"  # TODO: Update with actual repo owner
GITHUB_REPO_NAME = "cool-companion"  # TODO: Update with actual repo name


class UpdateInfo:
    """Information about an available update."""

    def __init__(
        self,
        current_version: str,
        latest_version: str,
        release_url: str,
        release_notes: str,
        published_at: str,
        download_url: Optional[str] = None
    ):
        self.current_version = current_version
        self.latest_version = latest_version
        self.release_url = release_url
        self.release_notes = release_notes
        self.published_at = published_at
        self.download_url = download_url

    def is_newer(self) -> bool:
        """Check if latest version is newer than current version."""
        try:
            # Simple version comparison (assumes semantic versioning: v1.2.3)
            current = self._parse_version(self.current_version)
            latest = self._parse_version(self.latest_version)
            return latest > current
        except Exception as e:
            logger.error(f"Error comparing versions: {e}")
            return False

    @staticmethod
    def _parse_version(version_str: str) -> Tuple[int, int, int]:
        """Parse version string into tuple for comparison."""
        # Remove 'v' prefix if present
        version_str = version_str.lstrip('v')
        parts = version_str.split('.')

        # Ensure we have at least 3 parts (major, minor, patch)
        while len(parts) < 3:
            parts.append('0')

        try:
            return (int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            return (0, 0, 0)


class UpdateService:
    """Service for checking and managing application updates."""

    def __init__(self, settings: Optional['Settings'] = None):
        """Initialize update service.

        Args:
            settings: Application settings
        """
        if settings is None:
            from config.settings import settings as default_settings
            self.settings = default_settings
        else:
            self.settings = settings

        self.app_dir = Path(__file__).parent.parent
        self.cache_file = self.app_dir / UPDATE_CHECK_CACHE_FILE
        self.is_git_repo = (self.app_dir / ".git").exists()

    def get_current_version(self) -> str:
        """Get current application version.

        Returns:
            Version string (e.g., "v1.0.0" or "dev")
        """
        # Try to get version from git tag if running from git repo
        if self.is_git_repo:
            try:
                result = subprocess.run(
                    ["git", "describe", "--tags", "--abbrev=0"],
                    cwd=self.app_dir,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return result.stdout.strip()
            except Exception as e:
                logger.debug(f"Could not get version from git: {e}")

        # Try to read from VERSION file
        version_file = self.app_dir / "VERSION"
        if version_file.exists():
            try:
                return version_file.read_text().strip()
            except Exception as e:
                logger.debug(f"Could not read VERSION file: {e}")

        # Fallback to development version
        return "dev"

    async def check_for_updates(self, force: bool = False) -> Optional[UpdateInfo]:
        """Check if updates are available.

        Args:
            force: Force check even if cache is valid

        Returns:
            UpdateInfo if update available, None otherwise
        """
        # Check if update checking is enabled
        if not self._is_update_check_enabled():
            logger.debug("Update checking is disabled")
            return None

        # Check cache unless forced
        if not force and self._is_cache_valid():
            logger.debug("Using cached update check result")
            cached_info = self._load_cache()
            if cached_info and not cached_info.get('update_available'):
                return None

        try:
            # Get current version
            current_version = self.get_current_version()

            # Check git status if in git repo
            if self.is_git_repo:
                git_update = await self._check_git_updates()
                if git_update:
                    return git_update

            # Check GitHub releases
            github_update = await self._check_github_releases(current_version)

            # Save cache
            self._save_cache(github_update)

            return github_update

        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return None

    async def _check_github_releases(self, current_version: str) -> Optional[UpdateInfo]:
        """Check GitHub releases for updates.

        Args:
            current_version: Current version string

        Returns:
            UpdateInfo if update available, None otherwise
        """
        try:
            url = GITHUB_API_RELEASES_URL.format(
                owner=GITHUB_REPO_OWNER,
                repo=GITHUB_REPO_NAME
            )

            # Make request in thread to avoid blocking
            response = await asyncio.to_thread(
                requests.get,
                url,
                timeout=self.settings.api_timeout,
                headers={"Accept": "application/vnd.github.v3+json"}
            )

            if response.status_code != 200:
                logger.warning(f"GitHub API returned status {response.status_code}")
                return None

            data = response.json()

            # Extract release information
            latest_version = data.get('tag_name', '')
            release_url = data.get('html_url', '')
            release_notes = data.get('body', 'No release notes available.')
            published_at = data.get('published_at', '')

            # Get download URL for appropriate asset
            download_url = None
            for asset in data.get('assets', []):
                # Look for zip or tar.gz files
                if asset['name'].endswith(('.zip', '.tar.gz')):
                    download_url = asset['browser_download_url']
                    break

            # Create update info
            update_info = UpdateInfo(
                current_version=current_version,
                latest_version=latest_version,
                release_url=release_url,
                release_notes=release_notes,
                published_at=published_at,
                download_url=download_url
            )

            # Check if update is available
            if update_info.is_newer():
                logger.info(f"Update available: {latest_version} (current: {current_version})")
                return update_info
            else:
                logger.debug(f"No update available (current: {current_version}, latest: {latest_version})")
                return None

        except Exception as e:
            logger.error(f"Error checking GitHub releases: {e}")
            return None

    async def _check_git_updates(self) -> Optional[UpdateInfo]:
        """Check for updates via git (if running from git repo).

        Returns:
            UpdateInfo if update available, None otherwise
        """
        try:
            # Fetch latest changes
            result = await asyncio.to_thread(
                subprocess.run,
                ["git", "fetch", "origin"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                logger.warning(f"Git fetch failed: {result.stderr}")
                return None

            # Check if local is behind remote
            result = await asyncio.to_thread(
                subprocess.run,
                ["git", "rev-list", "--count", "HEAD..@{u}"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                logger.debug("Could not check git status (no upstream configured?)")
                return None

            commits_behind = int(result.stdout.strip())

            if commits_behind > 0:
                # Get current commit
                current_commit = subprocess.run(
                    ["git", "rev-parse", "--short", "HEAD"],
                    cwd=self.app_dir,
                    capture_output=True,
                    text=True,
                    timeout=5
                ).stdout.strip()

                # Get latest commit
                latest_commit = subprocess.run(
                    ["git", "rev-parse", "--short", "@{u}"],
                    cwd=self.app_dir,
                    capture_output=True,
                    text=True,
                    timeout=5
                ).stdout.strip()

                # Get commit messages
                commit_log = subprocess.run(
                    ["git", "log", "--oneline", f"HEAD..@{{u}}"],
                    cwd=self.app_dir,
                    capture_output=True,
                    text=True,
                    timeout=5
                ).stdout.strip()

                logger.info(f"Git update available: {commits_behind} commit(s) behind")

                return UpdateInfo(
                    current_version=current_commit,
                    latest_version=latest_commit,
                    release_url="",  # Not applicable for git
                    release_notes=f"Commits:\n{commit_log}",
                    published_at="",
                    download_url=None
                )

            return None

        except Exception as e:
            logger.debug(f"Could not check git updates: {e}")
            return None

    async def apply_git_update(self) -> bool:
        """Apply update via git pull.

        Returns:
            True if successful, False otherwise
        """
        if not self.is_git_repo:
            logger.error("Cannot apply git update: not a git repository")
            return False

        try:
            # Pull latest changes
            result = await asyncio.to_thread(
                subprocess.run,
                ["git", "pull", "origin"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info("Git update applied successfully")
                return True
            else:
                logger.error(f"Git pull failed: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error applying git update: {e}")
            return False

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

    def _save_cache(self, update_info: Optional[UpdateInfo]) -> None:
        """Save update check cache.

        Args:
            update_info: Update information to cache
        """
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'update_available': update_info is not None,
            }

            if update_info:
                cache_data['latest_version'] = update_info.latest_version
                cache_data['release_url'] = update_info.release_url

            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)

        except Exception as e:
            logger.debug(f"Error saving cache: {e}")
