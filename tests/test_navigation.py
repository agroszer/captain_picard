"""Tests for Selection and Navigation components."""

import os
import unittest
from pycommander.vfs import FileStat
from pycommander.selection import SelectionManager
from pycommander.navigation import BookmarkManager, BreadcrumbNavigator, VolumeManager


class TestSelectionAndNavigation(unittest.TestCase):
    def test_selection_wildcards(self):
        items = [
            FileStat(name="app.ts", path="/app/app.ts"),
            FileStat(name="app.tsx", path="/app/app.tsx"),
            FileStat(name="main.py", path="/app/main.py"),
            FileStat(name="styles.css", path="/app/styles.css"),
        ]

        sm = SelectionManager()
        # Wildcard selection with multiple patterns
        count = sm.select_by_wildcard("*.ts;*.tsx", items, is_select=True)
        self.assertEqual(count, 2)
        self.assertTrue(sm.is_selected("/app/app.ts"))
        self.assertTrue(sm.is_selected("/app/app.tsx"))
        self.assertFalse(sm.is_selected("/app/main.py"))

        # Invert selection
        sm.invert(items)
        self.assertFalse(sm.is_selected("/app/app.ts"))
        self.assertTrue(sm.is_selected("/app/main.py"))
        self.assertTrue(sm.is_selected("/app/styles.css"))

        # Restore previous selection
        sm.restore_previous()
        self.assertTrue(sm.is_selected("/app/app.ts"))
        self.assertFalse(sm.is_selected("/app/main.py"))

        # Select all same extension
        sm.deselect_all()
        sm.select_all_same_extension(items[0], items)  # items[0] is app.ts
        self.assertTrue(sm.is_selected("/app/app.ts"))
        self.assertFalse(sm.is_selected("/app/app.tsx"))

    def test_regex_selection(self):
        items = [
            FileStat(name="data_2020.csv", path="/d/data_2020.csv"),
            FileStat(name="data_2021.csv", path="/d/data_2021.csv"),
            FileStat(name="notes.txt", path="/d/notes.txt"),
        ]
        sm = SelectionManager()
        sm.select_by_wildcard(r"re:data_\d{4}\.csv", items)
        self.assertTrue(sm.is_selected("/d/data_2020.csv"))
        self.assertTrue(sm.is_selected("/d/data_2021.csv"))
        self.assertFalse(sm.is_selected("/d/notes.txt"))

    def test_bookmarks(self):
        bm = BookmarkManager()
        self.assertTrue(len(bm.bookmarks) >= 2)
        added = bm.add_bookmark("My Project", "/projects/my-app", hotkey="p")
        self.assertEqual(bm.get_by_hotkey("p"), added)

        # Remove
        idx = bm.bookmarks.index(added)
        self.assertTrue(bm.remove_bookmark(idx))
        self.assertIsNone(bm.get_by_hotkey("p"))

    def test_breadcrumbs(self):
        crumbs = BreadcrumbNavigator.parse_breadcrumbs("/home/user/workspace/src")
        self.assertEqual(crumbs[0], ("/", "/"))
        self.assertEqual(crumbs[1], ("home", "/home"))
        self.assertEqual(crumbs[2], ("user", "/home/user"))
        self.assertEqual(crumbs[-1], ("src", "/home/user/workspace/src"))

    def test_volumes(self):
        mounts = VolumeManager.get_mounts()
        self.assertTrue(len(mounts) >= 1)
        self.assertTrue(any(m["mountpoint"] == "/" for m in mounts))


if __name__ == "__main__":
    unittest.main()
