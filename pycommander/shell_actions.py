"""Shell Command Action executor with rich template expansion from ActionContext."""

from __future__ import annotations
import os
import shlex
import subprocess
from typing import Any, Dict, List, Optional
from pycommander.actions import Action, ActionContext, ActionRegistry


class ShellTemplateExpander:
    """
    Expands template variables into shell commands based on the active ActionContext.

    Available Template Variables:
      -----------------------------------------------------------------------------------------
      Variable            Description
      -----------------------------------------------------------------------------------------
      ${current_dir}      Active pane's current working directory (alias: ${dir}, ${cwd})
      ${target_dir}       Opposite / target pane's current directory (alias: ${other_dir})
      ${full_fname}       Full absolute path of the current selected file (alias: ${file}, ${path})
      ${just_fname}       Filename of current selected file with extension (alias: ${name}, ${fname})
      ${stem}             Filename without extension (e.g. 'doc' for 'doc.txt', alias: ${basename})
      ${ext}              File extension without leading dot (e.g. 'txt')
      ${size}             Size in bytes of current selected item
      ${mtime}            Modification timestamp of current selected item
      ${perms}            Unix permissions string (e.g. '-rw-r--r--')
      ${user}             Owner username of current selected item
      ${group}            Group name of current selected item
      ${selected}         Space-separated, shell-quoted full paths of all selected items
      ${selected_names}   Space-separated, shell-quoted filenames of all selected items
      ${selected_stems}   Space-separated, shell-quoted stems (names without ext) of selected items
      ${count}            Number of selected items (or 1 if current item is targeted)
      ${active_pane}      Name of the active pane ('left' or 'right')
      ${target_pane}      Name of the target pane ('right' or 'left')
      -----------------------------------------------------------------------------------------
    """

    @classmethod
    def get_template_vars(cls, context: Optional[ActionContext]) -> Dict[str, str]:
        if not context:
            cwd = os.getcwd()
            return {
                "current_dir": cwd,
                "dir": cwd,
                "cwd": cwd,
                "target_dir": cwd,
                "other_dir": cwd,
                "full_fname": "",
                "file": "",
                "path": "",
                "just_fname": "",
                "name": "",
                "fname": "",
                "stem": "",
                "basename": "",
                "ext": "",
                "size": "0",
                "mtime": "0",
                "perms": "",
                "user": "",
                "group": "",
                "selected": "",
                "selected_names": "",
                "selected_stems": "",
                "count": "0",
                "active_pane": "left",
                "target_pane": "right",
            }

        cur = context.current_item
        cur_file = cur.path if cur else ""
        cur_name = cur.name if cur else ""
        cur_dir = context.active_tab.path if context.active_tab else os.getcwd()
        cur_ext = cur.extension if cur else ""

        stem = ""
        if cur_name:
            stem, _ = os.path.splitext(cur_name)

        target_dir = context.target_pane.active_tab.path if context.target_pane and context.target_pane.active_tab else cur_dir

        selected_items = context.selected_items or ([cur] if cur else [])
        quoted_selected = " ".join(shlex.quote(it.path) for it in selected_items)
        quoted_selected_names = " ".join(shlex.quote(it.name) for it in selected_items)
        quoted_selected_stems = " ".join(shlex.quote(os.path.splitext(it.name)[0]) for it in selected_items)
        count = str(len(selected_items))

        active_pane_id = getattr(context.active_pane, "id", "left")
        target_pane_id = getattr(context.target_pane, "id", "right")

        size_str = str(cur.size) if cur else "0"
        mtime_str = str(cur.mtime) if cur else "0"
        perms_str = cur.permissions_str if cur else ""
        user_str = cur.user if cur else ""
        group_str = cur.group if cur else ""

        return {
            # Directory variables
            "current_dir": cur_dir,
            "dir": cur_dir,
            "cwd": cur_dir,
            "target_dir": target_dir,
            "other_dir": target_dir,

            # Single file variables
            "full_fname": cur_file,
            "file": cur_file,
            "path": cur_file,
            "just_fname": cur_name,
            "name": cur_name,
            "fname": cur_name,
            "stem": stem,
            "basename": stem,
            "ext": cur_ext,

            # File metadata
            "size": size_str,
            "mtime": mtime_str,
            "perms": perms_str,
            "user": user_str,
            "group": group_str,

            # Selection collections
            "selected": quoted_selected,
            "selected_names": quoted_selected_names,
            "selected_stems": quoted_selected_stems,
            "count": count,

            # Panes
            "active_pane": str(active_pane_id),
            "target_pane": str(target_pane_id),
        }

    @classmethod
    def expand(cls, template: str, context: Optional[ActionContext]) -> str:
        vars_map = cls.get_template_vars(context)
        expanded = template
        for key, val in vars_map.items():
            # Replace ${key} and $key
            expanded = expanded.replace(f"${{{key}}}", val)
            expanded = expanded.replace(f"${key}", val)
        return expanded


def execute_shell_action(
    command_template: str,
    context: Optional[ActionContext] = None,
    run_in_background: bool = False,
    cwd: Optional[str] = None,
) -> int:
    """Expands template variables and executes the shell command."""
    expanded_cmd = ShellTemplateExpander.expand(command_template, context)
    work_dir = cwd or (context.active_tab.path if context and context.active_tab else os.getcwd())

    if run_in_background:
        proc = subprocess.Popen(expanded_cmd, shell=True, cwd=work_dir)
        return 0
    else:
        res = subprocess.run(expanded_cmd, shell=True, cwd=work_dir)
        return res.returncode


def register_shell_action(
    registry: ActionRegistry,
    action_id: str,
    command_template: str,
    title: Optional[str] = None,
    run_in_background: bool = False,
) -> Action:
    """Registers a user-defined shell command action with template expansion."""
    def handler(context: Optional[ActionContext] = None, **kwargs):
        return execute_shell_action(
            command_template=command_template,
            context=context,
            run_in_background=run_in_background,
        )

    action = Action(
        id=action_id,
        title=title or f"Shell: {command_template[:20]}",
        description=f"Executes shell command: {command_template}",
        category="Shell",
        handler=handler,
        is_user_defined=True,
        metadata={"template": command_template, "is_shell": True},
    )
    registry.register_action(action)
    return action
