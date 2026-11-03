"""Virtual Folder VFS for search results ('Feed to listbox'), remote abstractions, and arbitrary item collections."""

from __future__ import annotations
import io
import os
import posixpath
from typing import BinaryIO, Callable, Dict, List, Optional
from pycommander.vfs import FileStat, LocalVFS, VFS


class VirtualFolderVFS(VFS):
    """
    VFS holding arbitrary FileStat entries, e.g. search hits, duplicate files,
    or bookmarks flattened into a list. Operations delegate to target item's underlying VFS.
    """

    def __init__(self, title: str = "Search Results", items: Optional[List[FileStat]] = None, underlying_vfs: Optional[VFS] = None):
        self.title = title
        self._items: Dict[str, FileStat] = {}
        self._underlying_vfs = underlying_vfs or LocalVFS()
        if items:
            for item in items:
                self.add_item(item)

    def add_item(self, item: FileStat) -> None:
        key = item.path
        self._items[key] = item

    def clear(self) -> None:
        self._items.clear()

    def list_dir(self, path: str) -> List[FileStat]:
        # Single flat directory containing all virtual items
        return sorted(self._items.values(), key=lambda x: (not x.is_dir, x.name.lower()))

    def stat(self, path: str) -> FileStat:
        if path in ("/", ""):
            return FileStat(name=self.title, path="/", is_dir=True)
        if path in self._items:
            return self._items[path]
        for it in self._items.values():
            if it.path == path or it.name == path:
                return it
        return self._underlying_vfs.stat(path)

    def exists(self, path: str) -> bool:
        if path in ("/", ""):
            return True
        return path in self._items or self._underlying_vfs.exists(path)

    def is_dir(self, path: str) -> bool:
        if path in ("/", ""):
            return True
        if path in self._items:
            return self._items[path].is_dir
        return self._underlying_vfs.is_dir(path)

    def open_read(self, path: str) -> BinaryIO:
        target_path = self.stat(path).path
        return self._underlying_vfs.open_read(target_path)

    def open_write(self, path: str, append: bool = False) -> BinaryIO:
        target_path = self.stat(path).path
        return self._underlying_vfs.open_write(target_path, append=append)

    def read_bytes(self, path: str, length: int = -1, offset: int = 0) -> bytes:
        target_path = self.stat(path).path
        return self._underlying_vfs.read_bytes(target_path, length=length, offset=offset)

    def write_bytes(self, path: str, data: bytes, append: bool = False) -> int:
        target_path = self.stat(path).path
        return self._underlying_vfs.write_bytes(target_path, data, append=append)

    def make_dir(self, path: str, parents: bool = True) -> None:
        raise NotImplementedError("Cannot make directory inside Virtual Listbox.")

    def remove_file(self, path: str) -> None:
        st = self.stat(path)
        self._underlying_vfs.remove_file(st.path)
        if st.path in self._items:
            del self._items[st.path]

    def remove_dir(self, path: str, recursive: bool = False) -> None:
        st = self.stat(path)
        self._underlying_vfs.remove_dir(st.path, recursive=recursive)
        if st.path in self._items:
            del self._items[st.path]

    def rename(self, src: str, dst: str) -> None:
        st = self.stat(src)
        self._underlying_vfs.rename(st.path, dst)
        del self._items[st.path]
        new_st = self._underlying_vfs.stat(dst)
        self._items[new_st.path] = new_st


class RemoteVFS(VFS):
    """
    Extensible Remote Filesystem base provider (SFTP, FTP, SMB, WebDAV, S3).
    Provides pluggable remote filesystem interface for remote panes.
    """

    def __init__(self, protocol: str, host: str, port: Optional[int] = None, user: str = "", path_prefix: str = "/"):
        self.protocol = protocol
        self.host = host
        self.port = port
        self.user = user
        self.path_prefix = path_prefix
        self._mock_data: Dict[str, bytes] = {}
        self._mock_stats: Dict[str, FileStat] = {
            "/": FileStat(name="/", path="/", is_dir=True, mode=0o755)
        }

    def list_dir(self, path: str) -> List[FileStat]:
        norm = posixpath.normpath("/" + path.lstrip("/"))
        res = []
        for p, st in self._mock_stats.items():
            if p == norm:
                continue
            parent = posixpath.dirname(p)
            if parent == norm:
                res.append(st)
        return sorted(res, key=lambda x: (not x.is_dir, x.name.lower()))

    def stat(self, path: str) -> FileStat:
        norm = posixpath.normpath("/" + path.lstrip("/"))
        if norm in self._mock_stats:
            return self._mock_stats[norm]
        raise FileNotFoundError(f"Remote path not found: {norm}")

    def exists(self, path: str) -> bool:
        norm = posixpath.normpath("/" + path.lstrip("/"))
        return norm in self._mock_stats

    def is_dir(self, path: str) -> bool:
        norm = posixpath.normpath("/" + path.lstrip("/"))
        return norm in self._mock_stats and self._mock_stats[norm].is_dir

    def open_read(self, path: str) -> BinaryIO:
        data = self.read_bytes(path)
        return io.BytesIO(data)

    def open_write(self, path: str, append: bool = False) -> BinaryIO:
        class RemoteWriteStream(io.BytesIO):
            def __init__(stream_self, vfs_inst, p, app):
                super().__init__()
                stream_self.vfs = vfs_inst
                stream_self.p = p
                stream_self.app = app
            def close(stream_self):
                content = stream_self.getvalue()
                super().close()
                stream_self.vfs.write_bytes(stream_self.p, content, append=stream_self.app)
        return RemoteWriteStream(self, path, append)

    def read_bytes(self, path: str, length: int = -1, offset: int = 0) -> bytes:
        norm = posixpath.normpath("/" + path.lstrip("/"))
        if norm not in self._mock_data:
            raise FileNotFoundError(f"File not found: {norm}")
        data = self._mock_data[norm]
        if offset > 0:
            data = data[offset:]
        if length >= 0:
            data = data[:length]
        return data

    def write_bytes(self, path: str, data: bytes, append: bool = False) -> int:
        norm = posixpath.normpath("/" + path.lstrip("/"))
        if append and norm in self._mock_data:
            data = self._mock_data[norm] + data
        self._mock_data[norm] = data
        self._mock_stats[norm] = FileStat(
            name=posixpath.basename(norm),
            path=norm,
            is_dir=False,
            size=len(data),
            mode=0o644,
        )
        return len(data)

    def make_dir(self, path: str, parents: bool = True) -> None:
        norm = posixpath.normpath("/" + path.lstrip("/"))
        self._mock_stats[norm] = FileStat(
            name=posixpath.basename(norm),
            path=norm,
            is_dir=True,
            mode=0o755,
        )

    def remove_file(self, path: str) -> None:
        norm = posixpath.normpath("/" + path.lstrip("/"))
        if norm in self._mock_data:
            del self._mock_data[norm]
        if norm in self._mock_stats:
            del self._mock_stats[norm]

    def remove_dir(self, path: str, recursive: bool = False) -> None:
        norm = posixpath.normpath("/" + path.lstrip("/"))
        if norm in self._mock_stats:
            del self._mock_stats[norm]

    def rename(self, src: str, dst: str) -> None:
        src_norm = posixpath.normpath("/" + src.lstrip("/"))
        dst_norm = posixpath.normpath("/" + dst.lstrip("/"))
        if src_norm in self._mock_data:
            self._mock_data[dst_norm] = self._mock_data.pop(src_norm)
        if src_norm in self._mock_stats:
            st = self._mock_stats.pop(src_norm)
            st.path = dst_norm
            st.name = posixpath.basename(dst_norm)
            self._mock_stats[dst_norm] = st
