"""Folder Tabs implementation supporting locking, duplicate handling, and path history."""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import List, Optional
from pycommander.vfs import FileStat, LocalVFS, VFS


@dataclass
class FolderTab:
    """Represents a single tab within a pane."""
    path: str
    vfs: VFS
    title: Optional[str] = None
    is_locked: bool = False
    history: List[str] = field(default_factory=list)
    history_idx: int = -1
    cursor_index: int = 0
    scroll_offset: int = 0
    selected_paths: set = field(default_factory=set)

    def __post_init__(self):
        self.path = self.vfs.normalize_path(self.path)
        if not self.history:
            self.history = [self.path]
            self.history_idx = 0
        if not self.title:
            self.title = os.path.basename(self.path) or self.path

    def navigate_to(self, new_path: str, force: bool = False) -> bool:
        """Navigates to new path unless tab is locked."""
        if self.is_locked and not force:
            return False

        norm = self.vfs.normalize_path(new_path)
        if self.history_idx >= 0 and self.history_idx < len(self.history):
            if self.history[self.history_idx] == norm:
                return True

        # Truncate forward history and push new path
        self.history = self.history[: self.history_idx + 1]
        self.history.append(norm)
        self.history_idx = len(self.history) - 1
        self.path = norm
        self.title = os.path.basename(norm) or norm
        self.cursor_index = 0
        self.scroll_offset = 0
        self.selected_paths.clear()
        return True

    def can_go_back(self) -> bool:
        return self.history_idx > 0

    def can_go_forward(self) -> bool:
        return self.history_idx < len(self.history) - 1

    def go_back(self) -> bool:
        if self.can_go_back():
            self.history_idx -= 1
            self.path = self.history[self.history_idx]
            self.title = os.path.basename(self.path) or self.path
            self.cursor_index = 0
            self.scroll_offset = 0
            return True
        return False

    def go_forward(self) -> bool:
        if self.can_go_forward():
            self.history_idx += 1
            self.path = self.history[self.history_idx]
            self.title = os.path.basename(self.path) or self.path
            self.cursor_index = 0
            self.scroll_offset = 0
            return True
        return False

    def duplicate(self) -> FolderTab:
        """Creates a duplicated tab instance."""
        dup = FolderTab(
            path=self.path,
            vfs=self.vfs,
            title=self.title,
            is_locked=False,  # Duplicate starts unlocked
            cursor_index=self.cursor_index,
            scroll_offset=self.scroll_offset,
        )
        dup.history = list(self.history)
        dup.history_idx = self.history_idx
        return dup
