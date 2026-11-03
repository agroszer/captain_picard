"""Keybinding management, key sequence parser, and keymap dispatcher."""

from __future__ import annotations
import configparser
import json
import os
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

    def load_ini(self, ini_content_or_path: str) -> None:
        """Loads keybindings from an INI file or INI string."""
        config = configparser.ConfigParser()
        if os.path.exists(ini_content_or_path):
            config.read(ini_content_or_path)
        else:
            config.read_string(ini_content_or_path)

        for section in config.sections():
            for key_seq, value in config.items(section):
                val_trimmed = value.strip()
                # If command is a shell script (e.g. starts with 'sh:', 'shell:' or contains template vars like ${...})
                if val_trimmed.startswith(("sh:", "shell:", "cmd:")) or "${" in val_trimmed:
                    from pycommander.shell_actions import register_shell_action
                    from pycommander.actions import registry as global_registry

                    cmd_template = val_trimmed
                    for prefix in ("sh:", "shell:", "cmd:"):
                        if cmd_template.startswith(prefix):
                            cmd_template = cmd_template[len(prefix):].strip()

                    action_id = f"shell_cmd_{abs(hash(cmd_template)) % 100000}"
                    register_shell_action(global_registry, action_id, cmd_template)
                    self.bind(key_sequence=key_seq, action_id=action_id)
                else:
                    self.bind(key_sequence=key_seq, action_id=val_trimmed)

    def to_ini(self) -> str:
        """Exports keybindings to INI string."""
        lines = ["[keybindings]\n"]
        for b in self.bindings:
            lines.append(f"{b.key_sequence} = {b.action_id}\n")
        return "".join(lines)


def load_keymap_from_ini(ini_path: str, name: str = "custom") -> Keymap:
    km = Keymap(name)
    km.load_ini(ini_path)
    return km


def create_norton_keymap() -> Keymap:
    """Default Norton Commander keybindings loaded from keybindings.ini."""
    km = Keymap("norton")
    ini_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "keybindings.ini")
    if os.path.exists(ini_path):
        km.load_ini(ini_path)
    elif os.path.exists("keybindings.ini"):
        km.load_ini("keybindings.ini")
    else:
        # Fallback inline INI definition
        ini_content = """
[navigation]
up = cursor_up
down = cursor_down
left = cursor_left
right = cursor_right
pageup = page_up
pagedown = page_down
home = go_home
end = go_end
tab = switch_pane
enter = open_selected
backspace = go_parent_dir

[function_keys]
f1 = show_help
f2 = show_user_menu
f3 = view_file
f4 = edit_file
f5 = copy_items
f6 = move_items
f7 = make_directory
f8 = delete_items
delete = delete_items
f9 = toggle_menu_bar
f10 = quit_app

[selection]
insert = toggle_selection
space = toggle_selection
+ = select_by_wildcard
- = deselect_by_wildcard
* = invert_selection
alt++ = select_all_same_ext
ctrl+r = refresh_view
ctrl+u = swap_panes
ctrl+o = toggle_split_orientation

[tabs]
ctrl+t = new_tab
ctrl+w = close_tab
ctrl+pgup = prev_tab
ctrl+pgdn = next_tab
ctrl+l = lock_tab

[features]
alt+f7 = find_files
ctrl+f = quick_filter
ctrl+d = show_bookmarks
ctrl+g = go_to_path
ctrl+s = sync_directories
ctrl+q = toggle_quick_view
ctrl+i = toggle_info_panel
ctrl+m = show_mounts
ctrl+e = compare_directories
"""
        km.load_ini(ini_content)
    return km


def create_vim_keymap() -> Keymap:
    """Vim-style keybindings preset loaded from keybindings_vim.ini."""
    km = create_norton_keymap()
    km.name = "vim"
    ini_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "keybindings_vim.ini")
    if os.path.exists(ini_path):
        km.load_ini(ini_path)
    elif os.path.exists("keybindings_vim.ini"):
        km.load_ini("keybindings_vim.ini")
    else:
        ini_content = """
[vim]
j = cursor_down
k = cursor_up
h = go_parent_dir
l = open_selected
g g = go_home
shift+g = go_end
v = toggle_selection
d d = delete_items
y y = copy_items
p = move_items
/ = quick_filter
q = quit_app
"""
        km.load_ini(ini_content)
    return km
