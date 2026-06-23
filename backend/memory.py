"""Memory persistence — reads/writes user preferences to memory.json."""

import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MEMORY_PATH = DATA_DIR / "memory.json"


def load_memory() -> dict[str, Any]:
  """Load user memory from disk."""
  if not MEMORY_PATH.exists():
    return {}
  with open(MEMORY_PATH) as f:
    return json.load(f)


def save_memory(data: dict[str, Any]) -> None:
  """Persist user memory to disk."""
  MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
  with open(MEMORY_PATH, "w") as f:
    json.dump(data, f, indent=2)


def get_preference(key: str, default: Any = None) -> Any:
  """Get a single preference from memory."""
  mem = load_memory()
  return mem.get(key, default)


def set_preference(key: str, value: Any) -> dict[str, Any]:
  """Update a preference and save — used by save_preference tool and recovery."""
  mem = load_memory()
  mem[key] = value
  save_memory(mem)
  return mem


def load_study_kb() -> dict[str, Any]:
  """Load Study Mode knowledge base."""
  kb_path = DATA_DIR / "study_mode_kb.json"
  with open(kb_path) as f:
    return json.load(f)
