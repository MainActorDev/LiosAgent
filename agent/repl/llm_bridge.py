"""Async-friendly LLM wrapper with streaming and token/cost tracking."""

from __future__ import annotations

from typing import Generator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


# Pricing per 1M tokens: (input_cost, output_cost)
PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-3.5-turbo": (0.50, 1.50),
    "glm-4": (1.00, 1.00),
    "glm-5.1": (1.00, 1.00),
}

SYSTEM_PROMPT = """You are Lios, an Autonomous iOS Engineer.
The user is talking to you via your interactive CLI mode.
You can help them brainstorm, explain how to use the CLI, or answer general questions.
The available CLI commands are: /epic <name>, /story <epic> <id>, /execute <vault>, /board.
Keep your answers concise, helpful, and formatted in markdown."""

INTAKE_SYSTEM_PROMPT = """You are an expert iOS Product Manager. The user wants to build a new feature.
They will provide an initial PRD or description. Ask clarifying questions until you have enough detail to write a comprehensive technical PRD.
Do not write the PRD yet. Just ask 1-2 focused questions at a time to clarify the user's intent.
Once you have enough detail to proceed with architecture, or if the user explicitly says they are done, output exactly 'READY_TO_ARCHITECT' on a new line. Do not output this prematurely."""


def _get_pricing(model_name: str) -> tuple[float, float]:
    """Look up pricing for a model name, matching by prefix."""
    for prefix, costs in PRICING.items():
        if model_name.startswith(prefix):
            return costs
    return (0.0, 0.0)


def get_llm():
    """Lazy import to avoid circular deps."""
    from agent.llm_factory import get_llm as factory_get_llm

    return factory_get_llm


class LLMBridge:
    """Wraps LangChain ChatOpenAI with streaming, history, and cost tracking."""

    def __init__(self) -> None:
        self._llm = None
        self._model_name: str = ""
        self.history: list = []
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_cost: float = 0.0

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    def _ensure_llm(self) -> None:
        """Initialize the LLM on first use."""
        if self._llm is None:
            factory = get_llm()
            self._llm = factory(role="planning")
            self._model_name = getattr(self._llm, "model_name", "unknown")

    def add_system_prompt(self, content: str) -> None:
        self.history.append(SystemMessage(content=content))

    def add_user_message(self, content: str) -> None:
        self.history.append(HumanMessage(content=content))

    def add_ai_message(self, content: str) -> None:
        self.history.append(AIMessage(content=content))

    def accumulate_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Add token counts and compute incremental cost."""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        input_price, output_price = _get_pricing(self._model_name)
        self.total_cost += (input_tokens * input_price / 1_000_000) + (
            output_tokens * output_price / 1_000_000
        )

    def stream(self, messages: list | None = None) -> Generator[str, None, dict]:
        """Stream LLM response, yielding content chunks.

        Args:
            messages: If provided, use these instead of self.history.

        Yields:
            String chunks of the response content.

        Returns:
            A dict with ``usage_metadata`` (if available) after the generator
            is exhausted. Access via generator's ``.value`` attribute is not
            standard — callers should use ``accumulate_usage`` after streaming.
        """
        self._ensure_llm()
        msgs = messages if messages is not None else self.history

        full_content = ""
        usage_metadata = {}

        for chunk in self._llm.stream(msgs):
            token = chunk.content
            if token:
                full_content += token
                yield token

            # LangChain populates usage_metadata on the final chunk
            meta = getattr(chunk, "usage_metadata", None)
            if meta:
                usage_metadata = meta

        # Accumulate usage if metadata was provided
        if usage_metadata:
            self.accumulate_usage(
                input_tokens=usage_metadata.get("input_tokens", 0),
                output_tokens=usage_metadata.get("output_tokens", 0),
            )

        return usage_metadata
