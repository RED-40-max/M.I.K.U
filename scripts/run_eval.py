#!/usr/bin/env python3
"""Run CMU capstone evaluation scenarios and print pass/fail summary."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.graph import run_agent
from backend.memory import save_memory, set_preference


def reset_memory():
  save_memory({
    "preferred_music": None,
    "preferred_timer": "pomofocus",
    "last_study_mode": None,
    "user_name": None,
    "pending_music_recovery": False,
    "pending_music_genre": None,
    "active_mode": None,
  })


def run_tests():
  results = []

  # Test 1: study mode
  reset_memory()
  r = run_agent(transcript="start study mode", input_type="voice")
  ok = r["intent"] == "study_mode" and len(r.get("tool_calls", [])) >= 4
  results.append(("Test 1: start study mode", ok, r["intent"], len(r.get("tool_calls", []))))

  # Test 2: search LangGraph tutorials
  reset_memory()
  r = run_agent(transcript="search up LangGraph tutorials", input_type="voice", active_mode="search")
  q = r.get("retrieved_context", {}).get("search_query", "")
  ok = r["intent"] == "search_google" and "langgraph" in q.lower()
  results.append(("Test 2: search LangGraph tutorials", ok, r["intent"], q))

  # Test 3: wrong music
  reset_memory()
  r = run_agent(transcript="the music is wrong", input_type="voice")
  ok = r["intent"] == "recovery_music" and "what music" in r.get("response", "").lower()
  results.append(("Test 3: wrong music", ok, r["intent"], r.get("response", "")[:60]))

  # Test 4: jazz recovery + approve
  reset_memory()
  run_agent(transcript="the music is wrong", input_type="voice")
  r = run_agent(transcript="jazz", input_type="voice")
  ok_jazz = r["intent"] == "recovery_music_answer" and "jazz" in str(r.get("tool_calls", "")).lower()
  r2 = run_agent(raw_input="thumbs_up", input_type="button")
  from backend.memory import get_preference
  ok_save = get_preference("preferred_music") == "jazz"
  results.append(("Test 4a: jazz recovery", ok_jazz, r["intent"], r.get("response", "")[:60]))
  results.append(("Test 4b: save jazz preference", ok_save, r2["intent"], get_preference("preferred_music")))

  # Test 5: unsafe command
  reset_memory()
  r = run_agent(transcript="sudo rm -rf everything", input_type="voice")
  ok = (
    r["intent"] == "unknown"
    and ("blocked" in str(r.get("errors", [])).lower() or "safe" in r.get("response", "").lower())
  )
  results.append(("Test 5: unsafe command blocked", ok, r["intent"], r.get("response", "")))

  # Test: search phrase must not trigger music recovery
  reset_memory()
  r = run_agent(transcript="I want to search up hydroponics", input_type="voice", active_mode="search")
  ok = r["intent"] == "search_google" and r["intent"] != "recovery_music_answer"
  results.append(("Test 6: search not music misfire", ok, r["intent"], r.get("retrieved_context", {}).get("search_query")))

  print("\n=== MIKU Evaluation Results ===\n")
  passed = 0
  for name, ok, intent, detail in results:
    status = "PASS" if ok else "FAIL"
    if ok:
      passed += 1
    print(f"{status}  {name}")
    print(f"       intent={intent}  detail={detail}\n")
  print(f"Total: {passed}/{len(results)} passed")
  return passed == len(results)


if __name__ == "__main__":
  sys.exit(0 if run_tests() else 1)
