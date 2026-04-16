import pytest
from claude_core.utils.uuid import generate_uuid, generate_agent_id

def test_generate_uuid():
    uuid = generate_uuid()
    assert isinstance(uuid, str)
    assert len(uuid) == 36  # standard UUID format
    assert uuid.count("-") == 4

def test_generate_uuid_unique():
    uuids = [generate_uuid() for _ in range(100)]
    assert len(set(uuids)) == 100

def test_generate_agent_id():
    agent_id = generate_agent_id()
    assert isinstance(agent_id, str)
    assert agent_id.startswith("agent_")