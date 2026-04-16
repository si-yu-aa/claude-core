import pytest
import asyncio
from claude_core.utils.stream import Stream, stream_generator

@pytest.mark.asyncio
async def test_stream_basic():
    stream = Stream[str]()

    async def producer():
        stream.enqueue("hello")
        stream.enqueue("world")
        stream.done()

    task = asyncio.create_task(producer())

    results = []
    async for item in stream:
        results.append(item)

    assert results == ["hello", "world"]
    await task

@pytest.mark.asyncio
async def test_stream_error():
    stream = Stream[str]()

    async def producer():
        stream.error(ValueError("test error"))
        stream.done()

    task = asyncio.create_task(producer())

    with pytest.raises(ValueError, match="test error"):
        async for _ in stream:
            pass

    await task