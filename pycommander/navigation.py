"""Navigation engine: Directory Bookmarks, Breadcrumb parser, and Mount/Volume switcher."""

from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pycommander.vfs import LocalVFS, VFS


@dataclass
class Bookmark:
    """Represents a saved directory bookmark / hotlist entry."""
    title: str
    path: str
    hotkey: Optional[str] = None
    vfs_type: str = "local"


class BookmarkManager:
    """Manages directory bookmarks (Ctrl+D / hotlist)."""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.bookmarks: List[Bookmark] = []
        self._load_defaults()

    def _load_defaults(self) -> None:
        home = os.path.expanduser("~")
        self.bookmarks = [
            Bookmark(title="Home Directory", path=home, hotkey="~"),
            Bookmark(title="Root Directory", path="/", hotkey="/"),
            Bookmark(title="Current Directory", path=".", hotkey="."),
        ]
        if os.path.exists("/tmp"):
            self.bookmarks.append(Bookmark(title="Temporary Files", path="/tmp", hotkey="t"))

    def add_bookmark(self, title: str, path: str, hotkey: Optional[str] = None) -> Bookmark:
        bm = Bookmark(title=title, path=path, hotkey=hotkey)
        self.bookmarks.append(bm)
        return bm

    def remove_bookmark(self, index: int) -> bool:
        if 0 <= index < len(self.bookmarks):
            self.bookmarks.pop(index)
            return True
        return False

    def get_by_hotkey(self, hotkey: str) -> Optional[Bookmark]:
        for b in self.bookmarks:
            if b.hotkey == hotkey:
                return b
        return None


class BreadcrumbNavigator:
    """Parses and generates clickable breadcrumbs from a path."""

    @staticmethod
    def parse_breadcrumbs(path: str) -> List[Tuple[str, str]]:
        """
        Returns list of (label, target_path) tuples.
        Example: '/home/user/docs' -> [('/', '/'), ('home', '/home'), ('user', '/home/user'), ('docs', '/home/user/docs')]
        """
        norm = os.path.normpath(path)
        if norm in ("/", ""):
            return [("/", "/")]

        parts = [p for p in norm.split(os.sep) if p]
        res = [("/", "/")]
        accum = ""
        for p in parts:
            accum = os.path.join(accum, p)
            target = "/" + accum.lstrip("/")
            res.append((p, target))
        return res


class VolumeManager:
    """Enumerates mounted drives, volumes, and standard mountpoints."""

    @staticmethod
    def get_mounts() -> List[Dict[str, str]]:
        mounts = []
        # Check standard Linux/Unix mounts via /proc/mounts or mountpoint check
        if os.path.exists("/proc/mounts"):
            try:
                with open("/proc/mounts", "r") as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) >= 3:
                            dev, mnt, fstype = parts[0], parts[1], parts[2]
                            if fstype in ("ext4", "btrfs", "xfs", "vfat", "ntfs", "tmpfs", "overlay", "apfs"):
                                mounts.append({
                                    "device": dev,
                                    "mountpoint": mnt,
                                    "fstype": fstype,
                                })
            except Exception:
                pass

        if not mounts:
            # Fallback for systems without /proc/mounts
            mounts = [
                {"device": "root", "mountpoint": "/", "fstype": "rootfs"},
                {"device": "home", "mountpoint": os.path.expanduser("~"), "fstype": "user"},
            ]
        return mounts
