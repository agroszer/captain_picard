"""Optional Textual UI implementation for PyCommander."""

from __future__ import annotations
import os
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DirectoryTree, Footer, Header, Label, ListItem, ListView, Static
from pycommander.actions import ActionContext, registry as default_registry
from pycommander.keybindings import create_norton_keymap
from pycommander.panes import DualPaneManager
from pycommander.vfs import LocalVFS


class PyCommanderTextualApp(App):
    """Textual TUI for PyCommander."""

    CSS = """
    Screen {
        background: $primary-darken-3;
    }
    #panes-container {
        height: 1fr;
    }
    .pane {
        width: 1fr;
        border: solid $accent;
        padding: 0 1;
        background: $surface;
    }
    .active-pane {
        border: double $success;
    }
    .pane-header {
        dock: top;
        background: $accent-darken-2;
        color: $text;
        text-style: bold;
        padding: 0 1;
    }
    #status-bar {
        dock: bottom;
        background: $surface-darken-1;
        color: $text-muted;
        height: 1;
        padding: 0 1;
    }
    """

    BINDINGS = [
        ("tab", "switch_pane", "Switch Pane"),
        ("f1", "help", "Help"),
        ("f3", "view_file", "View"),
        ("f5", "copy_file", "Copy"),
        ("f6", "move_file", "Move"),
        ("f7", "mkdir", "Mkdir"),
        ("f8", "delete_file", "Delete"),
        ("f10", "quit", "Quit"),
    ]

    def __init__(self, left_path: str = ".", right_path: str = ".", **kwargs):
        super().__init__(**kwargs)
        self.panes_mgr = DualPaneManager(initial_path_left=left_path, initial_path_right=right_path)
        self.actions = default_registry

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="panes-container"):
            with Vertical(id="left-pane", classes="pane active-pane"):
                yield Label(self.panes_mgr.left.active_tab.path, id="left-title", classes="pane-header")
                yield ListView(id="left-list")
            with Vertical(id="right-pane", classes="pane"):
                yield Label(self.panes_mgr.right.active_tab.path, id="right-title", classes="pane-header")
                yield ListView(id="right-list")
        yield Label("Ready. Press Tab to switch panes, F1 for Help, F10 to Quit.", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_pane_lists()

    def refresh_pane_lists(self) -> None:
        left_list = self.query_one("#left-list", ListView)
        left_list.clear()
        for item in self.panes_mgr.left.get_items():
            prefix = "[DIR] " if item.is_dir else "      "
            left_list.append(ListItem(Label(f"{prefix}{item.name} ({item.formatted_size})")))

        right_list = self.query_one("#right-list", ListView)
        right_list.clear()
        for item in self.panes_mgr.right.get_items():
            prefix = "[DIR] " if item.is_dir else "      "
            right_list.append(ListItem(Label(f"{prefix}{item.name} ({item.formatted_size})")))

    def action_switch_pane(self) -> None:
        self.panes_mgr.switch_pane()
        left_p = self.query_one("#left-pane", Vertical)
        right_p = self.query_one("#right-pane", Vertical)
        if self.panes_mgr.active_pane_id == "left":
            left_p.add_class("active-pane")
            right_p.remove_class("active-pane")
        else:
            right_p.add_class("active-pane")
            left_p.remove_class("active-pane")
