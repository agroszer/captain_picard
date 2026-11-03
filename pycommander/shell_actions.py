"""Shell Command Action executor with template expansion from ActionContext."""

from __future__ import annotations
import os
import shlex
import subprocess
from typing import Any, Dict, List, Optional
from pycommander.actions import Action, ActionContext, ActionRegistry


class ShellTemplateExpander:
    """
    Expands template variables into shell commands based on the active ActionContext.

    Supported template variables:
      ${file}           - Absolute path of current item
      ${name}           - Filename of current item
      ${dir}            - Current directory path
      ${ext}            - Extension of current item
      ${target_dir}     - Target / opposite pane directory path
      ${selected}       - Space-separated quoted paths of all selected items
      ${selected_names} - Space-separated quoted names of all selected items
      ${count}          - Number of selected items (or 1 for current item)
    """

    @classmethod
    def get_template_vars(cls, context: Optional[ActionContext]) -> Dict[str, str]:
        if not context:
            return {
                "file": "",
                "name": "",
                "dir": os.getcwd(),
                "ext": "",
                "target_dir": os.getcwd(),
                "selected": "",
                "selected_names": "",
                "count": "0",
            }

        cur = context.current_item
        cur_file = cur.path if cur else ""
        cur_name = cur.name if cur else ""
        cur_dir = context.active_tab.path if context.active_tab else os.getcwd()
        cur_ext = cur.extension if cur else ""
        target_dir = context.target_pane.active_tab.path if context.target_pane and context.target_pane.active_tab else cur_dir

        selected_items = context.selected_items or ([cur] if cur else [])
        quoted_selected = " ".join(shlex.quote(it.path) for it in selected_items)
        quoted_selected_names = " ".join(shlex.quote(it.name) for it in selected_items)
        count = str(len(selected_items))

        return {
            "file": cur_file,
            "name": cur_name,
            "dir": cur_dir,
            "ext": cur_ext,
            "target_dir": target_dir,
            "selected": quoted_selected,
            "selected_names": quoted_selected_names,
            "count": count,
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
