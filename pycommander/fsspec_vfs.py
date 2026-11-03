"""FSSpec adapter providing seamless Virtual Filesystem integration using PyFilesystem / fsspec."""

from __future__ import annotations
import os
from typing import BinaryIO, List, Optional
import fsspec
from pycommander.vfs import FileStat, VFS


class FSSpecVFS(VFS):
    """
    VFS provider backed by fsspec (Filesystem Spec), supporting local, s3, sftp, ftp, memory, zip, etc.
    """

    def __init__(self, url_or_fs: str, **storage_options):
        if isinstance(url_or_fs, fsspec.AbstractFileSystem):
            self.fs = url_or_fs
            self.root = "/"
        else:
            self.fs, self.root = fsspec.core.url_to_fs(url_or_fs, **storage_options)

    def normalize_path(self, path: str) -> str:
        if not path:
            return self.root or "/"
        return os.path.normpath(path)

    def list_dir(self, path: str) -> List[FileStat]:
        norm = self.normalize_path(path)
        entries: List[FileStat] = []
        try:
            items = self.fs.ls(norm, detail=True)
            for item in items:
                p = item["name"]
                name = os.path.basename(p.rstrip("/"))
                is_dir = item.get("type") == "directory"
                entries.append(
                    FileStat(
                        name=name,
                        path=p,
                        is_dir=is_dir,
                        size=item.get("size", 0),
                        mtime=item.get("mtime", 0.0) or 0.0,
                    )
                )
        except Exception as e:
            raise IOError(f"fsspec list_dir error: {e}")

        entries.sort(key=lambda x: (not x.is_dir, x.name.lower()))
        return entries

    def stat(self, path: str) -> FileStat:
        norm = self.normalize_path(path)
        info = self.fs.info(norm)
        return FileStat(
            name=os.path.basename(norm.rstrip("/")),
            path=norm,
            is_dir=(info.get("type") == "directory"),
            size=info.get("size", 0),
            mtime=info.get("mtime", 0.0) or 0.0,
        )

    def exists(self, path: str) -> bool:
        return self.fs.exists(self.normalize_path(path))

    def is_dir(self, path: str) -> bool:
        return self.fs.isdir(self.normalize_path(path))

    def open_read(self, path: str) -> BinaryIO:
        return self.fs.open(self.normalize_path(path), "rb")

    def open_write(self, path: str, append: bool = False) -> BinaryIO:
        mode = "ab" if append else "wb"
        return self.fs.open(self.normalize_path(path), mode)

    def read_bytes(self, path: str, length: int = -1, offset: int = 0) -> bytes:
        norm = self.normalize_path(path)
        with self.fs.open(norm, "rb") as f:
            if offset > 0:
                f.seek(offset)
            if length >= 0:
                return f.read(length)
            return f.read()

    def write_bytes(self, path: str, data: bytes, append: bool = False) -> int:
        norm = self.normalize_path(path)
        mode = "ab" if append else "wb"
        with self.fs.open(norm, mode) as f:
            return f.write(data)

    def make_dir(self, path: str, parents: bool = True) -> None:
        self.fs.makedirs(self.normalize_path(path), exist_ok=True)

    def remove_file(self, path: str) -> None:
        self.fs.rm_file(self.normalize_path(path))

    def remove_dir(self, path: str, recursive: bool = False) -> None:
        self.fs.rm(self.normalize_path(path), recursive=recursive)

    def rename(self, src: str, dst: str) -> None:
        self.fs.rename(self.normalize_path(src), self.normalize_path(dst))
