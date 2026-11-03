"""Archive Virtual Filesystem supporting transparent browsing and editing (.zip, .tar, .tar.gz, etc.)."""

from __future__ import annotations
import io
import os
import posixpath
import tarfile
import tempfile
import time
import zipfile
from typing import BinaryIO, Dict, List, Optional, Tuple
from pycommander.vfs import FileStat, VFS


class ArchiveVFS(VFS):
    """VFS provider that mounts an archive file as a directory."""

    def __init__(self, archive_path: str, format_type: Optional[str] = None):
        self.archive_path = os.path.abspath(archive_path)
        if not format_type:
            lower = self.archive_path.lower()
            if lower.endswith(".zip"):
                format_type = "zip"
            elif lower.endswith((".tar.gz", ".tgz")):
                format_type = "tar.gz"
            elif lower.endswith((".tar.bz2", ".tbz2")):
                format_type = "tar.bz2"
            elif lower.endswith((".tar.xz", ".txz")):
                format_type = "tar.xz"
            elif lower.endswith(".tar"):
                format_type = "tar"
            else:
                format_type = "zip"
        self.format_type = format_type
        self._entries: Dict[str, FileStat] = {}
        self._refresh_index()

    def _refresh_index(self) -> None:
        self._entries = {}
        # Root directory
        self._entries["/"] = FileStat(
            name="/",
            path="/",
            is_dir=True,
            size=0,
            mtime=os.path.getmtime(self.archive_path) if os.path.exists(self.archive_path) else time.time(),
            mode=0o755,
        )

        if self.format_type == "zip":
            if not os.path.exists(self.archive_path):
                return
            with zipfile.ZipFile(self.archive_path, "r") as zf:
                for info in zf.infolist():
                    clean_path = "/" + info.filename.strip("/")
                    is_dir = info.is_dir()
                    dt = datetime = time.mktime(info.date_time + (0, 0, -1))
                    name = posixpath.basename(clean_path)
                    if not name:
                        continue

                    # Ensure parent dirs exist in index
                    parent = posixpath.dirname(clean_path)
                    self._ensure_parent_dirs(parent)

                    self._entries[clean_path] = FileStat(
                        name=name,
                        path=clean_path,
                        is_dir=is_dir,
                        size=info.file_size,
                        mtime=dt,
                        mode=0o755 if is_dir else 0o644,
                    )

        elif self.format_type.startswith("tar"):
            if not os.path.exists(self.archive_path):
                return
            mode = "r:*"
            if self.format_type == "tar.gz":
                mode = "r:gz"
            elif self.format_type == "tar.bz2":
                mode = "r:bz2"
            elif self.format_type == "tar.xz":
                mode = "r:xz"

            with tarfile.open(self.archive_path, mode) as tf:
                for member in tf.getmembers():
                    clean_path = "/" + member.name.strip("/")
                    name = posixpath.basename(clean_path)
                    if not name:
                        continue
                    parent = posixpath.dirname(clean_path)
                    self._ensure_parent_dirs(parent)

                    self._entries[clean_path] = FileStat(
                        name=name,
                        path=clean_path,
                        is_dir=member.isdir(),
                        is_symlink=member.issym(),
                        symlink_target=member.linkname if member.issym() else None,
                        size=member.size,
                        mtime=member.mtime,
                        mode=member.mode,
                        uid=member.uid,
                        gid=member.gid,
                        user=member.uname,
                        group=member.gname,
                    )

    def _ensure_parent_dirs(self, parent: str) -> None:
        if parent == "/" or not parent:
            return
        parts = [p for p in parent.split("/") if p]
        curr = ""
        for p in parts:
            curr = f"{curr}/{p}"
            if curr not in self._entries:
                self._entries[curr] = FileStat(
                    name=p,
                    path=curr,
                    is_dir=True,
                    size=0,
                    mtime=time.time(),
                    mode=0o755,
                )

    def normalize_path(self, path: str) -> str:
        if not path or path == ".":
            return "/"
        clean = posixpath.normpath("/" + path.lstrip("/"))
        return clean

    def list_dir(self, path: str) -> List[FileStat]:
        norm = self.normalize_path(path)
        if norm not in self._entries or not self._entries[norm].is_dir:
            raise NotADirectoryError(f"Not a directory in archive: {norm}")

        results = []
        prefix = norm if norm.endswith("/") else norm + "/"
        if norm == "/":
            prefix = "/"

        seen_names = set()
        for item_path, st in self._entries.items():
            if item_path == norm:
                continue
            if norm == "/":
                rel = item_path.lstrip("/")
            else:
                if not item_path.startswith(prefix):
                    continue
                rel = item_path[len(prefix):]

            if "/" not in rel:
                # Direct child
                if st.name not in seen_names:
                    results.append(st)
                    seen_names.add(st.name)

        results.sort(key=lambda x: (not x.is_dir, x.name.lower()))
        return results

    def stat(self, path: str) -> FileStat:
        norm = self.normalize_path(path)
        if norm not in self._entries:
            raise FileNotFoundError(f"Path not found in archive: {norm}")
        return self._entries[norm]

    def exists(self, path: str) -> bool:
        norm = self.normalize_path(path)
        return norm in self._entries

    def is_dir(self, path: str) -> bool:
        norm = self.normalize_path(path)
        return norm in self._entries and self._entries[norm].is_dir

    def read_bytes(self, path: str, length: int = -1, offset: int = 0) -> bytes:
        norm = self.normalize_path(path)
        if norm not in self._entries or self._entries[norm].is_dir:
            raise FileNotFoundError(f"File not found in archive: {norm}")

        arc_internal_name = norm.lstrip("/")
        if self.format_type == "zip":
            with zipfile.ZipFile(self.archive_path, "r") as zf:
                with zf.open(arc_internal_name) as f:
                    if offset > 0:
                        f.seek(offset)
                    if length >= 0:
                        return f.read(length)
                    return f.read()
        else:
            mode = "r:*"
            with tarfile.open(self.archive_path, mode) as tf:
                extracted = tf.extractfile(arc_internal_name)
                if not extracted:
                    raise IOError(f"Failed to extract file: {norm}")
                with extracted as f:
                    if offset > 0:
                        f.seek(offset)
                    if length >= 0:
                        return f.read(length)
                    return f.read()

    def open_read(self, path: str) -> BinaryIO:
        data = self.read_bytes(path)
        return io.BytesIO(data)

    def write_bytes(self, path: str, data: bytes, append: bool = False) -> int:
        """Adds or updates a file directly inside the archive."""
        norm = self.normalize_path(path)
        internal_name = norm.lstrip("/")
        if not internal_name:
            raise ValueError("Cannot write to archive root directory")

        if self.format_type == "zip":
            # For zip, rewrite with updated/appended content
            temp_path = self.archive_path + ".tmp"
            written_bytes = 0
            has_existing = os.path.exists(self.archive_path)

            final_data = data
            if append and norm in self._entries:
                prev = self.read_bytes(norm)
                final_data = prev + data

            with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
                if has_existing:
                    with zipfile.ZipFile(self.archive_path, "r") as zin:
                        for item in zin.infolist():
                            if item.filename != internal_name:
                                zout.writestr(item, zin.read(item.filename))
                zout.writestr(internal_name, final_data)
                written_bytes = len(final_data)

            os.replace(temp_path, self.archive_path)
            self._refresh_index()
            return written_bytes
        else:
            raise NotImplementedError("Direct writing to tar archives is not supported yet.")

    def open_write(self, path: str, append: bool = False) -> BinaryIO:
        """Buffered write stream for archive."""
        class ArchiveWriteStream(io.BytesIO):
            def __init__(stream_self, vfs_instance, file_path, append_mode):
                super().__init__()
                stream_self._vfs = vfs_instance
                stream_self._path = file_path
                stream_self._append = append_mode

            def close(stream_self):
                content = stream_self.getvalue()
                super().close()
                stream_self._vfs.write_bytes(stream_self._path, content, append=stream_self._append)

        return ArchiveWriteStream(self, path, append)

    def make_dir(self, path: str, parents: bool = True) -> None:
        norm = self.normalize_path(path)
        if norm == "/":
            return
        internal_name = norm.lstrip("/") + "/"
        if self.format_type == "zip":
            temp_path = self.archive_path + ".tmp"
            with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
                if os.path.exists(self.archive_path):
                    with zipfile.ZipFile(self.archive_path, "r") as zin:
                        for item in zin.infolist():
                            zout.writestr(item, zin.read(item.filename))
                zout.writestr(zipfile.ZipInfo(internal_name), "")
            os.replace(temp_path, self.archive_path)
            self._refresh_index()
        else:
            raise NotImplementedError("mkdir not implemented for tar archives")

    def remove_file(self, path: str) -> None:
        norm = self.normalize_path(path)
        internal_name = norm.lstrip("/")
        if self.format_type == "zip":
            temp_path = self.archive_path + ".tmp"
            with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
                with zipfile.ZipFile(self.archive_path, "r") as zin:
                    for item in zin.infolist():
                        if item.filename.rstrip("/") != internal_name:
                            zout.writestr(item, zin.read(item.filename))
            os.replace(temp_path, self.archive_path)
            self._refresh_index()
        else:
            raise NotImplementedError("remove_file not supported for tar")

    def remove_dir(self, path: str, recursive: bool = False) -> None:
        norm = self.normalize_path(path)
        internal_prefix = norm.lstrip("/") + "/"
        if self.format_type == "zip":
            temp_path = self.archive_path + ".tmp"
            with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
                with zipfile.ZipFile(self.archive_path, "r") as zin:
                    for item in zin.infolist():
                        if not item.filename.startswith(internal_prefix):
                            zout.writestr(item, zin.read(item.filename))
            os.replace(temp_path, self.archive_path)
            self._refresh_index()

    def rename(self, src: str, dst: str) -> None:
        data = self.read_bytes(src)
        self.write_bytes(dst, data)
        self.remove_file(src)
