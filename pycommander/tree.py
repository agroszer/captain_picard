"""Directory Tree View engine supporting collapsible hierarchical filesystem traversal."""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import List, Optional
from pycommander.vfs import FileStat, VFS


@dataclass
class TreeNode:
    """Represents a collapsible node in the directory tree view."""
    path: str
    name: str
    is_dir: bool = True
    is_expanded: bool = False
    children: List[TreeNode] = field(default_factory=list)
    depth: int = 0
    parent: Optional[TreeNode] = None

    def toggle(self, vfs: VFS) -> None:
        """Toggles expanded state, loading children if expanding."""
        if not self.is_dir:
            return
        self.is_expanded = not self.is_expanded
        if self.is_expanded and not self.children:
            self.load_children(vfs)

    def load_children(self, vfs: VFS) -> None:
        self.children.clear()
        try:
            entries = vfs.list_dir(self.path)
            for e in entries:
                if e.is_dir:
                    child = TreeNode(
                        path=e.path,
                        name=e.name,
                        is_dir=True,
                        depth=self.depth + 1,
                        parent=self,
                    )
                    self.children.append(child)
        except Exception:
            pass
        self.children.sort(key=lambda c: c.name.lower())

    def flatten(self) -> List[TreeNode]:
        """Flattens currently expanded visible nodes into a single linear list for rendering."""
        res = [self]
        if self.is_expanded:
            for c in self.children:
                res.extend(c.flatten())
        return res


class DirectoryTree:
    """Hierarchical Directory Tree View controller."""

    def __init__(self, root_path: str, vfs: VFS):
        self.vfs = vfs
        self.root_path = self.vfs.normalize_path(root_path)
        self.root = TreeNode(
            path=self.root_path,
            name=os.path.basename(self.root_path) or self.root_path,
            is_dir=True,
            is_expanded=False,
            depth=0,
        )
        self.cursor_index: int = 0

    def get_visible_nodes(self) -> List[TreeNode]:
        return self.root.flatten()

    def get_selected_node(self) -> Optional[TreeNode]:
        nodes = self.get_visible_nodes()
        if 0 <= self.cursor_index < len(nodes):
            return nodes[self.cursor_index]
        return None

    def move_cursor_up(self) -> None:
        if self.cursor_index > 0:
            self.cursor_index -= 1

    def move_cursor_down(self) -> None:
        nodes = self.get_visible_nodes()
        if self.cursor_index < len(nodes) - 1:
            self.cursor_index += 1

    def toggle_current(self) -> None:
        node = self.get_selected_node()
        if node and node.is_dir:
            node.toggle(self.vfs)

    def collapse_or_parent(self) -> None:
        node = self.get_selected_node()
        if not node:
            return
        if node.is_expanded:
            node.is_expanded = False
        elif node.parent:
            # Move cursor to parent
            nodes = self.get_visible_nodes()
            try:
                self.cursor_index = nodes.index(node.parent)
            except ValueError:
                pass
