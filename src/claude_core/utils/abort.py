"""AbortController implementation for cancellation support."""

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class AbortSignal:
    """Signal that indicates abort has been requested."""
    aborted: bool = False
    reason: str | None = None
    _callbacks: list[Callable] = field(default_factory=list)

    def add_event_listener(self, event: str, callback: Callable) -> Callable[[], None]:
        if event == "abort":
            self._callbacks.append(callback)
            return lambda: self.remove_event_listener(event, callback)
        return lambda: None

    def remove_event_listener(self, event: str, callback: Callable) -> None:
        if event != "abort":
            return
        try:
            self._callbacks.remove(callback)
        except ValueError:
            pass

    def _notify(self) -> None:
        for callback in list(self._callbacks):
            callback()


@dataclass
class AbortController:
    """Controller for aborting async operations."""
    signal: AbortSignal = field(default_factory=AbortSignal)
    _cleanup_callbacks: list[Callable[[], None]] = field(default_factory=list)

    def abort(self, reason: str = "abort") -> None:
        """Request abort with optional reason."""
        if self.signal.aborted:
            return
        self.signal.aborted = True
        self.signal.reason = reason
        self.signal._notify()
        self.dispose()

    def add_cleanup(self, callback: Callable[[], None]) -> None:
        self._cleanup_callbacks.append(callback)

    def dispose(self) -> None:
        while self._cleanup_callbacks:
            cleanup = self._cleanup_callbacks.pop()
            cleanup()


def create_child_abort_controller(parent: AbortController) -> AbortController:
    """Create a child abort controller with one-way parent-to-child propagation."""
    child = AbortController()

    if parent.signal.aborted:
        child.abort(parent.signal.reason or "parent_abort")
        return child

    def propagate_to_child():
        if not child.signal.aborted:
            child.abort(parent.signal.reason or "parent_abort")

    child.add_cleanup(parent.signal.add_event_listener("abort", propagate_to_child))
    return child
