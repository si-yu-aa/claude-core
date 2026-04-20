import pytest
from claude_core.engine.query_engine import QueryEngine
from claude_core.engine.config import QueryEngineConfig
from claude_core.models.message import UserMessage

@pytest.fixture
def config():
    return QueryEngineConfig(
        api_key="test-key",
        provider="openai",
        base_url="https://api.openai.com/v1",
        model="gpt-4o",
    )

@pytest.mark.asyncio
async def test_query_engine_initialization(config):
    engine = QueryEngine(config)
    assert engine.config == config
    assert engine._messages == []

@pytest.mark.asyncio
async def test_engine_submit_message_returns_generator(config):
    engine = QueryEngine(config)
    result = engine.submit_message("Hello")
    # Should return an async generator
    import inspect
    assert inspect.isasyncgen(result)

@pytest.mark.asyncio
async def test_engine_has_abort_controller(config):
    engine = QueryEngine(config)
    assert engine._abort_controller is not None
    assert hasattr(engine._abort_controller, 'signal')
    assert hasattr(engine._abort_controller.signal, 'aborted')


@pytest.mark.asyncio
async def test_query_engine_preserves_provider(config):
    engine = QueryEngine(config)
    assert engine.config.provider == "openai"
