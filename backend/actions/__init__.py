"""
Actions Framework - Composable, testable tool sequences.

This module provides an abstraction layer for defining complex actions
that sequence multiple tool calls together with:
- Declarative action definitions
- Built-in testing support
- Execution tracing for feedback loops
"""

from backend.actions.base import Action, ActionResult, ActionContext, ActionRegistry
from backend.actions.definitions import REGISTERED_ACTIONS

__all__ = [
    "Action",
    "ActionResult", 
    "ActionContext",
    "ActionRegistry",
    "REGISTERED_ACTIONS",
]
