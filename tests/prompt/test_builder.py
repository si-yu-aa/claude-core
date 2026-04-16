import pytest
from claude_core.prompt.builder import SystemPromptBuilder

@pytest.fixture
def builder():
    return SystemPromptBuilder(
        base_instructions="You are a helpful coding assistant.",
        tools=[],
        agents=[],
    )

def test_builder_initialization(builder):
    assert builder.base_instructions == "You are a helpful coding assistant."

def test_builder_build_empty_context(builder):
    prompt = builder.build(user_context={}, system_context={})
    assert "You are a helpful coding assistant." in prompt

def test_builder_build_with_context(builder):
    builder_with_context = SystemPromptBuilder(
        base_instructions="You are a helpful assistant.",
        tools=[],
        agents=[],
    )
    prompt = builder_with_context.build(
        user_context={"current_file": "main.py"},
        system_context={"os": "Linux"},
    )
    assert "current_file" in prompt
    assert "main.py" in prompt
    assert "os" in prompt
    assert "Linux" in prompt