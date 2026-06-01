"""Hot Reload — Watch .ai files and reload on changes.

Monitors the agents/, pipelines/, and plugins/ directories for changes
and automatically reloads affected components.

Usage:
    from ailang_integration.runtime.hot_reload import HotReloader

    reloader = HotReloader()
    reloader.start()  # Background thread watches for changes
    reloader.stop()
"""
from __future__ import annotations
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class FileWatcher:
    """Watches files for modifications by polling mtimes."""

    def __init__(self, directories: List[Path], pattern: str = "*.ai"):
        self.directories = directories
        self.pattern = pattern
        self._mtimes: Dict[str, float] = {}
        self._scan_initial()

    def _scan_initial(self) -> None:
        """Record initial file mtimes."""
        for d in self.directories:
            if not d.exists():
                continue
            for f in d.glob(self.pattern):
                try:
                    self._mtimes[str(f)] = f.stat().st_mtime
                except OSError:
                    pass

    def check_changes(self) -> Dict[str, str]:
        """Check for changed, added, or deleted files.

        Returns dict of {filepath: change_type} where change_type
        is 'modified', 'added', or 'deleted'.
        """
        changes: Dict[str, str] = {}
        current_files: Set[str] = set()

        for d in self.directories:
            if not d.exists():
                continue
            for f in d.glob(self.pattern):
                path = str(f)
                current_files.add(path)
                try:
                    mtime = f.stat().st_mtime
                except OSError:
                    continue

                if path not in self._mtimes:
                    changes[path] = "added"
                    self._mtimes[path] = mtime
                elif mtime > self._mtimes[path]:
                    changes[path] = "modified"
                    self._mtimes[path] = mtime

        # Check for deleted files
        for path in list(self._mtimes.keys()):
            if path not in current_files:
                changes[path] = "deleted"
                del self._mtimes[path]

        return changes


class HotReloader:
    """Watches .ai files and reloads components on change.

    Runs a background thread that polls for file changes every
    `poll_interval` seconds. When changes are detected, it reloads
    the appropriate component (bridge, plugins, or pipelines).
    """

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        poll_interval: float = 2.0,
        on_reload: Optional[Callable[[Dict[str, str]], None]] = None,
    ):
        base = base_dir or Path(__file__).parent.parent
        self.directories = [
            base / "agents",
            base / "pipelines",
            base / "plugins",
        ]
        self.poll_interval = poll_interval
        self.on_reload = on_reload
        self._watcher = FileWatcher(self.directories)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._reload_count = 0

    def start(self) -> None:
        """Start watching for changes in a background thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("Hot reloader already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._watch_loop,
            daemon=True,
            name="ailang-hot-reload",
        )
        self._thread.start()
        logger.info(f"Hot reloader started (polling every {self.poll_interval}s)")

    def stop(self) -> None:
        """Stop the background watcher."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Hot reloader stopped")

    def _watch_loop(self) -> None:
        """Main polling loop."""
        while not self._stop_event.is_set():
            try:
                changes = self._watcher.check_changes()
                if changes:
                    self._handle_changes(changes)
            except Exception as e:
                logger.error(f"Hot reload watch error: {e}")

            self._stop_event.wait(timeout=self.poll_interval)

    def _handle_changes(self, changes: Dict[str, str]) -> None:
        """Handle detected file changes."""
        self._reload_count += 1

        for path, change_type in changes.items():
            logger.info(f"Hot reload: {change_type} {path}")

        # Determine what to reload
        reload_agents = any("agents" in p for p in changes)
        reload_pipelines = any("pipelines" in p for p in changes)
        reload_plugins = any("plugins" in p for p in changes)

        try:
            if reload_agents or reload_pipelines:
                from .bridge import get_bridge
                get_bridge().reload()
                logger.info("Bridge reloaded (agents + pipelines)")

            if reload_pipelines:
                from .pipeline_runner import get_pipeline_runner
                get_pipeline_runner().reload()
                logger.info("Pipeline runner reloaded")

            if reload_plugins:
                from .plugin_loader import get_plugin_loader
                get_plugin_loader().reload_all()
                logger.info("Plugins reloaded")

        except Exception as e:
            logger.error(f"Hot reload failed: {e}")

        # Call user callback
        if self.on_reload:
            try:
                self.on_reload(changes)
            except Exception as e:
                logger.error(f"Hot reload callback failed: {e}")

    @property
    def reload_count(self) -> int:
        return self._reload_count

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()


# Singleton
_reloader: Optional[HotReloader] = None

def get_hot_reloader(**kwargs) -> HotReloader:
    global _reloader
    if _reloader is None:
        _reloader = HotReloader(**kwargs)
    return _reloader
