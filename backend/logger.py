"""Trace logging — appends full agent traces to logs.json."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LOGS_PATH = DATA_DIR / "logs.json"


def _load_logs() -> list[dict[str, Any]]:
  if not LOGS_PATH.exists():
    return []
  with open(LOGS_PATH) as f:
    return json.load(f)


def _save_logs(logs: list[dict[str, Any]]) -> None:
  LOGS_PATH.parent.mkdir(parents=True, exist_ok=True)
  with open(LOGS_PATH, "w") as f:
    json.dump(logs, f, indent=2)


def build_trace(state: dict[str, Any]) -> dict[str, Any]:
  """Build a trace object from agent state."""
  return {
    "timestamp": state.get("timestamp") or datetime.now(timezone.utc).isoformat(),
    "raw_input": state.get("raw_input", ""),
    "input_type": state.get("input_type", ""),
    "gesture": state.get("gesture"),
    "transcript": state.get("transcript", ""),
    "intent": state.get("intent", ""),
    "retrieved_context": state.get("retrieved_context", {}),
    "plan": state.get("plan", []),
    "tool_calls": state.get("tool_calls", []),
    "observations": state.get("observations", []),
    "recovery_steps": state.get("recovery_steps", []),
    "response": state.get("response", ""),
    "errors": state.get("errors", []),
  }


def append_trace(state: dict[str, Any]) -> dict[str, Any]:
  """Append a trace to logs.json and return the trace."""
  trace = build_trace(state)
  logs = _load_logs()
  logs.append(trace)
  _save_logs(logs)
  return trace


def get_recent_traces(limit: int = 20) -> list[dict[str, Any]]:
  """Return the most recent traces."""
  logs = _load_logs()
  return logs[-limit:]
