"""Tests for Shell Action Template Expansion and Keybinding INI Execution."""

import os
import shutil
import tempfile
import unittest

from pycommander.actions import ActionContext, ActionRegistry
from pycommander.keybindings import Keymap
from pycommander.panes import DualPaneManager, FolderTab
from pycommander.shell_actions import ShellTemplateExpander, execute_shell_action, register_shell_action
from pycommander.vfs import FileStat, LocalVFS


class TestShellActions(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.vfs = LocalVFS()
        self.f1 = os.path.join(self.test_dir, "document.txt")
        self.f2 = os.path.join(self.test_dir, "archive.tar")
        self.vfs.write_bytes(self.f1, b"hello")
        self.vfs.write_bytes(self.f2, b"tar data")

        self.st1 = self.vfs.stat(self.f1)
        self.st2 = self.vfs.stat(self.f2)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_template_expansion(self):
        tab = FolderTab(path=self.test_dir, vfs=self.vfs)
        ctx = ActionContext(
            current_item=self.st1,
            selected_items=[self.st1, self.st2],
            active_tab=tab,
        )

        expanded = ShellTemplateExpander.expand("echo file=${file} name=${name} ext=${ext} count=${count}", ctx)
        self.assertIn(f"file={self.f1}", expanded)
        self.assertIn("name=document.txt", expanded)
        self.assertIn("ext=txt", expanded)
        self.assertIn("count=2", expanded)

        # Extended variables: current_dir, full_fname, just_fname, stem, perms, user
        expanded_rich = ShellTemplateExpander.expand("cd ${current_dir} && run ${full_fname} --name ${just_fname} --stem ${stem}", ctx)
        self.assertIn(f"cd {self.test_dir}", expanded_rich)
        self.assertIn(f"--name document.txt", expanded_rich)
        self.assertIn(f"--stem document", expanded_rich)

        # Selected items expansion
        sel_expanded = ShellTemplateExpander.expand("tar -cvf backup.tar ${selected}", ctx)
        self.assertIn(self.f1, sel_expanded)
        self.assertIn(self.f2, sel_expanded)

    def test_shell_action_execution(self):
        reg = ActionRegistry()
        out_file = os.path.join(self.test_dir, "output.txt")
        cmd = f"echo ${{name}} > {out_file}"

        act = register_shell_action(reg, "write_name", cmd)
        tab = FolderTab(path=self.test_dir, vfs=self.vfs)
        ctx = ActionContext(current_item=self.st1, active_tab=tab)

        code = act.execute(context=ctx)
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(out_file))
        with open(out_file, "r") as f:
            content = f.read().strip()
        self.assertEqual(content, "document.txt")

    def test_ini_shell_action_binding(self):
        ini_content = """
[custom_scripts]
ctrl+x = sh: echo ${name} > custom_test.txt
"""
        km = Keymap("test_shell")
        km.load_ini(ini_content)
        status, binding = km.feed_key("ctrl+x")
        self.assertEqual(status, "match")
        self.assertIsNotNone(binding)
        self.assertTrue(binding.action_id.startswith("shell_cmd_"))


if __name__ == "__main__":
    unittest.main()
