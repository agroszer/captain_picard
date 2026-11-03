"""Advanced File Finder, Full-Text Search, and Duplicate File Finder."""

from __future__ import annotations
import fnmatch
import hashlib
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, Generator, List, Optional
from pycommander.archive_vfs import ArchiveVFS
from pycommander.vfs import FileStat, LocalVFS, VFS


@dataclass
class SearchCriteria:
    """Criteria for finding files."""
    name_pattern: str = "*"           # Wildcards (*.py, *.*) or regex if starts with re:
    content_pattern: Optional[str] = None  # Text or regex pattern inside file content
    case_sensitive: bool = False
    min_size: Optional[int] = None     # Bytes
    max_size: Optional[int] = None     # Bytes
    modified_after: Optional[float] = None
    modified_before: Optional[float] = None
    search_archives: bool = True       # Search inside .zip, .tar.gz archives
    is_regex: bool = False


class FileFinder:
    """Traverses directories/VFS and locates files matching criteria."""

    def __init__(self, vfs: Optional[VFS] = None):
        self.vfs = vfs or LocalVFS()

    def search(
        self,
        start_dir: str,
        criteria: SearchCriteria,
        cancel_check: Optional[Callable[[], bool]] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> List[FileStat]:
        results: List[FileStat] = []
        norm_start = self.vfs.normalize_path(start_dir)

        # Prepare regex for name matching
        if criteria.name_pattern.startswith("re:"):
            name_re = re.compile(
                criteria.name_pattern[3:],
                0 if criteria.case_sensitive else re.IGNORECASE,
            )
            use_regex_name = True
        else:
            name_re = None
            use_regex_name = False

        # Prepare content pattern regex
        content_re = None
        if criteria.content_pattern:
            flags = 0 if criteria.case_sensitive else re.IGNORECASE
            try:
                content_re = re.compile(criteria.content_pattern.encode("utf-8"), flags)
            except Exception:
                content_re = re.compile(re.escape(criteria.content_pattern).encode("utf-8"), flags)

        def walk(current_dir: str):
            if cancel_check and cancel_check():
                return
            if progress_callback:
                progress_callback(current_dir)

            try:
                entries = self.vfs.list_dir(current_dir)
            except Exception:
                return

            for entry in entries:
                if cancel_check and cancel_check():
                    return

                if entry.is_dir:
                    walk(entry.path)
                    continue

                # Check archive search
                if criteria.search_archives and entry.name.lower().endswith((".zip", ".tar.gz", ".tgz")):
                    try:
                        arc_vfs = ArchiveVFS(entry.path)
                        arc_finder = FileFinder(arc_vfs)
                        arc_results = arc_finder.search(
                            "/",
                            criteria,
                            cancel_check=cancel_check,
                        )
                        for r in arc_results:
                            r.path = f"{entry.path}!{r.path}"
                            results.append(r)
                    except Exception:
                        pass

                # Check name match
                matched_name = False
                if use_regex_name and name_re:
                    matched_name = bool(name_re.search(entry.name))
                else:
                    patterns = [p.strip() for p in criteria.name_pattern.split(";") if p.strip()]
                    for pat in patterns:
                        if criteria.case_sensitive:
                            if fnmatch.fnmatchcase(entry.name, pat):
                                matched_name = True
                                break
                        else:
                            if fnmatch.fnmatch(entry.name.lower(), pat.lower()):
                                matched_name = True
                                break

                if not matched_name:
                    continue

                # Check size range
                if criteria.min_size is not None and entry.size < criteria.min_size:
                    continue
                if criteria.max_size is not None and entry.size > criteria.max_size:
                    continue

                # Check date range
                if criteria.modified_after is not None and entry.mtime < criteria.modified_after:
                    continue
                if criteria.modified_before is not None and entry.mtime > criteria.modified_before:
                    continue

                # Check content search
                if content_re is not None:
                    try:
                        content_bytes = self.vfs.read_bytes(entry.path, length=1024 * 1024)
                        if not content_re.search(content_bytes):
                            continue
                    except Exception:
                        continue

                results.append(entry)

        walk(norm_start)
        return results


class DuplicateFinder:
    """Finds redundant files by comparing filename, size, and SHA256 hashes."""

    def __init__(self, vfs: Optional[VFS] = None):
        self.vfs = vfs or LocalVFS()

    @staticmethod
    def calculate_sha256(vfs: VFS, path: str, chunk_size: int = 64 * 1024) -> str:
        h = hashlib.sha256()
        with vfs.open_read(path) as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    def find_duplicates(
        self,
        start_dirs: List[str],
        match_by: str = "hash",  # "hash", "size_and_name", "size"
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, List[FileStat]]:
        """
        Returns mapping from duplicate key (e.g., hash or (name, size)) to list of duplicate FileStat objects.
        Only entries with 2 or more files are returned.
        """
        all_files: List[FileStat] = []

        def collect(d: str):
            if cancel_check and cancel_check():
                return
            try:
                entries = self.vfs.list_dir(d)
                for e in entries:
                    if cancel_check and cancel_check():
                        return
                    if e.is_dir:
                        collect(e.path)
                    else:
                        all_files.append(e)
            except Exception:
                pass

        for d in start_dirs:
            collect(self.vfs.normalize_path(d))

        # First bucket by size to optimize hashing
        size_buckets: Dict[int, List[FileStat]] = {}
        for f in all_files:
            size_buckets.setdefault(f.size, []).append(f)

        duplicates: Dict[str, List[FileStat]] = {}

        if match_by == "size":
            for size, files in size_buckets.items():
                if len(files) > 1 and size > 0:
                    duplicates[f"size:{size}"] = files

        elif match_by == "size_and_name":
            name_size_buckets: Dict[str, List[FileStat]] = {}
            for f in all_files:
                key = f"{f.name}:{f.size}"
                name_size_buckets.setdefault(key, []).append(f)
            for k, files in name_size_buckets.items():
                if len(files) > 1:
                    duplicates[k] = files

        elif match_by == "hash":
            # Only compute hashes for files having identical size > 0
            for size, files in size_buckets.items():
                if len(files) > 1 and size > 0:
                    hash_buckets: Dict[str, List[FileStat]] = {}
                    for f in files:
                        if cancel_check and cancel_check():
                            return duplicates
                        try:
                            f_hash = self.calculate_sha256(self.vfs, f.path)
                            hash_buckets.setdefault(f_hash, []).append(f)
                        except Exception:
                            continue
                    for h, h_files in hash_buckets.items():
                        if len(h_files) > 1:
                            duplicates[h] = h_files

        return duplicates
