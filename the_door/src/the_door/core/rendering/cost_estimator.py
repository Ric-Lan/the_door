"""Cost estimator — estimate token count and API cost without LLM calls."""
from __future__ import annotations

from the_door.models import CostEstimate, StructureJSON


# Approximate pricing per 1K tokens
_PRICING = {
    "openai": {"input": 0.005, "output": 0.015},
    "anthropic": {"input": 0.003, "output": 0.015},
    "ollama": {"input": 0.0, "output": 0.0},
}

# Approximate tokens per node for input (structure description + constraint prompt)
_TOKENS_PER_NODE_INPUT = 150
# Approximate tokens per node for output (feature description)
_TOKENS_PER_NODE_OUTPUT = 80
# Base constraint prompt tokens
_BASE_PROMPT_TOKENS = 500
# Nodes per batch (approximate)
_NODES_PER_BATCH = 10


class CostEstimator:
    """Estimate token consumption and API cost without making LLM calls."""

    def __init__(self, provider_name: str, model_name: str) -> None:
        self._provider = provider_name
        self._model = model_name

    def estimate(self, structure: StructureJSON) -> CostEstimate:
        """Calculate estimated cost based on structure size and provider pricing."""
        num_nodes = len(structure.nodes)

        if num_nodes == 0:
            return CostEstimate(
                total_input_tokens=0,
                total_output_tokens=0,
                estimated_cost_usd=0.0,
                provider=self._provider,
                model=self._model,
                batch_count=0,
                is_local=(self._provider == "ollama"),
            )

        # Calculate batch count
        batch_count = max(1, (num_nodes + _NODES_PER_BATCH - 1) // _NODES_PER_BATCH)
        batch_count = min(batch_count, 5)  # Max 5 batches

        # Estimate tokens
        input_tokens = (num_nodes * _TOKENS_PER_NODE_INPUT) + (_BASE_PROMPT_TOKENS * batch_count)
        output_tokens = num_nodes * _TOKENS_PER_NODE_OUTPUT

        # Calculate cost
        is_local = self._provider == "ollama"
        if is_local:
            cost = 0.0
        else:
            pricing = _PRICING.get(self._provider, _PRICING["openai"])
            cost = (input_tokens / 1000 * pricing["input"]) + (
                output_tokens / 1000 * pricing["output"]
            )

        return CostEstimate(
            total_input_tokens=input_tokens,
            total_output_tokens=output_tokens,
            estimated_cost_usd=round(cost, 6),
            provider=self._provider,
            model=self._model,
            batch_count=batch_count,
            is_local=is_local,
        )
