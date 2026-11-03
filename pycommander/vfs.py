"""Virtual Filesystem (VFS) abstraction and Local Filesystem implementation."""

from __future__ import annotations
import os
import shutil
import stat
import time
try:
    import pwd
    import grp
except ImportError:
    pwd = None
    grp = None
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, BinaryIO, Dict, Iterable, List, Optional, Tuple, Union


@dataclass
class FileStat:
    """Standardized metadata entry across all VFS providers."""
    name: str
    path: str
    is_dir: bool = False
    is_symlink: bool = False
    symlink_target: Optional[str] = None
    size: int = 0
    mtime: float = 0.0
    atime: float = 0.0
    ctime: float = 0.0
    mode: int = 0o644
    uid: int = 0
    gid: int = 0
    user: str = ""
    group: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def permissions_str(self) -> str:
        """Returns standard Unix permissions string e.g. -rw-r--r-- or drwxr-xr-x."""
        return stat.filemode(self.mode)

    @property
    def formatted_mtime(self) -> str:
        """Formatted timestamp for file listings."""
        try:
            dt = datetime.fromtimestamp(self.mtime)
            now = datetime.now()
            if dt.year == now.year:
                return dt.strftime("%b %d %H:%M")
            return dt.strftime("%b %d  %Y")
        except Exception:
            return "--- -- --:--"

    @property
    def formatted_size(self) -> str:
        """Human-readable size format."""
        if self.is_dir:
            return "<DIR>"
        n = float(self.size)
        for unit in ["B", "K", "M", "G", "T", "P"]:
            if n < 1024.0 or unit == "P":
                if unit == "B":
                    return f"{int(n)} B"
                return f"{n:.1f}{unit}"
            n /= 1024.0
        return f"{self.size} B"

    @property
    def extension(self) -> str:
        """File extension without dot, lowercased."""
        if self.is_dir:
            return ""
        _, ext = os.path.splitext(self.name)
        return ext.lstrip(".").lower()


class VFS(ABC):
    """Abstract Base Class for all Virtual Filesystems."""

    @abstractmethod
    def list_dir(self, path: str) -> List[FileStat]:
        """Lists directory entries under path."""
        pass

    @abstractmethod
    def stat(self, path: str) -> FileStat:
        """Retrieves stat metadata for path."""
        pass

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Checks if path exists."""
        pass

    @abstractmethod
    def is_dir(self, path: str) -> bool:
        """Checks if path is a directory."""
        pass

    @abstractmethod
    def open_read(self, path: str) -> BinaryIO:
        """Opens file stream for reading bytes."""
        pass

    @abstractmethod
    def open_write(self, path: str, append: bool = False) -> BinaryIO:
        """Opens file stream for writing bytes."""
        pass

    @abstractmethod
    def read_bytes(self, path: str, length: int = -1, offset: int = 0) -> bytes:
        """Reads raw bytes from file."""
        pass

    @abstractmethod
    def write_bytes(self, path: str, data: bytes, append: bool = False) -> int:
        """Writes raw bytes to file."""
        pass

    @abstractmethod
    def make_dir(self, path: str, parents: bool = True) -> None:
        """Creates a directory."""
        pass

    @abstractmethod
    def remove_file(self, path: str) -> None:
        """Removes a file."""
        pass

    @abstractmethod
    def remove_dir(self, path: str, recursive: bool = False) -> None:
        """Removes a directory."""
        pass

    @abstractmethod
    def rename(self, src: str, dst: str) -> None:
        """Renames or moves src to dst within the VFS."""
        pass

    def copy_file(self, src: str, dst: str, preserve_attrs: bool = True) -> None:
        """Default stream-copy implementation between paths."""
        with self.open_read(src) as fsrc, self.open_write(dst) as fdst:
            shutil.copyfileobj(fsrc, fdst)
        if preserve_attrs:
            st = self.stat(src)
            self.set_attributes(dst, mode=st.mode, mtime=st.mtime, atime=st.atime)

    def set_attributes(
        self,
        path: str,
        mode: Optional[int] = None,
        mtime: Optional[float] = None,
        atime: Optional[float] = None,
        uid: Optional[int] = None,
        gid: Optional[int] = None,
    ) -> None:
        """Preserves permissions and timestamps if supported by implementation."""
        pass

    def get_free_space(self, path: str) -> Tuple[int, int, int]:
        """Returns (total_bytes, used_bytes, free_bytes)."""
        return (0, 0, 0)

    def normalize_path(self, path: str) -> str:
        """Normalizes path."""
        return os.path.normpath(path)


class LocalVFS(VFS):
    """Local OS Filesystem implementation of VFS with attribute preservation."""

    def normalize_path(self, path: str) -> str:
        if not path:
            return os.path.abspath(os.getcwd())
        expanded = os.path.expanduser(path)
        return os.path.abspath(expanded)

    def stat(self, path: str) -> FileStat:
        norm = self.normalize_path(path)
        name = os.path.basename(norm) or "/"
        try:
            # use lstat to detect symlinks properly
            st = os.lstat(norm)
            is_symlink = stat.S_ISLNK(st.st_mode)
            symlink_target = os.readlink(norm) if is_symlink else None
            # If it's a symlink pointing to a dir, follow target to see if is_dir
            is_dir = stat.S_ISDIR(st.st_mode)
            if is_symlink:
                try:
                    stat_target = os.stat(norm)
                    is_dir = stat.S_ISDIR(stat_target.st_mode)
                except Exception:
                    pass

            user = ""
            group = ""
            if pwd is not None:
                try:
                    user = pwd.getpwuid(st.st_uid).pw_name
                except Exception:
                    user = str(st.st_uid)
            else:
                user = str(st.st_uid)

            if grp is not None:
                try:
                    group = grp.getgrgid(st.st_gid).gr_name
                except Exception:
                    group = str(st.st_gid)
            else:
                group = str(st.st_gid)

            return FileStat(
                name=name,
                path=norm,
                is_dir=is_dir,
                is_symlink=is_symlink,
                symlink_target=symlink_target,
                size=st.st_size,
                mtime=st.st_mtime,
                atime=st.st_atime,
                ctime=st.st_ctime,
                mode=st.st_mode,
                uid=st.st_uid,
                gid=st.st_gid,
                user=user,
                group=group,
            )
        except FileNotFoundError:
            raise FileNotFoundError(f"Path not found: {norm}")

    def list_dir(self, path: str) -> List[FileStat]:
        norm = self.normalize_path(path)
        if not os.path.isdir(norm):
            raise NotADirectoryError(f"Not a directory: {norm}")

        entries = []
        try:
            with os.scandir(norm) as it:
                for entry in it:
                    try:
                        st = self.stat(entry.path)
                        entries.append(st)
                    except Exception:
                        continue
        except PermissionError as e:
            raise PermissionError(f"Permission denied: {norm}") from e

        # Sort directories first, then alphabetical case-insensitive
        entries.sort(key=lambda x: (not x.is_dir, x.name.lower()))
        return entries

    def exists(self, path: str) -> bool:
        norm = self.normalize_path(path)
        return os.path.exists(norm) or os.path.islink(norm)

    def is_dir(self, path: str) -> bool:
        norm = self.normalize_path(path)
        return os.path.isdir(norm)

    def open_read(self, path: str) -> BinaryIO:
        norm = self.normalize_path(path)
        return open(norm, "rb")

    def open_write(self, path: str, append: bool = False) -> BinaryIO:
        norm = self.normalize_path(path)
        mode = "ab" if append else "wb"
        return open(norm, mode)

    def read_bytes(self, path: str, length: int = -1, offset: int = 0) -> bytes:
        norm = self.normalize_path(path)
        with open(norm, "rb") as f:
            if offset > 0:
                f.seek(offset)
            if length >= 0:
                return f.read(length)
            return f.read()

    def write_bytes(self, path: str, data: bytes, append: bool = False) -> int:
        norm = self.normalize_path(path)
        mode = "ab" if append else "wb"
        with open(norm, mode) as f:
            return f.write(data)

    def make_dir(self, path: str, parents: bool = True) -> None:
        norm = self.normalize_path(path)
        if parents:
            os.makedirs(norm, exist_ok=True)
        else:
            os.mkdir(norm)

    def remove_file(self, path: str) -> None:
        norm = self.normalize_path(path)
        os.unlink(norm)

    def remove_dir(self, path: str, recursive: bool = False) -> None:
        norm = self.normalize_path(path)
        if recursive:
            shutil.rmtree(norm)
        else:
            os.rmdir(norm)

    def rename(self, src: str, dst: str) -> None:
        os.rename(self.normalize_path(src), self.normalize_path(dst))

    def set_attributes(
        self,
        path: str,
        mode: Optional[int] = None,
        mtime: Optional[float] = None,
        atime: Optional[float] = None,
        uid: Optional[int] = None,
        gid: Optional[int] = None,
    ) -> None:
        norm = self.normalize_path(path)
        if mode is not None:
            try:
                os.chmod(norm, stat.S_IMODE(mode))
            except Exception:
                pass
        if mtime is not None or atime is not None:
            st = os.stat(norm)
            new_atime = atime if atime is not None else st.st_atime
            new_mtime = mtime if mtime is not None else st.st_mtime
            try:
                os.utime(norm, (new_atime, new_mtime))
            except Exception:
                pass
        if uid is not None and gid is not None:
            try:
                os.chown(norm, uid, gid)
            except Exception:
                pass

    def get_free_space(self, path: str) -> Tuple[int, int, int]:
        norm = self.normalize_path(path)
        try:
            statvfs = shutil.disk_usage(norm)
            return (statvfs.total, statvfs.used, statvfs.free)
        except Exception:
            return (0, 0, 0)
