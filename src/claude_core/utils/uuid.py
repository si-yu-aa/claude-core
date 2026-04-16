"""UUID generation utilities."""

import uuid as uuid_lib

def generate_uuid() -> str:
    """Generate a random UUID string."""
    return str(uuid_lib.uuid4())

def generate_agent_id() -> str:
    """Generate an agent ID with prefix."""
    return f"agent_{generate_uuid()}"