"""Tests for Dual-Pane Layout, Tabs, Tree, Quick View, and Comparison mode."""

import os
import shutil
import tempfile
import unittest

from pycommander.vfs import LocalVFS
from pycommander.panes import DualPaneManager, PaneMode, SplitOrientation
from pycommander.tabs import FolderTab
from pycommander.tree import DirectoryTree
from pycommander.quick_view import FileInfoGenerator, QuickViewer


class TestPanesAndLayout(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.left_dir = os.path.join(self.test_dir, "left")
        self.right_dir = os.path.join(self.test_dir, "right")
        os.makedirs(self.left_dir, exist_ok=True)
        os.makedirs(self.right_dir, exist_ok=True)

        with open(os.path.join(self.left_dir, "common.txt"), "wb") as f:
            f.write(b"Same content")
        with open(os.path.join(self.right_dir, "common.txt"), "wb") as f:
            f.write(b"Same content")
        with open(os.path.join(self.left_dir, "left_only.txt"), "wb") as f:
            f.write(b"Left only")
        with open(os.path.join(self.right_dir, "diff_size.txt"), "wb") as f:
            f.write(b"1234567890")
        with open(os.path.join(self.left_dir, "diff_size.txt"), "wb") as f:
            f.write(b"123")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_dual_pane_switch_and_swap(self):
        mgr = DualPaneManager(self.left_dir, self.right_dir)
        self.assertEqual(mgr.active_pane_id, "left")
        mgr.switch_pane()
        self.assertEqual(mgr.active_pane_id, "right")
        mgr.switch_pane()
        self.assertEqual(mgr.active_pane_id, "left")

        # Orientation toggle
        self.assertEqual(mgr.orientation, SplitOrientation.VERTICAL)
        mgr.toggle_split_orientation()
        self.assertEqual(mgr.orientation, SplitOrientation.HORIZONTAL)

        # Swap
        left_path = mgr.left.active_tab.path
        right_path = mgr.right.active_tab.path
        mgr.swap_panes()
        self.assertEqual(mgr.left.active_tab.path, right_path)
        self.assertEqual(mgr.right.active_tab.path, left_path)

    def test_tabs_management(self):
        vfs = LocalVFS()
        pane = DualPaneManager(self.left_dir, self.right_dir).left
        self.assertEqual(len(pane.tabs), 1)

        # New tab
        new_tab = pane.new_tab(self.test_dir)
        self.assertEqual(len(pane.tabs), 2)
        self.assertEqual(pane.active_tab.path, vfs.normalize_path(self.test_dir))

        # Duplicate tab
        dup = pane.duplicate_tab()
        self.assertEqual(len(pane.tabs), 3)
        self.assertEqual(dup.path, pane.active_tab.path)

        # Lock tab
        self.assertFalse(pane.active_tab.is_locked)
        pane.toggle_tab_lock()
        self.assertTrue(pane.active_tab.is_locked)
        # Attempt navigate while locked
        nav_success = pane.active_tab.navigate_to(self.left_dir)
        self.assertFalse(nav_success)

        # Close tab
        closed = pane.close_tab()
        self.assertTrue(closed)
        self.assertEqual(len(pane.tabs), 2)

    def test_tab_history(self):
        vfs = LocalVFS()
        tab = FolderTab(path=self.test_dir, vfs=vfs)
        tab.navigate_to(self.left_dir)
        tab.navigate_to(self.right_dir)
        self.assertTrue(tab.can_go_back())
        self.assertFalse(tab.can_go_forward())

        tab.go_back()
        self.assertEqual(tab.path, vfs.normalize_path(self.left_dir))
        self.assertTrue(tab.can_go_forward())

        tab.go_forward()
        self.assertEqual(tab.path, vfs.normalize_path(self.right_dir))

    def test_directory_tree_view(self):
        vfs = LocalVFS()
        tree = DirectoryTree(self.test_dir, vfs)
        nodes = tree.get_visible_nodes()
        self.assertTrue(len(nodes) >= 1)
        tree.toggle_current()
        expanded_nodes = tree.get_visible_nodes()
        self.assertTrue(len(expanded_nodes) >= len(nodes))

    def test_quick_view_and_file_info(self):
        vfs = LocalVFS()
        txt_path = os.path.join(self.left_dir, "common.txt")
        preview = QuickViewer.generate_preview(vfs, txt_path)
        self.assertIn("Same content", preview[0])

        info = FileInfoGenerator.generate_info(vfs, txt_path)
        self.assertTrue(any("common.txt" in line for line in info))
        self.assertTrue(any("Size:" in line for line in info))

        # Hex preview test
        bin_path = os.path.join(self.left_dir, "binary.dat")
        with open(bin_path, "wb") as f:
            f.write(bytes(range(32)))
        hex_prev = QuickViewer.generate_preview(vfs, bin_path)
        self.assertIn("--- HEX VIEW ---", hex_prev[0])

    def test_dual_pane_comparison_mode(self):
        mgr = DualPaneManager(self.left_dir, self.right_dir)
        diffs = mgr.compare_directories()
        self.assertEqual(diffs.get("left:left_only.txt"), "left_only")
        self.assertEqual(diffs.get("left:diff_size.txt"), "diff_size")
        self.assertEqual(diffs.get("right:diff_size.txt"), "diff_size")
        self.assertEqual(diffs.get("left:common.txt"), "identical")


if __name__ == "__main__":
    unittest.main()
