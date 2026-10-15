"""Versioned, package-local prompt sources; never caller-selected instructions."""
from pathlib import Path
PROMPT_VERSION = "1.0.0"
_ROOT = Path(__file__).resolve().parent / "prompts"
COMMON_PROMPT = (_ROOT / "common.md").read_text(encoding="utf-8")
PROMPTS = {role: (_ROOT / (role + ".md")).read_text(encoding="utf-8") for role in (
    "trial_researcher", "literature_researcher", "event_researcher", "outcome_adjudicator",
    "hypothesis_analyst", "evidence_critic")}
