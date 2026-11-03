"""PyCommander Main Application & TUI Controller."""

from __future__ import annotations
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from pycommander.actions import Action, ActionContext, ActionRegistry, registry as default_registry
from pycommander.keybindings import Keymap, create_norton_keymap, create_vim_keymap
from pycommander.navigation import BookmarkManager, BreadcrumbNavigator, VolumeManager
from pycommander.ops import FileOperations, OverwritePolicy
from pycommander.panes import DualPaneManager, ListingFormat, Pane, PaneMode, SplitOrientation
from pycommander.plugins import PluginManager
from pycommander.queue_manager import TransferQueueManager
from pycommander.quick_view import FileInfoGenerator, QuickViewer
from pycommander.search import DuplicateFinder, FileFinder, SearchCriteria
from pycommander.selection import SelectionManager
from pycommander.terminal import Color, ScreenBuffer
from pycommander.vfs import FileStat, LocalVFS, VFS
from pycommander.virtual_folder_vfs import VirtualFolderVFS


@dataclass
class DialogButton:
    text: str
    callback: Callable[[], Any]


class PyCommanderApp:
    """The central application orchestrator and TUI interface."""

    def __init__(
        self,
        left_path: str = ".",
        right_path: str = ".",
        keymap: Optional[Keymap] = None,
        width: int = 80,
        height: int = 24,
    ):
        self.width = width
        self.height = height
        self.buffer = ScreenBuffer(width=width, height=height)
        self.panes = DualPaneManager(initial_path_left=left_path, initial_path_right=right_path)
        self.actions = default_registry
        self.keymap = keymap or create_norton_keymap()
        self.ops = FileOperations()
        self.queue = TransferQueueManager(self.ops)
        self.bookmarks = BookmarkManager()
        self.plugins = PluginManager(self.actions)

        self.left_selection = SelectionManager()
        self.right_selection = SelectionManager()

        self.status_message: str = "Ready. Press F1 for Help, Tab to switch pane."
        self.is_running: bool = True
        self.active_dialog: Optional[Dict[str, Any]] = None  # Dialog state if active
        self.command_line_input: str = ""
        self.show_menu_bar: bool = False
        self.menu_bar_idx: int = 0

        self._register_builtin_actions()

    @property
    def current_selection_mgr(self) -> SelectionManager:
        return self.left_selection if self.panes.active_pane_id == "left" else self.right_selection

    def get_action_context(self) -> ActionContext:
        active = self.panes.active_pane
        target = self.panes.target_pane
        active_tab = active.active_tab
        items = active.get_items()
        cur_item = active.get_current_item()
        sel_mgr = self.current_selection_mgr
        selected = [it for it in items if sel_mgr.is_selected(it.path)]
        if not selected and cur_item:
            selected = [cur_item]

        return ActionContext(
            app=self,
            active_pane=active,
            target_pane=target,
            active_tab=active_tab,
            selected_items=selected,
            current_item=cur_item,
        )

    def _register_builtin_actions(self) -> None:
        reg = self.actions

        # Navigation
        @reg.register("cursor_up", title="Cursor Up")
        def act_cursor_up(ctx: ActionContext):
            if ctx.active_pane.mode == PaneMode.TREE and ctx.active_pane.tree_view:
                ctx.active_pane.tree_view.move_cursor_up()
            else:
                ctx.active_pane.move_cursor_up()

        @reg.register("cursor_down", title="Cursor Down")
        def act_cursor_down(ctx: ActionContext):
            if ctx.active_pane.mode == PaneMode.TREE and ctx.active_pane.tree_view:
                ctx.active_pane.tree_view.move_cursor_down()
            else:
                ctx.active_pane.move_cursor_down()

        @reg.register("go_home", title="Go to First Item")
        def act_go_home(ctx: ActionContext):
            ctx.active_pane.move_cursor_home()

        @reg.register("go_end", title="Go to Last Item")
        def act_go_end(ctx: ActionContext):
            ctx.active_pane.move_cursor_end()

        @reg.register("switch_pane", title="Switch Active Pane")
        def act_switch_pane(ctx: ActionContext):
            self.panes.switch_pane()

        @reg.register("open_selected", title="Open Item / Enter Directory")
        def act_open_selected(ctx: ActionContext):
            if ctx.active_pane.mode == PaneMode.TREE and ctx.active_pane.tree_view:
                node = ctx.active_pane.tree_view.get_selected_node()
                if node:
                    ctx.active_pane.active_tab.navigate_to(node.path)
                    ctx.active_pane.mode = PaneMode.FILE_LIST
                return

            cur = ctx.current_item
            if not cur:
                return
            if cur.is_dir:
                ctx.active_tab.navigate_to(cur.path)
            else:
                self.plugins.open_file(cur, ctx.active_tab.vfs)

        @reg.register("go_parent_dir", title="Go to Parent Directory")
        def act_go_parent_dir(ctx: ActionContext):
            parent = os.path.dirname(ctx.active_tab.path)
            if parent and parent != ctx.active_tab.path:
                ctx.active_tab.navigate_to(parent)

        # Tabs
        @reg.register("new_tab", title="New Tab")
        def act_new_tab(ctx: ActionContext):
            ctx.active_pane.new_tab()

        @reg.register("close_tab", title="Close Tab")
        def act_close_tab(ctx: ActionContext):
            ctx.active_pane.close_tab()

        @reg.register("next_tab", title="Next Tab")
        def act_next_tab(ctx: ActionContext):
            ctx.active_pane.next_tab()

        @reg.register("prev_tab", title="Previous Tab")
        def act_prev_tab(ctx: ActionContext):
            ctx.active_pane.prev_tab()

        @reg.register("lock_tab", title="Toggle Lock Tab")
        def act_lock_tab(ctx: ActionContext):
            locked = ctx.active_pane.toggle_tab_lock()
            self.status_message = f"Tab locked: {locked}"

        # Norton Function Keys
        @reg.register("show_help", title="Show Help")
        def act_show_help(ctx: ActionContext):
            self.open_dialog(
                "Help & Shortcuts",
                [
                    "F1: Help         F2: User Menu   F3: View File",
                    "F4: Edit File    F5: Copy Items  F6: Move/Rename",
                    "F7: Mkdir        F8: Delete      F9: Menu Bar",
                    "F10: Quit        Tab: Switch     Insert/Space: Select",
                    "+/-: Wildcard Sel  *: Invert Sel   Ctrl+Q: Quick View",
                    "Ctrl+T/W: New/Close Tab  Alt+F7: Find Files",
                ],
            )

        @reg.register("show_user_menu", title="User Menu")
        def act_show_user_menu(ctx: ActionContext):
            self.open_dialog("User Actions Menu", ["1. Compress to Zip", "2. Git Status", "3. System Information"])

        @reg.register("view_file", title="View File")
        def act_view_file(ctx: ActionContext):
            cur = ctx.current_item
            if not cur:
                return
            preview_lines = QuickViewer.generate_preview(ctx.active_tab.vfs, cur.path, max_lines=20)
            self.open_dialog(f"View: {cur.name}", preview_lines)

        @reg.register("edit_file", title="Edit File")
        def act_edit_file(ctx: ActionContext):
            cur = ctx.current_item
            if cur and not cur.is_dir:
                self.plugins.open_file(cur, ctx.active_tab.vfs)

        @reg.register("copy_items", title="Copy Items")
        def act_copy_items(ctx: ActionContext):
            for item in ctx.selected_items:
                target_path = os.path.join(ctx.target_pane.active_tab.path, item.name)
                self.queue.enqueue(
                    operation="copy",
                    src_vfs=ctx.active_tab.vfs,
                    src_path=item.path,
                    dst_vfs=ctx.target_pane.active_tab.vfs,
                    dst_path=target_path,
                )
            self.status_message = f"Enqueued {len(ctx.selected_items)} item(s) for copy."

        @reg.register("move_items", title="Move / Rename Items")
        def act_move_items(ctx: ActionContext):
            for item in ctx.selected_items:
                target_path = os.path.join(ctx.target_pane.active_tab.path, item.name)
                self.queue.enqueue(
                    operation="move",
                    src_vfs=ctx.active_tab.vfs,
                    src_path=item.path,
                    dst_vfs=ctx.target_pane.active_tab.vfs,
                    dst_path=target_path,
                )
            self.status_message = f"Enqueued {len(ctx.selected_items)} item(s) for move."

        @reg.register("make_directory", title="Create Directory")
        def act_mkdir(ctx: ActionContext):
            # Creates a directory in current folder
            new_path = os.path.join(ctx.active_tab.path, "New_Folder")
            ctx.active_tab.vfs.make_dir(new_path)
            self.status_message = f"Created directory: {new_path}"

        @reg.register("delete_items", title="Delete Items")
        def act_delete_items(ctx: ActionContext):
            for item in ctx.selected_items:
                self.queue.enqueue(
                    operation="delete",
                    src_vfs=ctx.active_tab.vfs,
                    src_path=item.path,
                )
            self.status_message = f"Enqueued {len(ctx.selected_items)} item(s) for deletion."

        @reg.register("quit_app", title="Quit PyCommander")
        def act_quit_app(ctx: ActionContext):
            self.is_running = False

        # Selection
        @reg.register("toggle_selection", title="Toggle Selection")
        def act_toggle_selection(ctx: ActionContext):
            cur = ctx.current_item
            if cur:
                self.current_selection_mgr.toggle(cur.path)
                ctx.active_pane.move_cursor_down()

        @reg.register("select_by_wildcard", title="Select by Wildcard")
        def act_select_wildcard(ctx: ActionContext):
            cnt = self.current_selection_mgr.select_by_wildcard("*.*", ctx.active_pane.get_items(), is_select=True)
            self.status_message = f"Selected {cnt} items."

        @reg.register("deselect_by_wildcard", title="Deselect by Wildcard")
        def act_deselect_wildcard(ctx: ActionContext):
            cnt = self.current_selection_mgr.select_by_wildcard("*.*", ctx.active_pane.get_items(), is_select=False)
            self.status_message = f"Deselected {cnt} items."

        @reg.register("invert_selection", title="Invert Selection")
        def act_invert_selection(ctx: ActionContext):
            self.current_selection_mgr.invert(ctx.active_pane.get_items())

        @reg.register("select_all_same_ext", title="Select All Same Extension")
        def act_same_ext(ctx: ActionContext):
            cnt = self.current_selection_mgr.select_all_same_extension(ctx.current_item, ctx.active_pane.get_items())
            self.status_message = f"Selected {cnt} items with same extension."

        # Quick View & Panels
        @reg.register("toggle_quick_view", title="Toggle Quick View")
        def act_quick_view(ctx: ActionContext):
            m = self.panes.toggle_quick_view()
            self.status_message = f"Opposite pane mode: {m.value}"

        @reg.register("toggle_info_panel", title="Toggle Info Panel")
        def act_info_panel(ctx: ActionContext):
            m = self.panes.toggle_info_panel()
            self.status_message = f"Opposite pane mode: {m.value}"

        @reg.register("toggle_tree_view", title="Toggle Tree View")
        def act_tree_view(ctx: ActionContext):
            m = self.panes.toggle_tree_view()
            self.status_message = f"Pane mode: {m.value}"

        @reg.register("compare_directories", title="Compare Directories")
        def act_compare_dirs(ctx: ActionContext):
            diffs = self.panes.compare_directories()
            self.status_message = f"Comparison complete. Found {len(diffs)} items."

        @reg.register("swap_panes", title="Swap Panes")
        def act_swap_panes(ctx: ActionContext):
            self.panes.swap_panes()

        @reg.register("toggle_split_orientation", title="Toggle Split Orientation")
        def act_toggle_split(ctx: ActionContext):
            ori = self.panes.toggle_split_orientation()
            self.status_message = f"Split orientation: {ori.value}"

        # Bookmarks & Mounts
        @reg.register("show_bookmarks", title="Directory Bookmarks (Hotlist)")
        def act_bookmarks(ctx: ActionContext):
            lines = [f"{b.hotkey or ' '}: [{b.title}] -> {b.path}" for b in self.bookmarks.bookmarks]
            self.open_dialog("Directory Bookmarks (Ctrl+D)", lines)

        @reg.register("show_mounts", title="Drive / Mounted Volumes")
        def act_mounts(ctx: ActionContext):
            mounts = VolumeManager.get_mounts()
            lines = [f"{m['device']} on {m['mountpoint']} ({m['fstype']})" for m in mounts]
            self.open_dialog("Mounted Volumes", lines)

        # Search & Feed to Listbox
        @reg.register("find_files", title="Advanced File Finder")
        def act_find_files(ctx: ActionContext):
            finder = FileFinder(ctx.active_tab.vfs)
            crit = SearchCriteria(name_pattern="*.*")
            hits = finder.search(ctx.active_tab.path, crit)
            vfolder = VirtualFolderVFS(f"Search Hits ({len(hits)})", items=hits, underlying_vfs=ctx.active_tab.vfs)
            ctx.active_pane.new_tab(path="/", vfs=vfolder)
            self.status_message = f"Found {len(hits)} hits. Fed to new virtual tab."

    def open_dialog(self, title: str, lines: List[str]) -> None:
        self.active_dialog = {
            "title": title,
            "lines": lines,
            "scroll_offset": 0,
        }

    def close_dialog(self) -> None:
        self.active_dialog = None

    def handle_key(self, key_name: str) -> bool:
        """Handles single key input event, routing to active dialog, input, or keymap."""
        if self.active_dialog:
            if key_name.lower() in ("escape", "enter", "f10", "q", "space"):
                self.close_dialog()
                return True
            elif key_name.lower() == "up":
                self.active_dialog["scroll_offset"] = max(0, self.active_dialog["scroll_offset"] - 1)
                return True
            elif key_name.lower() == "down":
                self.active_dialog["scroll_offset"] += 1
                return True
            return True

        status, binding = self.keymap.feed_key(key_name)
        if status == "match" and binding:
            ctx = self.get_action_context()
            self.actions.execute(binding.action_id, context=ctx, **binding.args)
            return True
        return False

    def render(self) -> str:
        """Renders the entire TUI screen into the ScreenBuffer."""
        self.buffer.clear(bg=Color.BG_BLUE, fg=Color.WHITE)

        # 1. Top Menu Bar
        menu_items = [" Left ", " File ", " Command ", " Options ", " Right "]
        menu_text = "".join(menu_items)
        self.buffer.put_text(0, 0, menu_text.ljust(self.width), fg=Color.BLACK, bg=Color.BG_CYAN)

        # 2. Main Panes Layout
        panel_y = 1
        panel_h = self.height - 4  # Reserve 1 for menu, 1 for cmdline, 1 for status, 1 for F-keys

        if self.panes.orientation == SplitOrientation.VERTICAL:
            panel_w = self.width // 2
            self._render_pane(self.panes.left, 0, panel_y, panel_w, panel_h, is_active=(self.panes.active_pane_id == "left"))
            self._render_pane(self.panes.right, panel_w, panel_y, self.width - panel_w, panel_h, is_active=(self.panes.active_pane_id == "right"))
        else:
            half_h = panel_h // 2
            self._render_pane(self.panes.left, 0, panel_y, self.width, half_h, is_active=(self.panes.active_pane_id == "left"))
            self._render_pane(self.panes.right, 0, panel_y + half_h, self.width, panel_h - half_h, is_active=(self.panes.active_pane_id == "right"))

        # 3. Status Bar / Command Line
        status_y = self.height - 2
        status_txt = f"{self.status_message}"
        self.buffer.put_text(0, status_y, status_txt.ljust(self.width), fg=Color.WHITE, bg=Color.BG_BLACK)

        # 4. Norton Bottom Button Bar (F1 - F10)
        btn_y = self.height - 1
        fn_keys = [
            ("1", "Help"),
            ("2", "Menu"),
            ("3", "View"),
            ("4", "Edit"),
            ("5", "Copy"),
            ("6", "Move"),
            ("7", "Mkdir"),
            ("8", "Delete"),
            ("9", "PullDn"),
            ("10", "Quit"),
        ]
        seg_w = max(1, self.width // 10)
        for i, (num, name) in enumerate(fn_keys):
            bx = i * seg_w
            self.buffer.put_text(bx, btn_y, num, fg=Color.WHITE, bg=Color.BG_BLACK, bold=True)
            self.buffer.put_text(bx + len(num), btn_y, name.ljust(seg_w - len(num)), fg=Color.BLACK, bg=Color.BG_CYAN)

        # 5. Modal Dialog Overlay if open
        if self.active_dialog:
            self._render_dialog()

        return self.buffer.render_to_string()

    def _render_pane(self, pane: Pane, x: int, y: int, w: int, h: int, is_active: bool) -> None:
        title = pane.active_tab.path
        if pane.active_tab.is_locked:
            title = f"[LOCKED] {title}"

        # Draw outer box
        box_fg = Color.CYAN if is_active else Color.WHITE
        self.buffer.draw_box(x, y, w, h, title=title, fg=box_fg, bg=Color.BG_BLUE, double=is_active)

        # Tabs Header line
        tab_str = ""
        for i, t in enumerate(pane.tabs):
            tab_title = t.title[:8]
            if i == pane.active_tab_idx:
                tab_str += f"[{tab_title}] "
            else:
                tab_str += f" {tab_title}  "
        self.buffer.put_text(x + 1, y + 1, tab_str[: w - 2], fg=Color.YELLOW, bg=Color.BG_BLUE)

        content_y = y + 2
        content_h = h - 3

        if pane.mode == PaneMode.QUICK_VIEW:
            # Inline Quick View of opposite pane's current file
            target = self.panes.left if pane == self.panes.right else self.panes.right
            cur = target.get_current_item()
            preview = QuickViewer.generate_preview(target.active_tab.vfs, cur.path if cur else "")
            for i, line in enumerate(preview[:content_h]):
                self.buffer.put_text(x + 1, content_y + i, line[: w - 2], fg=Color.WHITE, bg=Color.BG_BLUE)

        elif pane.mode == PaneMode.INFO:
            target = self.panes.left if pane == self.panes.right else self.panes.right
            cur = target.get_current_item()
            info = FileInfoGenerator.generate_info(target.active_tab.vfs, cur.path if cur else "")
            for i, line in enumerate(info[:content_h]):
                self.buffer.put_text(x + 1, content_y + i, line[: w - 2], fg=Color.WHITE, bg=Color.BG_BLUE)

        elif pane.mode == PaneMode.TREE and pane.tree_view:
            nodes = pane.tree_view.get_visible_nodes()
            for i, node in enumerate(nodes[:content_h]):
                prefix = "+-- " if not node.is_expanded else "-+- "
                indent = "  " * node.depth
                node_text = f"{indent}{prefix}{node.name}"
                is_cursor = (i == pane.tree_view.cursor_index and is_active)
                bg = Color.BG_CYAN if is_cursor else Color.BG_BLUE
                fg = Color.BLACK if is_cursor else Color.WHITE
                self.buffer.put_text(x + 1, content_y + i, node_text[: w - 2].ljust(w - 2), fg=fg, bg=bg)

        else:
            # File List View
            items = pane.get_items()
            sel_mgr = self.left_selection if pane.id == "left" else self.right_selection
            cursor = pane.active_tab.cursor_index

            for i, item in enumerate(items[:content_h]):
                is_cursor = (i == cursor and is_active)
                is_sel = sel_mgr.is_selected(item.path)

                bg = Color.BG_CYAN if is_cursor else Color.BG_BLUE
                fg = Color.BLACK if is_cursor else (Color.YELLOW if is_sel else (Color.WHITE if item.is_dir else Color.CYAN))

                # Comparison visual indicators
                comp_tag = self.panes.comparison_diffs.get(f"{pane.id}:{item.name}", "")
                marker = "*" if is_sel else ("!" if comp_tag.startswith("diff") else " ")

                # Column format
                name_w = w - 18
                name_part = f"{marker} {item.name[:name_w]:<{name_w}}"
                size_part = f"{item.formatted_size:>8}"
                row_str = f"{name_part} {size_part}"

                self.buffer.put_text(x + 1, content_y + i, row_str[: w - 2], fg=fg, bg=bg, bold=item.is_dir)

    def _render_dialog(self) -> None:
        if not self.active_dialog:
            return
        dw = min(60, self.width - 4)
        dh = min(15, self.height - 4)
        dx = (self.width - dw) // 2
        dy = (self.height - dh) // 2

        self.buffer.draw_box(dx, dy, dw, dh, title=self.active_dialog["title"], fg=Color.WHITE, bg=Color.BG_RED, double=True)
        lines = self.active_dialog["lines"]
        offset = self.active_dialog.get("scroll_offset", 0)

        for i, line in enumerate(lines[offset : offset + (dh - 3)]):
            self.buffer.put_text(dx + 2, dy + 1 + i, line[: dw - 4], fg=Color.WHITE, bg=Color.BG_RED)

        hint = "[ Enter / Esc to Close ]"
        self.buffer.put_text(dx + (dw - len(hint)) // 2, dy + dh - 1, hint, fg=Color.YELLOW, bg=Color.BG_RED)
