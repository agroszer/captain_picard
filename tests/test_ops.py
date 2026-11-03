"""Tests for File Operations, Overwrite Policies, and Background Queue Manager."""

import os
import shutil
import tempfile
import time
import unittest

from pycommander.vfs import LocalVFS
from pycommander.ops import FileOperations, OverwritePolicy
from pycommander.queue_manager import TransferQueueManager


class TestOps(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.vfs = LocalVFS()
        self.ops = FileOperations()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_copy_and_preserve_attributes(self):
        src = os.path.join(self.test_dir, "src.txt")
        dst = os.path.join(self.test_dir, "dst.txt")
        self.vfs.write_bytes(src, b"Copy content test")
        self.vfs.set_attributes(src, mode=0o755, mtime=1500000000.0)

        success = self.ops.copy_file(self.vfs, src, self.vfs, dst)
        self.assertTrue(success)
        self.assertTrue(self.vfs.exists(dst))
        self.assertEqual(self.vfs.read_bytes(dst), b"Copy content test")

        dst_stat = self.vfs.stat(dst)
        self.assertEqual(int(dst_stat.mtime), 1500000000)

    def test_overwrite_policies(self):
        src = os.path.join(self.test_dir, "src.txt")
        dst = os.path.join(self.test_dir, "dst.txt")

        # Test SKIP
        self.vfs.write_bytes(src, b"new content")
        self.vfs.write_bytes(dst, b"old content")
        res = self.ops.copy_file(self.vfs, src, self.vfs, dst, policy=OverwritePolicy.SKIP)
        self.assertFalse(res)
        self.assertEqual(self.vfs.read_bytes(dst), b"old content")

        # Test OVERWRITE
        res = self.ops.copy_file(self.vfs, src, self.vfs, dst, policy=OverwritePolicy.OVERWRITE)
        self.assertTrue(res)
        self.assertEqual(self.vfs.read_bytes(dst), b"new content")

        # Test AUTO_RENAME
        self.vfs.write_bytes(dst, b"keep this")
        res = self.ops.copy_file(self.vfs, src, self.vfs, dst, policy=OverwritePolicy.AUTO_RENAME)
        self.assertTrue(res)
        renamed = os.path.join(self.test_dir, "dst_1.txt")
        self.assertTrue(self.vfs.exists(renamed))
        self.assertEqual(self.vfs.read_bytes(renamed), b"new content")

        # Test APPEND
        self.vfs.write_bytes(src, b" added")
        res = self.ops.copy_file(self.vfs, src, self.vfs, dst, policy=OverwritePolicy.APPEND)
        self.assertTrue(res)
        self.assertEqual(self.vfs.read_bytes(dst), b"keep this added")

    def test_move_and_delete(self):
        src = os.path.join(self.test_dir, "move_me.txt")
        dst = os.path.join(self.test_dir, "moved.txt")
        self.vfs.write_bytes(src, b"move payload")

        self.ops.move_file(self.vfs, src, self.vfs, dst)
        self.assertFalse(self.vfs.exists(src))
        self.assertTrue(self.vfs.exists(dst))

        self.ops.delete_item(self.vfs, dst)
        self.assertFalse(self.vfs.exists(dst))

    def test_background_queue_manager(self):
        mgr = TransferQueueManager(self.ops)
        try:
            src = os.path.join(self.test_dir, "queue_src.txt")
            dst = os.path.join(self.test_dir, "queue_dst.txt")
            self.vfs.write_bytes(src, b"background payload")

            task = mgr.enqueue("copy", self.vfs, src, self.vfs, dst)

            # Wait for completion
            deadline = time.time() + 3.0
            while task.status not in ("completed", "failed") and time.time() < deadline:
                time.sleep(0.05)

            self.assertEqual(task.status, "completed")
            self.assertTrue(self.vfs.exists(dst))
            self.assertEqual(self.vfs.read_bytes(dst), b"background payload")
        finally:
            mgr.stop()

    def test_queue_pause_and_resume(self):
        mgr = TransferQueueManager(self.ops)
        try:
            mgr.pause()
            self.assertTrue(mgr.is_paused())

            src = os.path.join(self.test_dir, "pause_src.txt")
            dst = os.path.join(self.test_dir, "pause_dst.txt")
            self.vfs.write_bytes(src, b"paused data")

            task = mgr.enqueue("copy", self.vfs, src, self.vfs, dst)
            time.sleep(0.2)
            # Should be pending or paused, not completed yet
            self.assertIn(task.status, ("pending", "paused", "running"))

            mgr.resume()
            self.assertFalse(mgr.is_paused())

            deadline = time.time() + 3.0
            while task.status != "completed" and time.time() < deadline:
                time.sleep(0.05)
            self.assertEqual(task.status, "completed")
            self.assertTrue(self.vfs.exists(dst))
        finally:
            mgr.stop()


if __name__ == "__main__":
    unittest.main()
