"""Tests for Search Finder, Duplicate Finder, Directory Sync, and Side-by-Side Diff."""

import os
import shutil
import tempfile
import time
import unittest

from pycommander.vfs import LocalVFS
from pycommander.search import DuplicateFinder, FileFinder, SearchCriteria
from pycommander.diff_sync import DirectorySynchronizer, SideBySideFileDiff, SyncAction, SyncDirection


class TestSearchAndDiff(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.vfs = LocalVFS()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_file_finder_by_name_and_content(self):
        f1 = os.path.join(self.test_dir, "report_2023.txt")
        f2 = os.path.join(self.test_dir, "notes.md")
        f3 = os.path.join(self.test_dir, "image.png")

        self.vfs.write_bytes(f1, b"Key secret password in text")
        self.vfs.write_bytes(f2, b"Markdown info")
        self.vfs.write_bytes(f3, b"\x89PNG\r\n\x1a\n")

        finder = FileFinder(self.vfs)

        # Name search
        crit = SearchCriteria(name_pattern="*.txt")
        res = finder.search(self.test_dir, crit)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].name, "report_2023.txt")

        # Regex name search
        crit_re = SearchCriteria(name_pattern=r"re:report_\d{4}\.txt")
        res_re = finder.search(self.test_dir, crit_re)
        self.assertEqual(len(res_re), 1)

        # Content search
        crit_content = SearchCriteria(content_pattern="password")
        res_content = finder.search(self.test_dir, crit_content)
        self.assertEqual(len(res_content), 1)
        self.assertEqual(res_content[0].name, "report_2023.txt")

    def test_duplicate_finder(self):
        d1 = os.path.join(self.test_dir, "dir1")
        d2 = os.path.join(self.test_dir, "dir2")
        os.makedirs(d1, exist_ok=True)
        os.makedirs(d2, exist_ok=True)

        content = b"Duplicate file content byte for byte identical"
        f1 = os.path.join(d1, "file1.txt")
        f2 = os.path.join(d2, "file2.txt")
        f3 = os.path.join(d1, "unique.txt")

        self.vfs.write_bytes(f1, content)
        self.vfs.write_bytes(f2, content)
        self.vfs.write_bytes(f3, b"unique")

        dup_finder = DuplicateFinder(self.vfs)
        dups = dup_finder.find_duplicates([self.test_dir], match_by="hash")
        self.assertEqual(len(dups), 1)
        dup_list = next(iter(dups.values()))
        self.assertEqual(len(dup_list), 2)
        names = {x.name for x in dup_list}
        self.assertEqual(names, {"file1.txt", "file2.txt"})

    def test_directory_sync(self):
        left = os.path.join(self.test_dir, "left_sync")
        right = os.path.join(self.test_dir, "right_sync")
        os.makedirs(left, exist_ok=True)
        os.makedirs(right, exist_ok=True)

        # File in left only
        self.vfs.write_bytes(os.path.join(left, "left_only.txt"), b"left data")
        # File in right only
        self.vfs.write_bytes(os.path.join(right, "right_only.txt"), b"right data")

        sync = DirectorySynchronizer()
        items = sync.analyze(self.vfs, left, self.vfs, right, direction=SyncDirection.TWO_WAY)
        self.assertEqual(len(items), 2)

        acts = {item.rel_path: item.action for item in items}
        self.assertEqual(acts["left_only.txt"], SyncAction.COPY_TO_RIGHT)
        self.assertEqual(acts["right_only.txt"], SyncAction.COPY_TO_LEFT)

        # Execute sync
        sync.execute_sync(self.vfs, left, self.vfs, right, items)
        self.assertTrue(self.vfs.exists(os.path.join(right, "left_only.txt")))
        self.assertTrue(self.vfs.exists(os.path.join(left, "right_only.txt")))

    def test_side_by_side_diff(self):
        left_text = "line 1\nline 2 unchanged\nline 3 deleted\nline 4"
        right_text = "line 1\nline 2 unchanged\nline 3 inserted\nline 4"

        diff_lines = SideBySideFileDiff.compute_diff(left_text, right_text)
        self.assertTrue(len(diff_lines) >= 4)
        types = [d.diff_type for d in diff_lines]
        self.assertIn("same", types)
        self.assertIn("change", types)


if __name__ == "__main__":
    unittest.main()
