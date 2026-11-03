"""File Operations Engine with granular overwrite policies and attribute preservation."""

from __future__ import annotations
import enum
import os
import shutil
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple
from pycommander.vfs import FileStat, VFS


class OverwritePolicy(enum.Enum):
    OVERWRITE = "overwrite"
    SKIP = "skip"
    OVERWRITE_IF_NEWER = "overwrite_if_newer"
    OVERWRITE_IF_SIZE_DIFFERS = "overwrite_if_size_differs"
    AUTO_RENAME = "auto_rename"
    APPEND = "append"


@dataclass
class OpProgress:
    current_file: str = ""
    total_files: int = 0
    completed_files: int = 0
    total_bytes: int = 0
    completed_bytes: int = 0
    bytes_per_sec: float = 0.0
    status: str = "running"  # running, paused, cancelled, completed, error
    error_message: Optional[str] = None


class FileOperations:
    """Core file operations engine with policy evaluation and attribute preservation."""

    def __init__(self, default_policy: OverwritePolicy = OverwritePolicy.OVERWRITE):
        self.default_policy = default_policy

    @staticmethod
    def should_overwrite(
        src_stat: FileStat,
        dst_stat: FileStat,
        policy: OverwritePolicy,
    ) -> bool:
        """Determines whether dst should be overwritten by src under policy."""
        if policy == OverwritePolicy.OVERWRITE:
            return True
        elif policy == OverwritePolicy.SKIP:
            return False
        elif policy == OverwritePolicy.OVERWRITE_IF_NEWER:
            return src_stat.mtime > dst_stat.mtime
        elif policy == OverwritePolicy.OVERWRITE_IF_SIZE_DIFFERS:
            return src_stat.size != dst_stat.size
        elif policy == OverwritePolicy.APPEND:
            return True
        elif policy == OverwritePolicy.AUTO_RENAME:
            return False  # Will generate a new name instead
        return True

    @staticmethod
    def get_auto_renamed_path(vfs: VFS, dst_path: str) -> str:
        """Generates an auto-incremented non-existing path: foo_1.txt, foo_2.txt..."""
        if not vfs.exists(dst_path):
            return dst_path
        dirname, basename = os.path.split(dst_path)
        name, ext = os.path.splitext(basename)
        counter = 1
        while True:
            candidate = os.path.join(dirname, f"{name}_{counter}{ext}")
            if not vfs.exists(candidate):
                return candidate
            counter += 1

    def copy_file(
        self,
        src_vfs: VFS,
        src_path: str,
        dst_vfs: VFS,
        dst_path: str,
        policy: Optional[OverwritePolicy] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        throttle_kb_s: float = 0.0,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> bool:
        """Copies a single file across or within VFS providers with policy checks and throttling."""
        if cancel_check and cancel_check():
            return False

        effective_policy = policy or self.default_policy
        src_st = src_vfs.stat(src_path)

        # If destination exists, evaluate overwrite policy
        if dst_vfs.exists(dst_path):
            if dst_vfs.is_dir(dst_path):
                dst_path = os.path.join(dst_path, src_st.name)

            if dst_vfs.exists(dst_path):
                dst_st = dst_vfs.stat(dst_path)
                if effective_policy == OverwritePolicy.AUTO_RENAME:
                    dst_path = self.get_auto_renamed_path(dst_vfs, dst_path)
                elif not self.should_overwrite(src_st, dst_st, effective_policy):
                    return False

        is_append = (effective_policy == OverwritePolicy.APPEND)
        chunk_size = 64 * 1024  # 64KB chunks
        bytes_copied = 0

        with src_vfs.open_read(src_path) as fin, dst_vfs.open_write(dst_path, append=is_append) as fout:
            while True:
                if cancel_check and cancel_check():
                    return False
                chunk = fin.read(chunk_size)
                if not chunk:
                    break
                fout.write(chunk)
                bytes_copied += len(chunk)
                if progress_callback:
                    progress_callback(len(chunk), bytes_copied)

                # Throttle transfer speed if configured
                if throttle_kb_s > 0:
                    sleep_time = (len(chunk) / (throttle_kb_s * 1024.0))
                    if sleep_time > 0:
                        time.sleep(sleep_time)

        # Preserve Unix permissions and timestamps
        try:
            dst_vfs.set_attributes(
                dst_path,
                mode=src_st.mode,
                mtime=src_st.mtime,
                atime=src_st.atime,
                uid=src_st.uid,
                gid=src_st.gid,
            )
        except Exception:
            pass

        return True

    def copy_directory(
        self,
        src_vfs: VFS,
        src_dir: str,
        dst_vfs: VFS,
        dst_dir: str,
        policy: Optional[OverwritePolicy] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> None:
        """Recursively copies directory tree."""
        if not dst_vfs.exists(dst_dir):
            dst_vfs.make_dir(dst_dir, parents=True)

        for entry in src_vfs.list_dir(src_dir):
            if cancel_check and cancel_check():
                return
            target_entry_path = os.path.join(dst_dir, entry.name)
            if entry.is_dir:
                self.copy_directory(
                    src_vfs,
                    entry.path,
                    dst_vfs,
                    target_entry_path,
                    policy=policy,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check,
                )
            else:
                self.copy_file(
                    src_vfs,
                    entry.path,
                    dst_vfs,
                    target_entry_path,
                    policy=policy,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check,
                )

    def move_file(
        self,
        src_vfs: VFS,
        src_path: str,
        dst_vfs: VFS,
        dst_path: str,
        policy: Optional[OverwritePolicy] = None,
    ) -> bool:
        """Moves a file. If src and dst share the same local VFS, uses atomic rename."""
        if src_vfs == dst_vfs and src_vfs.__class__.__name__ == "LocalVFS":
            final_dst = dst_path
            if dst_vfs.exists(dst_path) and dst_vfs.is_dir(dst_path):
                final_dst = os.path.join(dst_path, os.path.basename(src_path))
            if dst_vfs.exists(final_dst):
                eff = policy or self.default_policy
                if eff == OverwritePolicy.AUTO_RENAME:
                    final_dst = self.get_auto_renamed_path(dst_vfs, final_dst)
                elif not self.should_overwrite(src_vfs.stat(src_path), dst_vfs.stat(final_dst), eff):
                    return False
            src_vfs.rename(src_path, final_dst)
            return True

        # Cross-VFS move: copy then delete
        copied = self.copy_file(src_vfs, src_path, dst_vfs, dst_path, policy=policy)
        if copied:
            src_vfs.remove_file(src_path)
            return True
        return False

    def delete_item(self, vfs: VFS, path: str, recursive: bool = True) -> None:
        """Deletes a file or directory tree."""
        if vfs.is_dir(path):
            vfs.remove_dir(path, recursive=recursive)
        else:
            vfs.remove_file(path)
