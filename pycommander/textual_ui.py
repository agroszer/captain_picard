"""Textual-native UI for PyCommander."""

from __future__ import annotations
import configparser
import os
from typing import Any, Callable, Dict, List, Optional
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DirectoryTree, Footer, Header, Label, ListItem, ListView, Static
from textual.screen import ModalScreen

from pycommander.actions import ActionContext, registry as default_registry
from pycommander.keybindings import Keymap, create_norton_keymap, create_vim_keymap
from pycommander.navigation import BookmarkManager, VolumeManager
from pycommander.ops import FileOperations, OverwritePolicy
from pycommander.panes import DualPaneManager, Pane, PaneMode, SplitOrientation
from pycommander.plugins import PluginManager
from pycommander.queue_manager import TransferQueueManager
from pycommander.quick_view import FileInfoGenerator, QuickViewer
from pycommander.search import DuplicateFinder, FileFinder, SearchCriteria
from pycommander.selection import SelectionManager
from pycommander.state import StateManager
from pycommander.vfs import FileStat, LocalVFS, VFS
from pycommander.virtual_folder_vfs import VirtualFolderVFS


def load_theme_colors(ini_path: str = "theme.ini") -> Dict[str, str]:
    config = configparser.ConfigParser()
    if os.path.exists(ini_path):
        config.read(ini_path)
    elif os.path.exists(os.path.join(os.path.dirname(os.path.dirname(__file__)), ini_path)):
        config.read(os.path.join(os.path.dirname(os.path.dirname(__file__)), ini_path))
    else:
        return {}
    if config.has_section("colors"):
        return dict(config.items("colors"))
    return {}


class HelpModal(ModalScreen):
    """Modal screen displaying INI-configured keybindings."""

    def __init__(self, keymap: Keymap, **kwargs):
        super().__init__(**kwargs)
        self.keymap = keymap

    def compose(self) -> ComposeResult:
        with Vertical(id="help-dialog"):
            yield Label("Help & Shortcuts (INI Configured)", id="help-title")
            help_lines = []
            for b in self.keymap.bindings:
                help_lines.append(f"{b.key_sequence.upper():<14} : {b.action_id.replace('_', ' ').title()}")
            content = "\n".join(help_lines)
            yield Static(content, id="help-body")
            yield Label("Press Escape or Enter to close", id="help-footer")

    def on_key(self, event) -> None:
        if event.key in ("escape", "enter"):
            self.dismiss()


class PyCommanderApp(App):
    """The complete Textual orthodox dual-pane file manager application."""

    CSS = """
    Screen {
        background: #000080;
    }
    #panes-container {
        height: 1fr;
    }
    .pane {
        width: 1fr;
        border: solid cyan;
        padding: 0 1;
        background: #000055;
    }
    .active-pane {
        border: double #ffff00;
    }
    .pane-header {
        dock: top;
        background: cyan;
        color: black;
        text-style: bold;
        padding: 0 1;
    }
    #status-bar {
        dock: bottom;
        background: black;
        color: white;
        height: 1;
        padding: 0 1;
    }
    #help-dialog {
        width: 60;
        height: 20;
        background: #880000;
        border: thick white;
        padding: 1 2;
        align: center middle;
    }
    #help-title {
        text-style: bold;
        color: yellow;
        dock: top;
    }
    #help-body {
        height: 1fr;
        color: white;
    }
    #help-footer {
        dock: bottom;
        color: yellow;
    }
    """

    def __init__(
        self,
        left_path: str = ".",
        right_path: str = ".",
        keymap: Optional[Keymap] = None,
        theme_path: str = "theme.ini",
        state_path: Optional[str] = None,
        auto_save_on_change: bool = True,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.panes = DualPaneManager(initial_path_left=left_path, initial_path_right=right_path)
        self.actions = default_registry
        self.keymap = keymap or create_norton_keymap()
        self.ops = FileOperations()
        self.queue = TransferQueueManager(self.ops)
        self.bookmarks = BookmarkManager()
        self.plugins = PluginManager(self.actions)
        self.left_selection = SelectionManager()
        self.right_selection = SelectionManager()
        self.theme_colors = load_theme_colors(theme_path)
        self.auto_save_on_change = auto_save_on_change

        self.state_mgr = StateManager(config_path=state_path) if state_path else StateManager()
        # Restore last saved tabs, active pane, and selection if available
        self.state_mgr.restore_to_app(self.panes, self.left_selection, self.right_selection)

        self._bind_actions_from_ini()
        self._register_actions()

    def persist_state(self) -> None:
        """Saves current state to INI configuration file."""
        try:
            self.state_mgr.save_state(self.panes, self.left_selection, self.right_selection)
        except Exception:
            pass

    def on_unmount(self) -> None:
        """Called automatically on application exit: persists current state."""
        self.persist_state()

    def _bind_actions_from_ini(self) -> None:
        """Dynamically registers Textual keybindings from the INI keymap."""
        for b in self.keymap.bindings:
            act = self.actions.get(b.action_id)
            title = act.title if act else b.action_id.replace("_", " ").title()
            try:
                self.bind(b.key_sequence, b.action_id, description=title)
            except Exception:
                pass

    def _register_actions(self) -> None:
        reg = self.actions

        @reg.register("switch_pane", title="Switch Active Pane")
        def act_switch_pane(ctx=None):
            self.panes.switch_pane()
            self.update_active_pane_ui()
            if self.auto_save_on_change:
                self.persist_state()

        @reg.register("show_help", title="Show Help")
        def act_show_help(ctx=None):
            self.push_screen(HelpModal(self.keymap))

        @reg.register("cursor_up", title="Cursor Up")
        def act_up(ctx=None):
            self.panes.active_pane.move_cursor_up()
            self.refresh_pane_lists()

        @reg.register("cursor_down", title="Cursor Down")
        def act_down(ctx=None):
            self.panes.active_pane.move_cursor_down()
            self.refresh_pane_lists()

        @reg.register("open_selected", title="Open Item")
        def act_open(ctx=None):
            pane = self.panes.active_pane
            cur = pane.get_current_item()
            if cur and cur.is_dir:
                pane.active_tab.navigate_to(cur.path)
                self.refresh_pane_lists()
                if self.auto_save_on_change:
                    self.persist_state()
            elif cur:
                self.plugins.open_file(cur, pane.active_tab.vfs)

        @reg.register("go_parent_dir", title="Parent Directory")
        def act_parent(ctx=None):
            pane = self.panes.active_pane
            parent = os.path.dirname(pane.active_tab.path)
            if parent and parent != pane.active_tab.path:
                pane.active_tab.navigate_to(parent)
                self.refresh_pane_lists()
                if self.auto_save_on_change:
                    self.persist_state()

        @reg.register("toggle_selection", title="Toggle Selection")
        def act_toggle_sel(ctx=None):
            pane = self.panes.active_pane
            sel_mgr = self.left_selection if pane.id == "left" else self.right_selection
            cur = pane.get_current_item()
            if cur:
                sel_mgr.toggle(cur.path)
                pane.move_cursor_down()
                self.refresh_pane_lists()
                if self.auto_save_on_change:
                    self.persist_state()

        @reg.register("copy_items", title="Copy Items")
        def act_copy(ctx=None):
            pane = self.panes.active_pane
            target = self.panes.target_pane
            cur = pane.get_current_item()
            if cur:
                dst = os.path.join(target.active_tab.path, cur.name)
                self.queue.enqueue("copy", pane.active_tab.vfs, cur.path, target.active_tab.vfs, dst)
                self.set_status(f"Enqueued copy for {cur.name}")

        @reg.register("move_items", title="Move Items")
        def act_move(ctx=None):
            pane = self.panes.active_pane
            target = self.panes.target_pane
            cur = pane.get_current_item()
            if cur:
                dst = os.path.join(target.active_tab.path, cur.name)
                self.queue.enqueue("move", pane.active_tab.vfs, cur.path, target.active_tab.vfs, dst)
                self.set_status(f"Enqueued move for {cur.name}")

        @reg.register("delete_items", title="Delete Items")
        def act_delete(ctx=None):
            pane = self.panes.active_pane
            cur = pane.get_current_item()
            if cur:
                self.queue.enqueue("delete", pane.active_tab.vfs, cur.path)
                self.set_status(f"Enqueued delete for {cur.name}")

        @reg.register("quit_app", title="Quit Application")
        def act_quit(ctx=None):
            self.exit()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="panes-container"):
            with Vertical(id="left-pane", classes="pane active-pane"):
                yield Label(self.panes.left.active_tab.path, id="left-title", classes="pane-header")
                yield ListView(id="left-list")
            with Vertical(id="right-pane", classes="pane"):
                yield Label(self.panes.right.active_tab.path, id="right-title", classes="pane-header")
                yield ListView(id="right-list")
        yield Label("Ready. Tab to switch, F1 Help, F10 Quit.", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_pane_lists()

    def set_status(self, msg: str) -> None:
        self.query_one("#status-bar", Label).update(msg)

    def refresh_pane_lists(self) -> None:
        for pane_id, list_id, title_id in [("left", "#left-list", "#left-title"), ("right", "#right-list", "#right-title")]:
            pane: Pane = getattr(self.panes, pane_id)
            title_widget = self.query_one(title_id, Label)
            title_widget.update(pane.active_tab.path)

            list_widget = self.query_one(list_id, ListView)
            list_widget.clear()

            sel_mgr = self.left_selection if pane_id == "left" else self.right_selection
            for it in pane.get_items():
                mark = "*" if sel_mgr.is_selected(it.path) else ("/" if it.is_dir else " ")
                list_widget.append(ListItem(Label(f"[{mark}] {it.name:<30} {it.formatted_size:>10}")))

    def update_active_pane_ui(self) -> None:
        left_pane = self.query_one("#left-pane", Vertical)
        right_pane = self.query_one("#right-pane", Vertical)
        if self.panes.active_pane_id == "left":
            left_pane.add_class("active-pane")
            right_pane.remove_class("active-pane")
        else:
            right_pane.add_class("active-pane")
            left_pane.remove_class("active-pane")
