"""Quick View and File Info generator."""

from __future__ import annotations
import os
import stat
from typing import List, Optional, Tuple
from pycommander.vfs import FileStat, VFS


class QuickViewer:
    """Generates preview content for text, hex/binary, and structured documents."""

    @staticmethod
    def is_binary_string(bytes_data: bytes) -> bool:
        """Determines if a byte slice contains non-text/null bytes."""
        text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
        return bool(bytes_data.translate(None, text_chars))

    @classmethod
    def generate_hex_view(cls, data: bytes, max_bytes: int = 1024) -> List[str]:
        lines = []
        slice_data = data[:max_bytes]
        for offset in range(0, len(slice_data), 16):
            chunk = slice_data[offset : offset + 16]
            hex_part = " ".join(f"{b:02x}" for b in chunk)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            lines.append(f"{offset:08x}  {hex_part:<48}  |{ascii_part}|")
        if len(data) > max_bytes:
            lines.append(f"... ({len(data) - max_bytes} more bytes)")
        return lines

    @classmethod
    def generate_preview(cls, vfs: VFS, path: str, max_lines: int = 50) -> List[str]:
        if not vfs.exists(path):
            return [f"File not found: {path}"]
        if vfs.is_dir(path):
            try:
                entries = vfs.list_dir(path)
                lines = [f"Directory: {path}", f"Total items: {len(entries)}", ""]
                for e in entries[:max_lines]:
                    prefix = "[DIR] " if e.is_dir else "      "
                    lines.append(f"{prefix}{e.name:<30} {e.formatted_size:>10}")
                return lines
            except Exception as e:
                return [f"Unable to read directory: {e}"]

        try:
            sample = vfs.read_bytes(path, length=4096)
            if not sample:
                return ["<Empty file>"]

            if cls.is_binary_string(sample):
                return ["--- HEX VIEW ---"] + cls.generate_hex_view(sample)
            else:
                try:
                    text = sample.decode("utf-8", errors="replace")
                except Exception:
                    text = sample.decode("latin-1", errors="replace")
                return text.splitlines()[:max_lines]
        except Exception as e:
            return [f"Error reading file preview: {e}"]


class FileInfoGenerator:
    """Generates partition free space, inode stats, permissions, and file metadata."""

    @staticmethod
    def generate_info(vfs: VFS, path: str) -> List[str]:
        lines = []
        try:
            st = vfs.stat(path)
            lines.append(f"Name:        {st.name}")
            lines.append(f"Full Path:   {st.path}")
            lines.append(f"Type:        {'Directory' if st.is_dir else 'Regular File'}")
            if st.is_symlink:
                lines.append(f"Symlink to:  {st.symlink_target}")
            lines.append(f"Size:        {st.size:,} bytes ({st.formatted_size})")
            lines.append(f"Permissions: {st.permissions_str} ({oct(st.mode)})")
            lines.append(f"Owner/Group: {st.user}:{st.group} (uid: {st.uid}, gid: {st.gid})")
            lines.append(f"Modified:    {st.formatted_mtime}")

            total, used, free = vfs.get_free_space(path)
            if total > 0:
                lines.append("-" * 35)
                lines.append("Filesystem Partition Stats:")
                def fmt(b):
                    for u in ["B", "KB", "MB", "GB", "TB"]:
                        if b < 1024 or u == "TB":
                            return f"{b:.1f} {u}"
                        b /= 1024.0
                    return f"{b} B"
                lines.append(f"Total Space: {fmt(total)}")
                lines.append(f"Used Space:  {fmt(used)} ({used/total*100:.1f}%)")
                lines.append(f"Free Space:  {fmt(free)} ({free/total*100:.1f}%)")
        except Exception as e:
            lines.append(f"Failed to query file info: {e}")
        return lines
