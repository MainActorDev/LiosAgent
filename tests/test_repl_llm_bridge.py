"""Tests for LLMBridge token/cost tracking."""

import pytest
from unittest.mock import MagicMock, patch
from agent.repl.llm_bridge import LLMBridge


@pytest.fixture
def bridge():
    """Create an LLMBridge with a mocked LLM."""
    with patch("agent.repl.llm_bridge.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.model_name = "gpt-4o"
        # get_llm() returns a factory; factory(role=...) returns the llm
        mock_factory = MagicMock(return_value=mock_llm)
        mock_get_llm.return_value = mock_factory
        b = LLMBridge()
        b._ensure_llm()
        return b


def test_initial_state(bridge):
    assert bridge.total_input_tokens == 0
    assert bridge.total_output_tokens == 0
    assert bridge.total_cost == 0.0
    assert bridge.model_name == "gpt-4o"


def test_accumulate_usage(bridge):
    bridge.accumulate_usage(input_tokens=100, output_tokens=50)
    assert bridge.total_input_tokens == 100
    assert bridge.total_output_tokens == 50
    assert bridge.total_tokens == 150

    bridge.accumulate_usage(input_tokens=200, output_tokens=100)
    assert bridge.total_input_tokens == 300
    assert bridge.total_output_tokens == 150
    assert bridge.total_tokens == 450


def test_cost_calculation_gpt4o(bridge):
    # gpt-4o: $2.50/1M input, $10.00/1M output
    bridge.accumulate_usage(input_tokens=1_000_000, output_tokens=1_000_000)
    assert abs(bridge.total_cost - 12.50) < 0.01


def test_cost_calculation_unknown_model():
    with patch("agent.repl.llm_bridge.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.model_name = "some-unknown-model"
        mock_factory = MagicMock(return_value=mock_llm)
        mock_get_llm.return_value = mock_factory
        b = LLMBridge()
        b._ensure_llm()
        b.accumulate_usage(input_tokens=1000, output_tokens=500)
        assert b.total_cost == 0.0
        assert b.total_tokens == 1500


def test_history_management(bridge):
    assert len(bridge.history) == 0
    bridge.add_system_prompt("You are helpful.")
    assert len(bridge.history) == 1
    bridge.add_user_message("Hello")
    assert len(bridge.history) == 2
    bridge.add_ai_message("Hi there!")
    assert len(bridge.history) == 3
