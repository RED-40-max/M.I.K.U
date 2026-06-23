"""MIKU agent state — shared across all LangGraph nodes."""

from typing import Any, Optional, TypedDict


class MIKUState(TypedDict, total=False):
  """Visible state passed through the LangGraph workflow."""

  raw_input: str
  input_type: str  # gesture | voice | text | button
  gesture: Optional[str]
  transcript: str
  intent: str
  retrieved_context: dict[str, Any]
  plan: list[str]
  tool_calls: list[dict[str, Any]]
  observations: list[str]
  recovery_steps: list[str]
  response: str
  errors: list[str]
  timestamp: str
  miku_status: str  # asleep | awake | listening | thinking | acting | speaking
  should_speak: bool
  pending_music_recovery: bool


def initial_state() -> MIKUState:
  """Return a fresh state dict for a new agent run."""
  return {
    "raw_input": "",
    "input_type": "text",
    "gesture": None,
    "transcript": "",
    "intent": "unknown",
    "retrieved_context": {},
    "plan": [],
    "tool_calls": [],
    "observations": [],
    "recovery_steps": [],
    "response": "",
    "errors": [],
    "timestamp": "",
    "miku_status": "thinking",
    "should_speak": False,
    "pending_music_recovery": False,
  }
