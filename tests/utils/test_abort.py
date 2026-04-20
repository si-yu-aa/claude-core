import pytest
import asyncio
from claude_core.utils.abort import AbortController, create_child_abort_controller

@pytest.mark.asyncio
async def test_abort_controller_basic():
    controller = AbortController()
    assert not controller.signal.aborted

    controller.abort()
    assert controller.signal.aborted
    assert controller.signal.reason == "abort"

@pytest.mark.asyncio
async def test_abort_controller_with_reason():
    controller = AbortController()
    controller.abort("custom_reason")
    assert controller.signal.aborted
    assert controller.signal.reason == "custom_reason"

@pytest.mark.asyncio
async def test_child_abort_controller():
    parent = AbortController()
    child = create_child_abort_controller(parent)

    assert not child.signal.aborted
    parent.abort()
    assert child.signal.aborted

@pytest.mark.asyncio
async def test_child_abort_controller_own_abort():
    parent = AbortController()
    child = create_child_abort_controller(parent)

    child.abort("child_reason")
    assert child.signal.aborted
    assert child.signal.reason == "child_reason"
    # Child lifecycle changes must not abort the parent session.
    assert parent.signal.aborted is False


@pytest.mark.asyncio
async def test_child_abort_controller_fast_path_when_parent_already_aborted():
    parent = AbortController()
    parent.abort("already_done")

    child = create_child_abort_controller(parent)

    assert child.signal.aborted is True
    assert child.signal.reason == "already_done"
    assert len(parent.signal._callbacks) == 0


@pytest.mark.asyncio
async def test_child_abort_controller_cleans_parent_listener_on_child_abort():
    parent = AbortController()
    child = create_child_abort_controller(parent)

    assert len(parent.signal._callbacks) == 1

    child.abort("child_done")

    assert len(parent.signal._callbacks) == 0
