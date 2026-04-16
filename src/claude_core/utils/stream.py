"""Async stream utilities for handling streaming data."""

from typing import AsyncGenerator, TypeVar, Generic, Callable, Awaitable
import asyncio
import enum

T = TypeVar("T")

class _StreamState(enum.Enum):
    PENDING = "pending"
    DONE = "done"
    ERROR = "error"

class Stream(Generic[T]):
    """Async stream with enqueue/done/error operations."""

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._state = _StreamState.PENDING
        self._error: BaseException | None = None

    def enqueue(self, item: T) -> None:
        """Add an item to the stream."""
        if self._state == _StreamState.DONE:
            return
        self._queue.put_nowait(item)

    def error(self, exc: BaseException) -> None:
        """Signal an error on the stream."""
        self._state = _StreamState.ERROR
        self._error = exc
        self._queue.put_nowait(None)

    def done(self) -> None:
        """Signal that the stream is complete."""
        if self._state == _StreamState.PENDING:
            self._state = _StreamState.DONE
            self._queue.put_nowait(None)

    async def _get_next(self) -> T:
        while True:
            item = await self._queue.get()
            if item is None:
                if self._state == _StreamState.ERROR and self._error:
                    raise self._error
                elif self._state == _StreamState.DONE:
                    raise StopAsyncIteration
                else:
                    continue
            return item

    def __aiter__(self) -> AsyncGenerator[T, None]:
        return self._async_iter()

    async def _async_iter(self) -> AsyncGenerator[T, None]:
        try:
            while True:
                yield await self._get_next()
        except StopAsyncIteration:
            pass

def stream_generator(stream: Stream[T]) -> AsyncGenerator[T, None]:
    """Helper to iterate over a stream."""
    return stream._async_iter()