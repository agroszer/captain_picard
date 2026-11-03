"""Dual-Pane Layout Engine and Pane State Management."""

from __future__ import annotations
import enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from pycommander.quick_view import FileInfoGenerator, QuickViewer
from pycommander.tabs import FolderTab
from pycommander.tree import DirectoryTree
from pycommander.vfs import FileStat, LocalVFS, VFS


class PaneMode(enum.Enum):
    FILE_LIST = "file_list"
    TREE = "tree"
    QUICK_VIEW = "quick_view"
    INFO = "info"


class SplitOrientation(enum.Enum):
    VERTICAL = "vertical"      # Side-by-side (orthodox default)
    HORIZONTAL = "horizontal"  # Stacked top / bottom


class ListingFormat(enum.Enum):
    FULL = "full"            # Name, Size, Date, Perms
    BRIEF = "brief"          # Multi-column or simple name only
    LONG = "long"            # Name, Size, Date, Perms, Owner, Group
    PERMISSIONS = "perms"    # Name, Perms, Owner, Group
    CUSTOM = "custom"        # User defined columns


@dataclass
class Pane:
    """Represents one of the two panes in the orthodox file manager."""
    id: str  # "left" or "right"
    mode: PaneMode = PaneMode.FILE_LIST
    listing_format: ListingFormat = ListingFormat.FULL
    tabs: List[FolderTab] = field(default_factory=list)
    active_tab_idx: int = 0
    tree_view: Optional[DirectoryTree] = None
    quick_filter_pattern: str = ""
    is_quick_filter_active: bool = False

    def __post_init__(self):
        if not self.tabs:
            vfs = LocalVFS()
            self.tabs.append(FolderTab(path=".", vfs=vfs))

    @property
    def active_tab(self) -> FolderTab:
        if 0 <= self.active_tab_idx < len(self.tabs):
            return self.tabs[self.active_tab_idx]
        return self.tabs[0]

    def new_tab(self, path: Optional[str] = None, vfs: Optional[VFS] = None) -> FolderTab:
        cur = self.active_tab
        target_path = path or cur.path
        target_vfs = vfs or cur.vfs
        tab = FolderTab(path=target_path, vfs=target_vfs)
        self.tabs.append(tab)
        self.active_tab_idx = len(self.tabs) - 1
        return tab

    def duplicate_tab(self) -> FolderTab:
        dup = self.active_tab.duplicate()
        self.tabs.append(dup)
        self.active_tab_idx = len(self.tabs) - 1
        return dup

    def close_tab(self) -> bool:
        if len(self.tabs) <= 1:
            return False
        self.tabs.pop(self.active_tab_idx)
        if self.active_tab_idx >= len(self.tabs):
            self.active_tab_idx = len(self.tabs) - 1
        return True

    def next_tab(self) -> None:
        self.active_tab_idx = (self.active_tab_idx + 1) % len(self.tabs)

    def prev_tab(self) -> None:
        self.active_tab_idx = (self.active_tab_idx - 1) % len(self.tabs)

    def toggle_tab_lock(self) -> bool:
        tab = self.active_tab
        tab.is_locked = not tab.is_locked
        return tab.is_locked

    def get_items(self) -> List[FileStat]:
        """Returns directory entries filtered by quick filter if active."""
        tab = self.active_tab
        try:
            items = tab.vfs.list_dir(tab.path)
        except Exception:
            return []

        if self.is_quick_filter_active and self.quick_filter_pattern:
            patt = self.quick_filter_pattern.lower()
            items = [it for it in items if patt in it.name.lower()]

        return items

    def get_current_item(self) -> Optional[FileStat]:
        items = self.get_items()
        idx = self.active_tab.cursor_index
        if 0 <= idx < len(items):
            return items[idx]
        return None

    def move_cursor_up(self) -> None:
        tab = self.active_tab
        if tab.cursor_index > 0:
            tab.cursor_index -= 1

    def move_cursor_down(self) -> None:
        tab = self.active_tab
        items = self.get_items()
        if tab.cursor_index < len(items) - 1:
            tab.cursor_index += 1

    def move_cursor_home(self) -> None:
        self.active_tab.cursor_index = 0

    def move_cursor_end(self) -> None:
        items = self.get_items()
        if items:
            self.active_tab.cursor_index = len(items) - 1


class DualPaneManager:
    """Coordinates active/inactive panes, layout orientation, and dual-pane operations."""

    def __init__(self, initial_path_left: str = ".", initial_path_right: str = "."):
        vfs = LocalVFS()
        self.left = Pane("left", tabs=[FolderTab(path=initial_path_left, vfs=vfs)])
        self.right = Pane("right", tabs=[FolderTab(path=initial_path_right, vfs=vfs)])
        self.active_pane_id: str = "left"
        self.orientation: SplitOrientation = SplitOrientation.VERTICAL
        self.comparison_mode: bool = False
        self.comparison_diffs: Dict[str, str] = {}  # "left_only", "right_only", "diff_size", "diff_time"

    @property
    def active_pane(self) -> Pane:
        return self.left if self.active_pane_id == "left" else self.right

    @property
    def target_pane(self) -> Pane:
        return self.right if self.active_pane_id == "left" else self.left

    def switch_pane(self) -> None:
        self.active_pane_id = "right" if self.active_pane_id == "left" else "left"

    def swap_panes(self) -> None:
        self.left.tabs, self.right.tabs = self.right.tabs, self.left.tabs
        self.left.mode, self.right.mode = self.right.mode, self.left.mode

    def toggle_split_orientation(self) -> SplitOrientation:
        self.orientation = (
            SplitOrientation.HORIZONTAL
            if self.orientation == SplitOrientation.VERTICAL
            else SplitOrientation.VERTICAL
        )
        return self.orientation

    def toggle_quick_view(self) -> PaneMode:
        """Toggles Quick View in the opposite (inactive) pane."""
        target = self.target_pane
        if target.mode == PaneMode.QUICK_VIEW:
            target.mode = PaneMode.FILE_LIST
        else:
            target.mode = PaneMode.QUICK_VIEW
        return target.mode

    def toggle_info_panel(self) -> PaneMode:
        """Toggles File Info in the opposite (inactive) pane."""
        target = self.target_pane
        if target.mode == PaneMode.INFO:
            target.mode = PaneMode.FILE_LIST
        else:
            target.mode = PaneMode.INFO
        return target.mode

    def toggle_tree_view(self) -> PaneMode:
        active = self.active_pane
        if active.mode == PaneMode.TREE:
            active.mode = PaneMode.FILE_LIST
        else:
            active.mode = PaneMode.TREE
            active.tree_view = DirectoryTree(active.active_tab.path, active.active_tab.vfs)
        return active.mode

    def compare_directories(self) -> Dict[str, str]:
        """
        Dual-Pane Comparison Mode:
        Compares active tabs of left and right panes and tags differences:
        'diff_size', 'diff_time', 'left_only', 'right_only'.
        """
        self.comparison_mode = True
        self.comparison_diffs.clear()

        left_items = {it.name: it for it in self.left.get_items()}
        right_items = {it.name: it for it in self.right.get_items()}

        all_names = set(left_items.keys()) | set(right_items.keys())
        for name in all_names:
            in_left = name in left_items
            in_right = name in right_items
            if in_left and not in_right:
                self.comparison_diffs[f"left:{name}"] = "left_only"
            elif in_right and not in_left:
                self.comparison_diffs[f"right:{name}"] = "right_only"
            else:
                l_stat = left_items[name]
                r_stat = right_items[name]
                if l_stat.size != r_stat.size:
                    self.comparison_diffs[f"left:{name}"] = "diff_size"
                    self.comparison_diffs[f"right:{name}"] = "diff_size"
                elif abs(l_stat.mtime - r_stat.mtime) > 1.0:
                    self.comparison_diffs[f"left:{name}"] = "diff_time"
                    self.comparison_diffs[f"right:{name}"] = "diff_time"
                else:
                    self.comparison_diffs[f"left:{name}"] = "identical"
                    self.comparison_diffs[f"right:{name}"] = "identical"

        return self.comparison_diffs
