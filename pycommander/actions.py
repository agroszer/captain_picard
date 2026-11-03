"""Action Registry and Action Execution Engine for PyCommander."""

from __future__ import annotations
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ActionContext:
    """Execution context passed to actions when executed."""
    app: Any = None
    active_pane: Any = None
    target_pane: Any = None
    active_tab: Any = None
    selected_items: List[Any] = field(default_factory=list)
    current_item: Any = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Action:
    """Represents an executable action in PyCommander."""
    id: str
    title: str
    description: str = ""
    category: str = "General"
    handler: Optional[Callable[..., Any]] = None
    default_keybinding: Optional[str] = None
    is_user_defined: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def execute(self, context: Optional[ActionContext] = None, **kwargs) -> Any:
        if self.handler is None:
            raise NotImplementedError(f"Action '{self.id}' has no handler defined.")
        sig = inspect.signature(self.handler)
        params = sig.parameters
        if len(params) == 0:
            return self.handler()
        elif "context" in params:
            return self.handler(context=context, **kwargs)
        else:
            first_param = next(iter(params.values()))
            if first_param.name in ("ctx", "context"):
                return self.handler(context, **kwargs)
            return self.handler(context, **kwargs)


class ActionRegistry:
    """Central registry of all built-in and user-defined actions."""

    def __init__(self):
        self._actions: Dict[str, Action] = {}

    def register(
        self,
        action_or_id: Any,
        title: Optional[str] = None,
        description: str = "",
        category: str = "General",
        default_keybinding: Optional[str] = None,
        is_user_defined: bool = False,
        **metadata,
    ) -> Callable:
        """Register an action or use as a decorator."""
        if isinstance(action_or_id, Action):
            self._actions[action_or_id.id] = action_or_id
            return action_or_id

        if callable(action_or_id):
            handler = action_or_id
            act_id = handler.__name__
            act_title = title or act_id.replace("_", " ").title()
            act = Action(
                id=act_id,
                title=act_title,
                description=description or (handler.__doc__ or "").strip(),
                category=category,
                handler=handler,
                default_keybinding=default_keybinding,
                is_user_defined=is_user_defined,
                metadata=metadata,
            )
            self._actions[act_id] = act
            return handler

        def decorator(handler: Callable) -> Callable:
            act_id = action_or_id
            act_title = title or act_id.replace("_", " ").title()
            act = Action(
                id=act_id,
                title=act_title,
                description=description or (handler.__doc__ or "").strip(),
                category=category,
                handler=handler,
                default_keybinding=default_keybinding,
                is_user_defined=is_user_defined,
                metadata=metadata,
            )
            self._actions[act_id] = act
            return handler

        return decorator

    def register_action(self, action: Action) -> None:
        self._actions[action.id] = action

    def unregister(self, action_id: str) -> None:
        if action_id in self._actions:
            del self._actions[action_id]

    def get(self, action_id: str) -> Optional[Action]:
        return self._actions.get(action_id)

    def execute(self, action_id: str, context: Optional[ActionContext] = None, **kwargs) -> Any:
        action = self.get(action_id)
        if not action:
            raise KeyError(f"Action '{action_id}' not found in registry.")
        return action.execute(context=context, **kwargs)

    def list_actions(self, category: Optional[str] = None) -> List[Action]:
        actions = list(self._actions.values())
        if category:
            actions = [a for a in actions if a.category == category]
        return sorted(actions, key=lambda a: a.id)


# Global default registry instance
registry = ActionRegistry()
register = registry.register
