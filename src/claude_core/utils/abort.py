"""AbortController implementation for cancellation support."""

from dataclasses import dataclass, field
from typing import Callable
import asyncio

@dataclass
class AbortSignal:
    """Signal that indicates abort has been requested."""
    aborted: bool = False
    reason: str | None = None
    _callbacks: list[Callable] = field(default_factory=list)

    def add_event_listener(self, event: str, callback: Callable) -> None:
        if event == "abort":
            self._callbacks.append(callback)

    def _notify(self) -> None:
        for callback in self._callbacks:
            callback()

@dataclass
class AbortController:
    """Controller for aborting async operations."""
    signal: AbortSignal = field(default_factory=AbortSignal)

    def abort(self, reason: str = "abort") -> None:
        """Request abort with optional reason."""
        self.signal.aborted = True
        self.signal.reason = reason
        self.signal._notify()

def create_child_abort_controller(parent: AbortController) -> AbortController:
    """Create a child abort controller that propagates to parent and vice versa."""
    child = AbortController()

    def propagate_to_parent():
        if not parent.signal.aborted:
            parent.abort(child.signal.reason or "child_abort")

    def propagate_to_child():
        if not child.signal.aborted:
            child.abort(parent.signal.reason or "parent_abort")

    child.signal.add_event_listener("abort", propagate_to_parent)
    parent.signal.add_event_listener("abort", propagate_to_child)
    return child