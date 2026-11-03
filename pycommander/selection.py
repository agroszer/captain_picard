"""Selection engine supporting wildcards, regex, invert, restore, and extension grouping."""

from __future__ import annotations
import fnmatch
import re
from typing import List, Optional, Set
from pycommander.vfs import FileStat


class SelectionManager:
    """Manages file selection states for a pane/tab."""

    def __init__(self):
        self.selected_paths: Set[str] = set()
        self.previous_selection: Set[str] = set()

    def is_selected(self, path: str) -> bool:
        return path in self.selected_paths

    def toggle(self, path: str) -> bool:
        """Toggles single path selection."""
        self._save_previous()
        if path in self.selected_paths:
            self.selected_paths.remove(path)
            return False
        else:
            self.selected_paths.add(path)
            return True

    def select(self, path: str) -> None:
        self._save_previous()
        self.selected_paths.add(path)

    def deselect(self, path: str) -> None:
        self._save_previous()
        self.selected_paths.discard(path)

    def select_all(self, items: List[FileStat]) -> None:
        self._save_previous()
        for it in items:
            self.selected_paths.add(it.path)

    def deselect_all(self) -> None:
        self._save_previous()
        self.selected_paths.clear()

    def invert(self, items: List[FileStat]) -> None:
        """Inverts the current selection for visible items."""
        self._save_previous()
        new_set = set()
        for it in items:
            if it.path not in self.selected_paths:
                new_set.add(it.path)
        self.selected_paths = new_set

    def restore_previous(self) -> None:
        """Restores the last selection state."""
        current = set(self.selected_paths)
        self.selected_paths = set(self.previous_selection)
        self.previous_selection = current

    def select_by_wildcard(self, pattern: str, items: List[FileStat], is_select: bool = True) -> int:
        """
        Selects or deselects files using wildcards (e.g., '*.*', '*.ts;*.tsx', or regex 're:...').
        """
        self._save_previous()
        patterns = [p.strip() for p in pattern.split(";") if p.strip()]
        matched_count = 0

        for it in items:
            matches = False
            for pat in patterns:
                if pat.startswith("re:"):
                    regex_pat = pat[3:]
                    if re.search(regex_pat, it.name, re.IGNORECASE):
                        matches = True
                        break
                else:
                    if fnmatch.fnmatch(it.name.lower(), pat.lower()):
                        matches = True
                        break
            if matches:
                if is_select:
                    self.selected_paths.add(it.path)
                else:
                    self.selected_paths.discard(it.path)
                matched_count += 1

        return matched_count

    def select_all_same_extension(self, current_item: Optional[FileStat], items: List[FileStat]) -> int:
        """Selects all files that share the same extension as current_item."""
        if not current_item or current_item.is_dir:
            return 0
        ext = current_item.extension
        if not ext:
            pattern = "*."
        else:
            pattern = f"*.{ext}"
        return self.select_by_wildcard(pattern, items, is_select=True)

    def _save_previous(self) -> None:
        self.previous_selection = set(self.selected_paths)
