"""Tests for TUI, Terminal Renderer, and Plugin system."""

import os
import shutil
import tempfile
import unittest

from pycommander.plugins import PluginManager
from pycommander.terminal import ScreenBuffer
from pycommander.tui import PyCommanderApp
from pycommander.actions import ActionRegistry
from pycommander.vfs import FileStat, LocalVFS


class TestTUIAndTerminal(unittest.TestCase):
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

    def test_screen_buffer_rendering(self):
        buf = ScreenBuffer(width=40, height=10)
        buf.draw_box(0, 0, 40, 10, title="Test Box")
        lines = buf.render_plain_lines()
        self.assertEqual(len(lines), 10)
        self.assertIn("Test Box", lines[0])
        self.assertTrue(lines[0].startswith("╔"))
        self.assertTrue(lines[-1].endswith("╝"))

    def test_app_initialization_and_headless_render(self):
        app = PyCommanderApp(left_path=self.sub1, right_path=self.sub2, width=80, height=24)
        output = app.render()
        plain_lines = app.buffer.render_plain_lines()

        self.assertEqual(len(plain_lines), 24)
        # Check Top menu bar
        self.assertIn("Left", plain_lines[0])
        # Check bottom button bar
        self.assertIn("1Help", plain_lines[-1])
        self.assertIn("10Quit", plain_lines[-1])

    def test_key_handling_actions(self):
        app = PyCommanderApp(left_path=self.sub1, right_path=self.sub2, width=80, height=24)
        self.assertEqual(app.panes.active_pane_id, "left")

        # Tab switches pane
        handled = app.handle_key("tab")
        self.assertTrue(handled)
        self.assertEqual(app.panes.active_pane_id, "right")

        # F1 opens Help dialog
        app.handle_key("f1")
        self.assertIsNotNone(app.active_dialog)
        self.assertIn("Help", app.active_dialog["title"])

        # Escape closes dialog
        app.handle_key("escape")
        self.assertIsNone(app.active_dialog)

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
