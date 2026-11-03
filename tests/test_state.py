"""Tests for StateManager persistence in ~/.config/pycommander.ini."""

import os
import shutil
import tempfile
import unittest

from pycommander.panes import DualPaneManager
from pycommander.selection import SelectionManager
from pycommander.state import StateManager


class TestStateManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.test_dir, "pycommander.ini")
        self.state_mgr = StateManager(config_path=self.state_file)

        self.left_dir = os.path.join(self.test_dir, "left_pane")
        self.right_dir = os.path.join(self.test_dir, "right_pane")
        os.makedirs(self.left_dir, exist_ok=True)
        os.makedirs(self.right_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_save_and_restore_state(self):
        panes = DualPaneManager(initial_path_left=self.left_dir, initial_path_right=self.right_dir)
        left_sel = SelectionManager()
        right_sel = SelectionManager()

        # Add a tab and selection
        new_tab_path = os.path.join(self.test_dir, "extra_tab")
        os.makedirs(new_tab_path, exist_ok=True)
        panes.left.new_tab(path=new_tab_path)
        panes.switch_pane()
        self.assertEqual(panes.active_pane_id, "right")

        f_sel = os.path.join(self.left_dir, "selected_file.txt")
        left_sel.select(f_sel)

        # Save state
        self.state_mgr.save_state(panes, left_sel, right_sel)
        self.assertTrue(os.path.exists(self.state_file))

        # Restore into clean panes
        panes_new = DualPaneManager(initial_path_left="/", initial_path_right="/")
        left_sel_new = SelectionManager()
        right_sel_new = SelectionManager()

        restored = self.state_mgr.restore_to_app(panes_new, left_sel_new, right_sel_new)
        self.assertTrue(restored)

        self.assertEqual(panes_new.active_pane_id, "right")
        self.assertEqual(len(panes_new.left.tabs), 2)
        self.assertEqual(panes_new.left.tabs[1].path, os.path.abspath(new_tab_path))
        self.assertTrue(left_sel_new.is_selected(f_sel))


if __name__ == "__main__":
    unittest.main()
