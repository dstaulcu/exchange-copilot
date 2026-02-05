"""
Base classes for the Actions Framework.

Actions are composable units that can:
1. Sequence multiple tool calls
2. Include conditional logic
3. Be tested in isolation
4. Produce detailed execution traces
"""

import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger("exchange-backend.actions")


class ActionStatus(Enum):
    """Status of an action execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"  # Some steps succeeded
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ToolCall:
    """Record of a single tool invocation."""
    tool_name: str
    arguments: Dict[str, Any]
    result: Any = None
    error: Optional[str] = None
    duration_ms: float = 0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "result": self.result if not isinstance(self.result, str) else json.loads(self.result) if self.result.startswith("{") else self.result,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }


@dataclass
class ActionResult:
    """Result of an action execution with full trace."""
    action_name: str
    status: ActionStatus
    output: Any = None
    error: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    duration_ms: float = 0
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    @property
    def tools_used(self) -> List[str]:
        """List of tool names that were called."""
        return [tc.tool_name for tc in self.tool_calls]
    
    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "action_name": self.action_name,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "tools_used": self.tools_used,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }


@dataclass
class ActionContext:
    """Context passed through action execution."""
    user_query: str
    model_name: str
    provider: str
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    variables: Dict[str, Any] = field(default_factory=dict)
    
    def set(self, key: str, value: Any):
        """Store a value in context for subsequent steps."""
        self.variables[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from context."""
        return self.variables.get(key, default)


class Action(ABC):
    """
    Base class for defining composable actions.
    
    Actions encapsulate sequences of tool calls with:
    - Declarative definition
    - Execution tracing
    - Test support
    
    Example:
        class SummarizeInboxAction(Action):
            name = "summarize_inbox"
            description = "Get inbox and summarize important emails"
            
            def execute(self, context: ActionContext) -> ActionResult:
                # Step 1: Get inbox
                inbox = self.call_tool("get_inbox", limit=20, unread_only=True)
                
                # Step 2: Get details for high-priority emails
                for email in inbox.get("emails", [])[:5]:
                    if email.get("importance") == "High":
                        self.call_tool("read_email", email_id=email["id"])
                
                return self.complete(output={"summary": "..."})
    """
    
    # Override these in subclasses
    name: str = "base_action"
    description: str = "Base action"
    tags: List[str] = []  # For categorization: ["email", "calendar", "lookup"]
    
    def __init__(self, tool_registry: Dict[str, Callable] = None):
        """
        Initialize action with tool registry.
        
        Args:
            tool_registry: Dict mapping tool names to callable functions.
                          If None, tools must be set via set_tools().
        """
        self._tools = tool_registry or {}
        self._tool_calls: List[ToolCall] = []
        self._start_time: float = 0
        self._context: Optional[ActionContext] = None
    
    def set_tools(self, tool_registry: Dict[str, Callable]):
        """Set the tool registry (for dependency injection in tests)."""
        self._tools = tool_registry
    
    def call_tool(self, tool_name: str, **kwargs) -> Any:
        """
        Call a tool and record the invocation.
        
        Args:
            tool_name: Name of the tool to call
            **kwargs: Arguments to pass to the tool
            
        Returns:
            Parsed result from the tool (dict if JSON, else raw string)
        """
        if tool_name not in self._tools:
            raise ValueError(f"Unknown tool: {tool_name}. Available: {list(self._tools.keys())}")
        
        start = time.perf_counter()
        tool_call = ToolCall(tool_name=tool_name, arguments=kwargs)
        
        try:
            result = self._tools[tool_name](**kwargs)
            tool_call.result = result
            
            # Parse JSON results for easier access
            if isinstance(result, str):
                try:
                    return json.loads(result)
                except json.JSONDecodeError:
                    return result
            return result
            
        except Exception as e:
            tool_call.error = str(e)
            logger.error(f"Tool {tool_name} failed: {e}")
            raise
        finally:
            tool_call.duration_ms = (time.perf_counter() - start) * 1000
            self._tool_calls.append(tool_call)
    
    def complete(
        self,
        output: Any = None,
        status: ActionStatus = ActionStatus.SUCCESS
    ) -> ActionResult:
        """Create a successful result."""
        duration = (time.perf_counter() - self._start_time) * 1000
        return ActionResult(
            action_name=self.name,
            status=status,
            output=output,
            tool_calls=self._tool_calls.copy(),
            duration_ms=duration,
        )
    
    def fail(self, error: str) -> ActionResult:
        """Create a failed result."""
        duration = (time.perf_counter() - self._start_time) * 1000
        return ActionResult(
            action_name=self.name,
            status=ActionStatus.FAILED,
            error=error,
            tool_calls=self._tool_calls.copy(),
            duration_ms=duration,
        )
    
    @abstractmethod
    def execute(self, context: ActionContext) -> ActionResult:
        """
        Execute the action.
        
        Override this method to define your action's logic.
        Use self.call_tool() to invoke tools.
        Use self.complete() or self.fail() to return results.
        """
        pass
    
    def run(self, context: ActionContext) -> ActionResult:
        """
        Run the action with full tracing.
        
        This is the main entry point - it wraps execute() with
        timing, error handling, and trace collection.
        """
        self._tool_calls = []
        self._start_time = time.perf_counter()
        self._context = context
        
        try:
            logger.info(f"Starting action: {self.name}")
            result = self.execute(context)
            logger.info(f"Action {self.name} completed: {result.status.value}")
            return result
        except Exception as e:
            logger.error(f"Action {self.name} failed: {e}")
            return self.fail(str(e))


class ActionRegistry:
    """
    Registry for action classes.
    
    Provides:
    - Registration of action classes
    - Lookup by name or tag
    - Execution with tool binding
    """
    
    def __init__(self):
        self._actions: Dict[str, Type[Action]] = {}
        self._tools: Dict[str, Callable] = {}
    
    def register(self, action_class: Type[Action]) -> Type[Action]:
        """
        Register an action class. Can be used as decorator.
        
        Example:
            @registry.register
            class MyAction(Action):
                ...
        """
        self._actions[action_class.name] = action_class
        logger.debug(f"Registered action: {action_class.name}")
        return action_class
    
    def set_tools(self, tools: Dict[str, Callable]):
        """Set the tool registry for all actions."""
        self._tools = tools
    
    def get(self, name: str) -> Optional[Type[Action]]:
        """Get an action class by name."""
        return self._actions.get(name)
    
    def list_actions(self) -> List[Dict[str, Any]]:
        """List all registered actions with metadata."""
        return [
            {
                "name": ac.name,
                "description": ac.description,
                "tags": ac.tags,
            }
            for ac in self._actions.values()
        ]
    
    def find_by_tag(self, tag: str) -> List[Type[Action]]:
        """Find actions by tag."""
        return [
            ac for ac in self._actions.values()
            if tag in ac.tags
        ]
    
    def execute(self, action_name: str, context: ActionContext) -> ActionResult:
        """
        Execute a registered action by name.
        
        Args:
            action_name: Name of the action to execute
            context: Execution context
            
        Returns:
            ActionResult with full execution trace
        """
        action_class = self._actions.get(action_name)
        if not action_class:
            raise ValueError(f"Unknown action: {action_name}")
        
        action = action_class(tool_registry=self._tools)
        return action.run(context)


# Global registry instance
registry = ActionRegistry()
