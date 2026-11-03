"""Keybinding management, key sequence parser, and keymap dispatcher."""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from pycommander.actions import ActionContext, ActionRegistry, registry as default_registry


@dataclass
class KeyBinding:
    """Represents a key combination mapped to an action."""
    key_sequence: str  # e.g., "ctrl+c", "alt+f", "f3", "g g", "shift+tab"
    action_id: str
    args: Dict[str, Any] = field(default_factory=dict)
    when: Optional[str] = None  # e.g. "panel_active", "input_focused", "tree_active"
    description: str = ""


class Keymap:
    """Manages keybindings and handles multi-key sequences (like Vim 'gg' or 'ctrl+k ctrl+s')."""

    def __init__(self, name: str = "default"):
        self.name = name
        self.bindings: List[KeyBinding] = []
        self._lookup: Dict[str, KeyBinding] = {}
        self._prefix_tree: Dict[str, Any] = {}
        self._current_sequence: List[str] = []

    @staticmethod
    def normalize_key(key: str) -> str:
        """Normalizes key names (e.g., 'CTRL+X' -> 'ctrl+x', 'Esc' -> 'escape', '+', 'alt++')."""
        key_str = key.strip()
        if key_str == "+":
            return "+"
        # If it ends with '+', like 'alt++', handle carefully
        if key_str.endswith("++"):
            prefix = key_str[:-2]
            parts = [p.strip().lower() for p in prefix.split("+") if p.strip()] + ["+"]
        else:
            parts = [p.strip().lower() for p in key_str.split("+") if p.strip()]

        modifiers = []
        base_key = ""
        for p in parts:
            if p in ("ctrl", "control"):
                modifiers.append("ctrl")
            elif p in ("alt", "meta", "opt", "option"):
                modifiers.append("alt")
            elif p in ("shift",):
                modifiers.append("shift")
            else:
                base_key = p

        mod_order = {"ctrl": 0, "alt": 1, "shift": 2}
        modifiers.sort(key=lambda m: mod_order.get(m, 99))
        if modifiers:
            return "+".join(modifiers + [base_key])
        return base_key

    @classmethod
    def normalize_sequence(cls, seq: str) -> str:
        """Normalizes a sequence like 'Ctrl+K Ctrl+S' or 'g g'."""
        subkeys = seq.strip().split()
        return " ".join(cls.normalize_key(k) for k in subkeys)

    def bind(
        self,
        key_sequence: str,
        action_id: str,
        args: Optional[Dict[str, Any]] = None,
        when: Optional[str] = None,
        description: str = "",
    ) -> None:
        normalized = self.normalize_sequence(key_sequence)
        # Remove any existing binding with the exact same sequence
        self.unbind(normalized)
        binding = KeyBinding(
            key_sequence=normalized,
            action_id=action_id,
            args=args or {},
            when=when,
            description=description,
        )
        self.bindings.append(binding)
        self._lookup[normalized] = binding
        self._rebuild_tree()

    def unbind(self, key_sequence: str) -> bool:
        normalized = self.normalize_sequence(key_sequence)
        if normalized in self._lookup:
            self.bindings = [b for b in self.bindings if b.key_sequence != normalized]
            del self._lookup[normalized]
            self._rebuild_tree()
            return True
        return False

    def _rebuild_tree(self) -> None:
        self._prefix_tree = {}
        for b in self.bindings:
            keys = b.key_sequence.split()
            node = self._prefix_tree
            for k in keys[:-1]:
                if k not in node:
                    node[k] = {}
                node = node[k]
            node[keys[-1]] = b

    def reset_sequence(self) -> None:
        self._current_sequence.clear()

    def feed_key(self, key: str, context_conditions: Optional[Dict[str, bool]] = None) -> Tuple[str, Optional[KeyBinding]]:
        """
        Feeds a single key stroke.
        Returns:
          ("match", binding) if a binding is matched.
          ("prefix", None) if key is part of a longer pending sequence.
          ("nomatch", None) if no binding matched (sequence resets).
        """
        norm_key = self.normalize_key(key)
        self._current_sequence.append(norm_key)

        node = self._prefix_tree
        for k in self._current_sequence:
            if isinstance(node, dict) and k in node:
                node = node[k]
            else:
                self.reset_sequence()
                return "nomatch", None

        if isinstance(node, KeyBinding):
            binding = node
            self.reset_sequence()
            # Check 'when' condition if any
            if binding.when and context_conditions:
                if not context_conditions.get(binding.when, True):
                    return "nomatch", None
            return "match", binding
        elif isinstance(node, dict):
            return "prefix", None
        else:
            self.reset_sequence()
            return "nomatch", None

    def get_binding_for_action(self, action_id: str) -> Optional[str]:
        for b in reversed(self.bindings):
            if b.action_id == action_id:
                return b.key_sequence
        return None

    def export_dict(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": b.key_sequence,
                "action": b.action_id,
                "args": b.args,
                "when": b.when,
                "description": b.description,
            }
            for b in self.bindings
        ]

    def load_dict(self, data: List[Dict[str, Any]]) -> None:
        self.bindings.clear()
        self._lookup.clear()
        self._prefix_tree.clear()
        self._current_sequence.clear()
        for item in data:
            self.bind(
                key_sequence=item["key"],
                action_id=item["action"],
                args=item.get("args"),
                when=item.get("when"),
                description=item.get("description", ""),
            )

    def load_json(self, json_str: str) -> None:
        data = json.loads(json_str)
        self.load_dict(data)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.export_dict(), indent=indent)


def create_norton_keymap() -> Keymap:
    """Default Norton Commander / Midnight Commander style keybindings."""
    km = Keymap("norton")
    # Navigation
    km.bind("up", "cursor_up")
    km.bind("down", "cursor_down")
    km.bind("left", "cursor_left")
    km.bind("right", "cursor_right")
    km.bind("pageup", "page_up")
    km.bind("pagedown", "page_down")
    km.bind("home", "go_home")
    km.bind("end", "go_end")
    km.bind("tab", "switch_pane")
    km.bind("enter", "open_selected")
    km.bind("backspace", "go_parent_dir")

    # Function Keys (Standard Norton / MC)
    km.bind("f1", "show_help")
    km.bind("f2", "show_user_menu")
    km.bind("f3", "view_file")
    km.bind("f4", "edit_file")
    km.bind("f5", "copy_items")
    km.bind("f6", "move_items")
    km.bind("f7", "make_directory")
    km.bind("f8", "delete_items")
    km.bind("delete", "delete_items")
    km.bind("f9", "toggle_menu_bar")
    km.bind("f10", "quit_app")

    # Selection
    km.bind("insert", "toggle_selection")
    km.bind("space", "toggle_selection")
    km.bind("+", "select_by_wildcard")
    km.bind("-", "deselect_by_wildcard")
    km.bind("*", "invert_selection")
    km.bind("alt++", "select_all_same_ext")
    km.bind("ctrl+r", "refresh_view")
    km.bind("ctrl+u", "swap_panes")
    km.bind("ctrl+o", "toggle_split_orientation")

    # Tabs
    km.bind("ctrl+t", "new_tab")
    km.bind("ctrl+w", "close_tab")
    km.bind("ctrl+pgup", "prev_tab")
    km.bind("ctrl+pgdn", "next_tab")
    km.bind("ctrl+l", "lock_tab")

    # Search & Diff
    km.bind("alt+f7", "find_files")
    km.bind("ctrl+f", "quick_filter")
    km.bind("ctrl+d", "show_bookmarks")
    km.bind("ctrl+g", "go_to_path")
    km.bind("ctrl+s", "sync_directories")
    km.bind("ctrl+q", "toggle_quick_view")
    km.bind("ctrl+i", "toggle_info_panel")
    km.bind("ctrl+m", "show_mounts")
    km.bind("ctrl+e", "compare_directories")

    return km


def create_vim_keymap() -> Keymap:
    """Vim-style keybindings preset."""
    km = create_norton_keymap()
    km.name = "vim"
    km.bind("j", "cursor_down")
    km.bind("k", "cursor_up")
    km.bind("h", "go_parent_dir")
    km.bind("l", "open_selected")
    km.bind("g g", "go_home")
    km.bind("shift+g", "go_end")
    km.bind("v", "toggle_selection")
    km.bind("d d", "delete_items")
    km.bind("y y", "copy_items")
    km.bind("p", "move_items")
    km.bind("/", "quick_filter")
    km.bind(":", "open_command_palette")
    km.bind("q", "quit_app")
    return km
