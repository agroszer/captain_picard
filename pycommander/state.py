"""State persistence manager for tabs, active pane, and selections in ~/.config/pycommander.ini."""

from __future__ import annotations
import configparser
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from pycommander.panes import DualPaneManager, FolderTab, Pane
from pycommander.selection import SelectionManager
from pycommander.vfs import LocalVFS, VFS


DEFAULT_CONFIG_PATH = os.path.expanduser("~/.config/pycommander.ini")


class StateManager:
    """Saves and restores runtime state (tabs, active pane, selections) to/from an INI file."""

    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH):
        self.config_path = os.path.expanduser(config_path)

    def load_state(self) -> Dict[str, Any]:
        """Loads state dictionary from INI file if present."""
        if not os.path.exists(self.config_path):
            return {}

        config = configparser.ConfigParser()
        try:
            config.read(self.config_path)
        except Exception:
            return {}

        state: Dict[str, Any] = {}

        if config.has_section("general"):
            state["active_pane"] = config.get("general", "active_pane", fallback="left")

        if config.has_section("left_pane"):
            state["left_tabs"] = [p.strip() for p in config.get("left_pane", "tabs", fallback="").split(";") if p.strip()]
            state["left_active_tab_idx"] = config.getint("left_pane", "active_tab_idx", fallback=0)
            state["left_selected"] = [p.strip() for p in config.get("left_pane", "selected", fallback="").split(";") if p.strip()]

        if config.has_section("right_pane"):
            state["right_tabs"] = [p.strip() for p in config.get("right_pane", "tabs", fallback="").split(";") if p.strip()]
            state["right_active_tab_idx"] = config.getint("right_pane", "active_tab_idx", fallback=0)
            state["right_selected"] = [p.strip() for p in config.get("right_pane", "selected", fallback="").split(";") if p.strip()]

        return state

    def save_state(
        self,
        panes: DualPaneManager,
        left_selection: Optional[SelectionManager] = None,
        right_selection: Optional[SelectionManager] = None,
    ) -> None:
        """Saves current panes, tabs, active tab indices, and selections to INI file."""
        config = configparser.ConfigParser()

        # Ensure directory exists
        config_dir = os.path.dirname(self.config_path)
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)

        config["general"] = {
            "active_pane": panes.active_pane_id,
        }

        left_tab_paths = ";".join(t.path for t in panes.left.tabs)
        left_sel = ";".join(left_selection.selected_paths) if left_selection else ""
        config["left_pane"] = {
            "tabs": left_tab_paths,
            "active_tab_idx": str(panes.left.active_tab_idx),
            "selected": left_sel,
        }

        right_tab_paths = ";".join(t.path for t in panes.right.tabs)
        right_sel = ";".join(right_selection.selected_paths) if right_selection else ""
        config["right_pane"] = {
            "tabs": right_tab_paths,
            "active_tab_idx": str(panes.right.active_tab_idx),
            "selected": right_sel,
        }

        with open(self.config_path, "w") as f:
            config.write(f)

    def restore_to_app(
        self,
        panes: DualPaneManager,
        left_selection: Optional[SelectionManager] = None,
        right_selection: Optional[SelectionManager] = None,
        vfs: Optional[VFS] = None,
    ) -> bool:
        """Restores state from INI file directly into the dual pane manager and selection managers."""
        state = self.load_state()
        if not state:
            return False

        effective_vfs = vfs or LocalVFS()

        if "active_pane" in state and state["active_pane"] in ("left", "right"):
            panes.active_pane_id = state["active_pane"]

        # Restore Left Pane
        if "left_tabs" in state and state["left_tabs"]:
            panes.left.tabs = [FolderTab(path=p, vfs=effective_vfs) for p in state["left_tabs"]]
            panes.left.active_tab_idx = min(len(panes.left.tabs) - 1, max(0, state.get("left_active_tab_idx", 0)))
        if left_selection and "left_selected" in state:
            left_selection.selected_paths = set(state["left_selected"])

        # Restore Right Pane
        if "right_tabs" in state and state["right_tabs"]:
            panes.right.tabs = [FolderTab(path=p, vfs=effective_vfs) for p in state["right_tabs"]]
            panes.right.active_tab_idx = min(len(panes.right.tabs) - 1, max(0, state.get("right_active_tab_idx", 0)))
        if right_selection and "right_selected" in state:
            right_selection.selected_paths = set(state["right_selected"])

        return True
