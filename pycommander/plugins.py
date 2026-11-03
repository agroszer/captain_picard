"""Plugin Architecture and Custom Openers/Viewers."""

from __future__ import annotations
import os
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from pycommander.actions import Action, ActionContext, ActionRegistry
from pycommander.vfs import FileStat, VFS


@dataclass
class FileAssociation:
    """Associates file patterns (extensions or regex) with custom openers/viewers."""
    pattern: str  # e.g. "py", "md", "png"
    command: Optional[str] = None  # e.g. "nvim {file}"
    handler: Optional[Callable[[str, VFS], Any]] = None
    is_internal_viewer: bool = False


class PluginManager:
    """Plugin and File Association Architecture."""

    def __init__(self, action_registry: ActionRegistry):
        self.registry = action_registry
        self.associations: List[FileAssociation] = []
        self._hooks: Dict[str, List[Callable[..., Any]]] = {}
        self._load_default_associations()

    def _load_default_associations(self) -> None:
        # Default associations can be customized by plugins or user config
        self.associations.append(
            FileAssociation(
                pattern="txt;md;py;json;yml;yaml;sh;c;cpp;h;ts;js;html;css",
                is_internal_viewer=True,
            )
        )

    def register_hook(self, event_name: str, callback: Callable[..., Any]) -> None:
        self._hooks.setdefault(event_name, []).append(callback)

    def trigger_hook(self, event_name: str, *args, **kwargs) -> List[Any]:
        results = []
        for cb in self._hooks.get(event_name, []):
            try:
                results.append(cb(*args, **kwargs))
            except Exception:
                pass
        return results

    def add_association(
        self,
        pattern: str,
        command: Optional[str] = None,
        handler: Optional[Callable[[str, VFS], Any]] = None,
    ) -> None:
        self.associations.insert(0, FileAssociation(pattern=pattern, command=command, handler=handler))

    def open_file(self, stat_entry: FileStat, vfs: VFS) -> bool:
        """Opens file using registered association or default opener."""
        ext = stat_entry.extension.lower()

        for assoc in self.associations:
            patterns = [p.strip().lower() for p in assoc.pattern.split(";")]
            if ext in patterns or "*" in patterns:
                if assoc.handler:
                    assoc.handler(stat_entry.path, vfs)
                    return True
                elif assoc.command:
                    cmd = assoc.command.replace("{file}", stat_entry.path)
                    try:
                        subprocess.Popen(cmd, shell=True)
                        return True
                    except Exception:
                        return False

        # Fallback: check environment $EDITOR or sensible default
        editor = os.environ.get("EDITOR", "nano")
        try:
            subprocess.run([editor, stat_entry.path])
            return True
        except Exception:
            return False
