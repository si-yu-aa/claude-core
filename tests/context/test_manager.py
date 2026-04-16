import pytest
from claude_core.context.manager import ContextManager
from claude_core.context.budget import TokenBudget

@pytest.fixture
def context_manager():
    return ContextManager(max_tokens=100000, model="gpt-4o")

def test_context_manager_initialization(context_manager):
    assert context_manager._max_tokens == 100000
    assert context_manager._model == "gpt-4o"

@pytest.mark.asyncio
async def test_should_compact_false_when_under_threshold(context_manager):
    # Under threshold should not compact
    result = await context_manager.should_compact([], 50000)
    assert result is False

@pytest.mark.asyncio
async def test_should_compact_true_when_over_threshold(context_manager):
    # Over threshold should compact
    result = await context_manager.should_compact([], 90000)
    assert result is True

def test_token_budget_initialization():
    budget = TokenBudget(max_tokens=100000)
    assert budget.max_tokens == 100000
    assert budget.used_tokens == 0

def test_token_budget_add_usage():
    budget = TokenBudget(max_tokens=100000)
    budget.add_usage(prompt_tokens=1000, completion_tokens=500)
    assert budget.used_tokens == 1500

def test_token_budget_remaining():
    budget = TokenBudget(max_tokens=100000)
    budget.add_usage(prompt_tokens=1000, completion_tokens=500)
    assert budget.remaining_tokens == 98500