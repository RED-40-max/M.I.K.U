"""LangChain tools — safe browser actions, Study Mode, memory, and TTS."""

import random
import webbrowser
from typing import Any

from langchain_core.tools import tool

from backend.memory import get_preference, load_study_kb, set_preference
from backend.safety import (
  safe_google_search_url,
  safe_youtube_search_url,
  validate_or_reject,
)
from backend.logger import append_trace as _log_trace_event


def _open_safe_url(url: str) -> str:
  """Open URL only if it passes safety whitelist."""
  ok, msg = validate_or_reject(url)
  if not ok:
    return msg
  webbrowser.open(url)
  return f"opened {url}"


@tool
def open_url(url: str) -> str:
  """Open a whitelisted URL in the default browser."""
  return _open_safe_url(url)


@tool
def google_search(query: str) -> str:
  """Open a Google search for the given query."""
  url = safe_google_search_url(query)
  return _open_safe_url(url)


@tool
def youtube_search(query: str) -> str:
  """Open a YouTube search for the given query."""
  url = safe_youtube_search_url(query)
  return _open_safe_url(url)


@tool
def youtube_search_random_top3(query: str) -> str:
  """
  Search YouTube and try to open one of the top 3 results.
  MVP fallback: opens search results page and logs simulated selection.
  """
  search_url = safe_youtube_search_url(query)

  # Attempt lightweight scrape — if brittle, fall back gracefully
  try:
    import requests
    from bs4 import BeautifulSoup

    headers = {"User-Agent": "Mozilla/5.0 (compatible; MIKU/1.0)"}
    resp = requests.get(search_url, headers=headers, timeout=5)
    if resp.ok:
      soup = BeautifulSoup(resp.text, "html.parser")
      links = []
      for a in soup.select("a#video-title"):
        href = a.get("href", "")
        if href.startswith("/watch"):
          links.append(f"https://www.youtube.com{href}")
        if len(links) >= 3:
          break
      if links:
        chosen = random.choice(links)
        result = _open_safe_url(chosen)
        return f"{result} (selected 1 of top {len(links)} via scrape)"
  except Exception:
    pass

  # Fallback: open search page and simulate top-3 pick in logs
  result = _open_safe_url(search_url)
  simulated = random.randint(1, 3)
  return (
    f"{result} (fallback: top-3 selection simulated — picked result #{simulated})"
  )


@tool
def start_study_mode() -> str:
  """Open Study Mode: music, timer, notes, and checklist."""
  kb = load_study_kb()
  mem = get_preference("preferred_music")
  if mem:
    music_query = f"{mem} study music"
  else:
    music_query = kb.get("music_query", "lofi study music")

  results = []
  results.append(youtube_search_random_top3.invoke({"query": music_query}))
  timer_url = kb.get("timer", "https://pomofocus.io")
  results.append(_open_safe_url(timer_url))
  results.append(_open_safe_url(kb.get("notes", "https://docs.google.com/document/create")))
  results.append(_open_safe_url(kb.get("checklist", "https://keep.google.com")))
  return "; ".join(results)


@tool
def save_preference(key: str, value: str) -> str:
  """Save a user preference to memory.json."""
  set_preference(key, value)
  return f"saved {key}={value}"


@tool
def log_event(event: str) -> str:
  """Append an event string to logs."""
  from datetime import datetime, timezone

  trace = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "raw_input": event,
    "input_type": "event",
    "intent": "log",
    "retrieved_context": {},
    "plan": [],
    "tool_calls": [],
    "observations": [event],
    "recovery_steps": [],
    "response": "",
    "errors": [],
  }
  _log_trace_event(trace)
  return f"logged: {event}"


@tool
def speak_text(text: str) -> str:
  """Speak text aloud using pyttsx3 or edge-tts fallback."""
  from backend.tts import speak

  speak(text)
  return f"spoke: {text[:80]}..."


# All tools for LangGraph tool_node
ALL_TOOLS = [
  open_url,
  google_search,
  youtube_search,
  youtube_search_random_top3,
  start_study_mode,
  save_preference,
  log_event,
  speak_text,
]

TOOL_MAP = {t.name: t for t in ALL_TOOLS}
