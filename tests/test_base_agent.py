"""Tests for base agent class."""
import pytest
import pytest_asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from src.agent.agents.base_agent import BaseAgent
from src.agent.database.agent_schema import init_agent_schema
from src.agent.database.agent_operations import AgentOperations


class ConcreteAgent(BaseAgent):
    """Concrete implementation for testing."""

    agent_type = "test_agent"

    async def run(self, input_data: dict) -> dict:
        return {"result": "test", "input": input_data}


@pytest_asyncio.fixture
async def db_ops():
    """Create temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    await init_agent_schema(db_path)
    ops = AgentOperations(db_path)
    yield ops
    db_path.unlink()


@pytest.mark.asyncio
async def test_base_agent_save_output(db_ops):
    """Test that base agent saves output to database."""
    agent = ConcreteAgent(db_ops=db_ops)

    await agent._save_output(
        session_id="test-session",
        symbol="BTCUSDT",
        input_data={"test": "input"},
        output_data={"test": "output"},
        tokens_used=100,
        duration_ms=500
    )

    outputs = await db_ops.get_agent_outputs_by_session("test-session")
    assert len(outputs) == 1
    assert outputs[0]["agent_type"] == "test_agent"
    assert outputs[0]["symbol"] == "BTCUSDT"


@pytest.mark.asyncio
async def test_base_agent_run_with_tracking(db_ops):
    """Test run_with_tracking saves output."""
    agent = ConcreteAgent(db_ops=db_ops)

    result = await agent.run_with_tracking(
        session_id="test-session-2",
        symbol="ETHUSDT",
        input_data={"symbol": "ETHUSDT"}
    )

    assert result["result"] == "test"

    # Verify output was saved
    outputs = await db_ops.get_agent_outputs_by_session("test-session-2")
    assert len(outputs) == 1


@pytest.mark.asyncio
async def test_base_agent_requires_agent_type():
    """Test that agent_type must be defined."""

    class BadAgent(BaseAgent):
        async def run(self, input_data: dict) -> dict:
            return {}

    with pytest.raises(NotImplementedError):
        BadAgent(db_ops=MagicMock())
