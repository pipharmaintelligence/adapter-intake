"""Version-owned optional portfolio reflection configuration."""
from __future__ import annotations

from typing import Any

MAX_PORTFOLIO_REVIEW_PASSES = 3


def portfolio_review_passes(inputs: Any) -> int:
    variables = inputs.get("variables", {})
    if not isinstance(variables, dict):
        raise ValueError("inputs.variables must be an object.")
    passes = variables.get("portfolio_review_passes", 1)
    if type(passes) is not int or not 1 <= passes <= MAX_PORTFOLIO_REVIEW_PASSES:
        raise ValueError("variables.portfolio_review_passes must be an integer from 1 to 3.")
    return passes
