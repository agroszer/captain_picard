"""Tests for pycommander.actions and pycommander.keybindings."""

import unittest
from pycommander.actions import Action, ActionContext, ActionRegistry
from pycommander.keybindings import Keymap, create_norton_keymap, create_vim_keymap


class TestActions(unittest.TestCase):
    def setUp(self):
        self.reg = ActionRegistry()

    def test_register_and_execute_simple(self):
        called = []

        @self.reg.register("test_act", title="Test Action")
        def my_action():
            called.append(True)
            return "done"

        self.assertIn("test_act", [a.id for a in self.reg.list_actions()])
        result = self.reg.execute("test_act")
        self.assertEqual(result, "done")
        self.assertEqual(called, [True])

    def test_register_with_context(self):
        @self.reg.register("ctx_act")
        def act_with_ctx(context: ActionContext, extra_val=10):
            return context.current_item + extra_val

        ctx = ActionContext(current_item=5)
        res = self.reg.execute("ctx_act", context=ctx, extra_val=20)
        self.assertEqual(res, 25)

    def test_action_object_registration(self):
        act = Action(id="manual", title="Manual Action", handler=lambda: "manual_res")
        self.reg.register_action(act)
        self.assertEqual(self.reg.execute("manual"), "manual_res")

    def test_unregister(self):
        @self.reg.register("temp")
        def temp():
            pass

        self.assertIsNotNone(self.reg.get("temp"))
        self.reg.unregister("temp")
        self.assertIsNone(self.reg.get("temp"))


class TestKeybindings(unittest.TestCase):
    def test_key_normalization(self):
        self.assertEqual(Keymap.normalize_key("Ctrl+C"), "ctrl+c")
        self.assertEqual(Keymap.normalize_key("SHIFT+alt+X"), "alt+shift+x")
        self.assertEqual(Keymap.normalize_sequence("ctrl+k ctrl+s"), "ctrl+k ctrl+s")

    def test_single_key_dispatch(self):
        km = Keymap()
        km.bind("f3", "view_file")
        status, binding = km.feed_key("F3")
        self.assertEqual(status, "match")
        self.assertIsNotNone(binding)
        self.assertEqual(binding.action_id, "view_file")

    def test_sequence_dispatch(self):
        km = Keymap()
        km.bind("g g", "go_home")
        status, binding = km.feed_key("g")
        self.assertEqual(status, "prefix")
        self.assertIsNone(binding)

        status, binding = km.feed_key("g")
        self.assertEqual(status, "match")
        self.assertIsNotNone(binding)
        self.assertEqual(binding.action_id, "go_home")

    def test_sequence_reset_on_mismatch(self):
        km = Keymap()
        km.bind("g g", "go_home")
        status, binding = km.feed_key("g")
        self.assertEqual(status, "prefix")

        status, binding = km.feed_key("x")
        self.assertEqual(status, "nomatch")
        self.assertIsNone(binding)

    def test_when_conditions(self):
        km = Keymap()
        km.bind("enter", "submit_form", when="form_open")
        status, binding = km.feed_key("enter", context_conditions={"form_open": False})
        self.assertEqual(status, "nomatch")

        status, binding = km.feed_key("enter", context_conditions={"form_open": True})
        self.assertEqual(status, "match")
        self.assertEqual(binding.action_id, "submit_form")

    def test_json_serialization(self):
        km = Keymap()
        km.bind("ctrl+a", "select_all", description="Select everything")
        km.bind("ctrl+d", "show_bookmarks")
        data_json = km.to_json()

        km2 = Keymap()
        km2.load_json(data_json)
        self.assertEqual(len(km2.bindings), 2)
        st, b = km2.feed_key("ctrl+a")
        self.assertEqual(st, "match")
        self.assertEqual(b.action_id, "select_all")

    def test_preset_keymaps(self):
        norton = create_norton_keymap()
        self.assertEqual(norton.get_binding_for_action("view_file"), "f3")
        self.assertEqual(norton.get_binding_for_action("switch_pane"), "tab")

        vim = create_vim_keymap()
        self.assertEqual(vim.get_binding_for_action("cursor_down"), "j")
        self.assertEqual(vim.get_binding_for_action("go_home"), "g g")


if __name__ == "__main__":
    unittest.main()
