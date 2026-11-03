"""Directory Synchronization engine and Side-by-Side File Diff & Merge tool."""

from __future__ import annotations
import difflib
import enum
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from pycommander.ops import FileOperations, OverwritePolicy
from pycommander.vfs import FileStat, VFS


class SyncDirection(enum.Enum):
    TWO_WAY = "two_way"            # Sync changes bidirectionally
    LEFT_TO_RIGHT = "left_to_right"  # Mirror Left -> Right
    RIGHT_TO_LEFT = "right_to_left"  # Mirror Right -> Left


class SyncAction(enum.Enum):
    COPY_TO_RIGHT = "->"
    COPY_TO_LEFT = "<-"
    DELETE_RIGHT = "X>"
    DELETE_LEFT = "<X"
    IDENTICAL = "=="
    CONFLICT = "!!"


@dataclass
class SyncItem:
    rel_path: str
    left_stat: Optional[FileStat] = None
    right_stat: Optional[FileStat] = None
    action: SyncAction = SyncAction.IDENTICAL
    reason: str = ""


class DirectorySynchronizer:
    """Calculates synchronization actions and performs folder sync."""

    def __init__(self, file_ops: Optional[FileOperations] = None):
        self.file_ops = file_ops or FileOperations()

    def analyze(
        self,
        left_vfs: VFS,
        left_dir: str,
        right_vfs: VFS,
        right_dir: str,
        direction: SyncDirection = SyncDirection.TWO_WAY,
    ) -> List[SyncItem]:
        left_files = self._collect_all(left_vfs, left_dir)
        right_files = self._collect_all(right_vfs, right_dir)

        all_rel_paths = sorted(set(left_files.keys()) | set(right_files.keys()))
        sync_items: List[SyncItem] = []

        for rel in all_rel_paths:
            l_stat = left_files.get(rel)
            r_stat = right_files.get(rel)

            if l_stat and not r_stat:
                if direction in (SyncDirection.TWO_WAY, SyncDirection.LEFT_TO_RIGHT):
                    act = SyncAction.COPY_TO_RIGHT
                    reason = "New on left"
                else:
                    act = SyncAction.DELETE_LEFT
                    reason = "Missing on right (one-way)"
            elif r_stat and not l_stat:
                if direction == SyncDirection.TWO_WAY:
                    act = SyncAction.COPY_TO_LEFT
                    reason = "New on right"
                elif direction == SyncDirection.RIGHT_TO_LEFT:
                    act = SyncAction.COPY_TO_LEFT
                    reason = "New on right"
                else:
                    act = SyncAction.DELETE_RIGHT
                    reason = "Missing on left (one-way)"
            else:
                # Both exist: compare size and mtime
                if l_stat.size == r_stat.size and abs(l_stat.mtime - r_stat.mtime) < 1.0:
                    act = SyncAction.IDENTICAL
                    reason = "Identical"
                else:
                    if direction == SyncDirection.LEFT_TO_RIGHT:
                        act = SyncAction.COPY_TO_RIGHT
                        reason = "Left to right overwrite"
                    elif direction == SyncDirection.RIGHT_TO_LEFT:
                        act = SyncAction.COPY_TO_LEFT
                        reason = "Right to left overwrite"
                    else:
                        # Two-way: newer wins, or conflict if both modified
                        if l_stat.mtime > r_stat.mtime:
                            act = SyncAction.COPY_TO_RIGHT
                            reason = "Left is newer"
                        elif r_stat.mtime > l_stat.mtime:
                            act = SyncAction.COPY_TO_LEFT
                            reason = "Right is newer"
                        else:
                            act = SyncAction.CONFLICT
                            reason = "Different size, same timestamp"

            sync_items.append(
                SyncItem(
                    rel_path=rel,
                    left_stat=l_stat,
                    right_stat=r_stat,
                    action=act,
                    reason=reason,
                )
            )

        return sync_items

    def execute_sync(
        self,
        left_vfs: VFS,
        left_dir: str,
        right_vfs: VFS,
        right_dir: str,
        items: List[SyncItem],
    ) -> None:
        """Executes the analyzed sync actions."""
        for item in items:
            left_path = os.path.join(left_dir, item.rel_path)
            right_path = os.path.join(right_dir, item.rel_path)

            if item.action == SyncAction.COPY_TO_RIGHT:
                os.makedirs(os.path.dirname(right_path), exist_ok=True)
                self.file_ops.copy_file(left_vfs, left_path, right_vfs, right_path, policy=OverwritePolicy.OVERWRITE)
            elif item.action == SyncAction.COPY_TO_LEFT:
                os.makedirs(os.path.dirname(left_path), exist_ok=True)
                self.file_ops.copy_file(right_vfs, right_path, left_vfs, left_path, policy=OverwritePolicy.OVERWRITE)
            elif item.action == SyncAction.DELETE_LEFT:
                if left_vfs.exists(left_path):
                    left_vfs.remove_file(left_path)
            elif item.action == SyncAction.DELETE_RIGHT:
                if right_vfs.exists(right_path):
                    right_vfs.remove_file(right_path)

    def _collect_all(self, vfs: VFS, base_dir: str) -> Dict[str, FileStat]:
        result = {}
        norm_base = vfs.normalize_path(base_dir)

        def walk(cur: str):
            try:
                for entry in vfs.list_dir(cur):
                    if entry.is_dir:
                        walk(entry.path)
                    else:
                        rel = os.path.relpath(entry.path, norm_base)
                        result[rel] = entry
            except Exception:
                pass

        walk(norm_base)
        return result


@dataclass
class DiffLine:
    left_line_num: Optional[int]
    left_text: str
    right_line_num: Optional[int]
    right_text: str
    diff_type: str  # "same", "change", "insert", "delete"


class SideBySideFileDiff:
    """Visual side-by-side file diff tool with intra-line change comparison."""

    @classmethod
    def compute_diff(cls, left_content: str, right_content: str) -> List[DiffLine]:
        left_lines = left_content.splitlines()
        right_lines = right_content.splitlines()
        matcher = difflib.SequenceMatcher(None, left_lines, right_lines)

        result: List[DiffLine] = []
        l_idx = 1
        r_idx = 1

        for tag, alo, ahi, blo, bhi in matcher.get_opcodes():
            if tag == "equal":
                for a_i, b_i in zip(range(alo, ahi), range(blo, bhi)):
                    result.append(
                        DiffLine(
                            left_line_num=l_idx,
                            left_text=left_lines[a_i],
                            right_line_num=r_idx,
                            right_text=right_lines[b_i],
                            diff_type="same",
                        )
                    )
                    l_idx += 1
                    r_idx += 1
            elif tag == "replace":
                a_slice = left_lines[alo:ahi]
                b_slice = right_lines[blo:bhi]
                max_len = max(len(a_slice), len(b_slice))
                for i in range(max_len):
                    has_l = i < len(a_slice)
                    has_r = i < len(b_slice)
                    result.append(
                        DiffLine(
                            left_line_num=l_idx if has_l else None,
                            left_text=a_slice[i] if has_l else "",
                            right_line_num=r_idx if has_r else None,
                            right_text=b_slice[i] if has_r else "",
                            diff_type="change",
                        )
                    )
                    if has_l:
                        l_idx += 1
                    if has_r:
                        r_idx += 1
            elif tag == "delete":
                for a_i in range(alo, ahi):
                    result.append(
                        DiffLine(
                            left_line_num=l_idx,
                            left_text=left_lines[a_i],
                            right_line_num=None,
                            right_text="",
                            diff_type="delete",
                        )
                    )
                    l_idx += 1
            elif tag == "insert":
                for b_i in range(blo, bhi):
                    result.append(
                        DiffLine(
                            left_line_num=None,
                            left_text="",
                            right_line_num=r_idx,
                            right_text=right_lines[b_i],
                            diff_type="insert",
                        )
                    )
                    r_idx += 1

        return result
