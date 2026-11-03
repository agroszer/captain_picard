"""Tests for FSSpec VFS integration."""

import os
import shutil
import tempfile
import unittest
from pycommander.fsspec_vfs import FSSpecVFS


class TestFSSpecVFS(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.vfs = FSSpecVFS(f"file://{self.test_dir}")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_memory_fs(self):
        mem_vfs = FSSpecVFS("memory://")
        mem_vfs.write_bytes("/test.txt", b"fsspec memory content")
        self.assertTrue(mem_vfs.exists("/test.txt"))
        self.assertEqual(mem_vfs.read_bytes("/test.txt"), b"fsspec memory content")
        items = mem_vfs.list_dir("/")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].name, "test.txt")

    def test_local_fsspec_ops(self):
        target = os.path.join(self.test_dir, "fsspec_file.txt")
        self.vfs.write_bytes(target, b"Local via fsspec")
        self.assertTrue(self.vfs.exists(target))
        self.assertEqual(self.vfs.read_bytes(target), b"Local via fsspec")
        st = self.vfs.stat(target)
        self.assertEqual(st.size, len(b"Local via fsspec"))


if __name__ == "__main__":
    unittest.main()
