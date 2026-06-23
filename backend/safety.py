"""Safety guardrails — URL whitelist enforcement for all browser actions."""

import json
import re
from pathlib import Path
from urllib.parse import quote, urlparse

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_config() -> dict:
  with open(DATA_DIR / "config.json") as f:
    return json.load(f)


def _load_study_kb() -> dict:
  with open(DATA_DIR / "study_mode_kb.json") as f:
    return json.load(f)


def get_allowed_patterns() -> list[str]:
  """Return allowed URL prefix patterns from config + study KB."""
  config = _load_config()
  patterns = list(config.get("allowed_url_patterns", []))
  kb = _load_study_kb()
  for key in ("timer", "backup_timer", "notes", "checklist"):
    url = kb.get(key)
    if url and url not in patterns:
      patterns.append(url)
  for url in config.get("whitelisted_urls", []):
    if url not in patterns:
      patterns.append(url)
  return patterns


def is_url_allowed(url: str) -> bool:
  """Check if a URL matches a whitelisted pattern or exact whitelist entry."""
  if not url or not url.startswith("https://"):
    return False

  config = _load_config()
  kb = _load_study_kb()

  exact_whitelist = set(config.get("whitelisted_urls", []))
  exact_whitelist.update(
    v for k, v in kb.items() if isinstance(v, str) and v.startswith("https://")
  )

  if url in exact_whitelist:
    return True

  for pattern in get_allowed_patterns():
    if url.startswith(pattern):
      return True

  return False


def safe_google_search_url(query: str) -> str:
  """Build a safe Google search URL from a query string."""
  encoded = quote(query.strip())
  return f"https://www.google.com/search?q={encoded}"


def safe_youtube_search_url(query: str) -> str:
  """Build a safe YouTube search URL from a query string."""
  encoded = quote(query.strip())
  return f"https://www.youtube.com/results?search_query={encoded}"


def validate_or_reject(url: str) -> tuple[bool, str]:
  """Validate URL; return (ok, message)."""
  if is_url_allowed(url):
    return True, "allowed"
  return False, f"Blocked: URL not in whitelist — {url}"


BLOCKED_ACTIONS = {
  "shell",
  "exec",
  "delete",
  "remove",
  "email",
  "payment",
  "download",
  "admin",
  "sudo",
  "rm -rf",
}


def is_input_safe(text: str) -> bool:
  """Reject inputs that look like dangerous system commands."""
  lower = text.lower()
  for blocked in BLOCKED_ACTIONS:
    if blocked in lower:
      return False
  return True
