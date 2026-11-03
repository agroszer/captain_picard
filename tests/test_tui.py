"""Tests for Textual UI integration and Plugin system."""

import os
import shutil
import tempfile
import unittest

from pycommander.plugins import PluginManager
from pycommander.textual_ui import PyCommanderApp, load_theme_colors
from pycommander.actions import ActionRegistry
from pycommander.vfs import FileStat, LocalVFS


class TestTextualUI(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.sub1 = os.path.join(self.test_dir, "sub1")
        self.sub2 = os.path.join(self.test_dir, "sub2")
        os.makedirs(self.sub1, exist_ok=True)
        os.makedirs(self.sub2, exist_ok=True)

        with open(os.path.join(self.sub1, "hello.txt"), "w") as f:
            f.write("Hello from test")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_app_initialization(self):
        app = PyCommanderApp(left_path=self.sub1, right_path=self.sub2)
        self.assertEqual(app.panes.active_pane_id, "left")
        self.assertEqual(app.panes.left.active_tab.path, os.path.abspath(self.sub1))
        self.assertEqual(app.panes.right.active_tab.path, os.path.abspath(self.sub2))
        self.assertTrue(len(app.keymap.bindings) > 0)

    def test_theme_colors_loader(self):
        colors = load_theme_colors("theme.ini")
        self.assertIn("background", colors)
        self.assertIn("foreground", colors)
        self.assertEqual(colors["background"], "blue")

    def test_plugin_and_file_associations(self):
        reg = ActionRegistry()
        pm = PluginManager(reg)
        opened = []

        pm.add_association("custom", handler=lambda path, vfs: opened.append(path))
        st = FileStat(name="test.custom", path="/dummy/test.custom")
        res = pm.open_file(st, LocalVFS())
        self.assertTrue(res)
        self.assertEqual(opened, ["/dummy/test.custom"])


if __name__ == "__main__":
    unittest.main()
