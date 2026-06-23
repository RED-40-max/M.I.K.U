"""LangGraph workflow — MIKU agent with named nodes and full traceability."""

import os
import re
from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, StateGraph

from backend.memory import get_preference, load_study_kb, set_preference
from backend.safety import is_input_safe
from backend.state import MIKUState
from backend.tools import TOOL_MAP

# ---------------------------------------------------------------------------
# Optional OpenAI — used only when OPENAI_API_KEY is set
# ---------------------------------------------------------------------------

def _llm_chat(prompt: str, user_text: str) -> str | None:
  """Use ChatOpenAI if available; otherwise return None for rule-based fallback."""
  if not os.environ.get("OPENAI_API_KEY"):
    return None
  try:
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    resp = llm.invoke(f"{prompt}\n\nUser: {user_text}")
    return resp.content
  except Exception:
    return None


# ---------------------------------------------------------------------------
# Intent patterns (rule-based, deterministic)
# ---------------------------------------------------------------------------

MUSIC_COMPLAINT_PATTERNS = [
  r"wrong music",
  r"the music is wrong",
  r"change music",
  r"change the music",
  r"different music",
  r"not this music",
]

MUSIC_REQUEST_PATTERNS = [
  r"(?:play|use|i want)\s+(.+?)\s+study music",
  r"(?:play|use)\s+(.+?)\s+instead",
  r"(?:i want)\s+(jazz|lofi|bossa nova|anime|classical|hip hop|rock|pop|electronic)(?:\s+instead)?",
]

STUDY_PATTERNS = [r"start study", r"study mode", r"begin study", r"open study"]
GOOGLE_PATTERNS = [r"search (?:up |for )?(.+)", r"google (.+)", r"look up (.+)"]
YOUTUBE_PATTERNS = [r"find (.+?) (?:on )?youtube", r"youtube (.+)", r"play (.+?) music"]
CHAT_GREETINGS = [r"hello", r"hi miku", r"hey miku", r"how are you"]
APPROVAL_PATTERNS = [r"yes", r"better", r"that'?s good", r"perfect", r"thumbs up", r"approve"]
THUMBS_DOWN = [r"thumbs down", r"no", r"still wrong", r"not better"]


def _match_any(text: str, patterns: list[str]) -> re.Match | None:
  for p in patterns:
    m = re.search(p, text, re.IGNORECASE)
    if m:
      return m
  return None


# ---------------------------------------------------------------------------
# LangGraph nodes
# ---------------------------------------------------------------------------

def input_node(state: MIKUState) -> MIKUState:
  """Receives gesture/text/voice input and normalizes transcript."""
  state = dict(state)
  state["timestamp"] = state.get("timestamp") or datetime.now(timezone.utc).isoformat()
  state["miku_status"] = "thinking"

  raw = state.get("raw_input", "")
  gesture = state.get("gesture")
  input_type = state.get("input_type", "text")

  # Gesture-only: set mode/status — never pass gesture name as search query
  if input_type == "gesture" and gesture:
    gesture_intents = {
      "open_hand": "wake",
      "closed_fist": "sleep",
      "closed_pinch": "listen",
      "one_finger": "listen",      # frontend sets study mode then listens
      "two_fingers": "listen",     # frontend sets search mode then listens
      "three_fingers": "listen",   # frontend sets chat mode then listens
    }
    state["intent"] = gesture_intents.get(gesture, "unknown")
    state["transcript"] = ""
    return state

  if input_type == "button":
    button_intents = {
      "wake": "wake",
      "sleep": "sleep",
      "listen": "listen",
      "study_mode": "listen",
      "search_mode": "listen",
      "chat_mode": "listen",
      "thumbs_up": "approve_music",
      "thumbs_down": "reject_music",
    }
    mapped = button_intents.get(raw, "unknown")
    state["intent"] = mapped
    state["transcript"] = raw if mapped in ("approve_music", "reject_music") else ""
    return state

  # Text/voice: use transcript
  transcript = state.get("transcript") or raw
  state["transcript"] = transcript.strip()
  return state


def intent_node(state: MIKUState) -> MIKUState:
  """Map input to intent using rules (or LLM if available)."""
  state = dict(state)

  # Skip if gesture/button already set intent
  if state.get("input_type") in ("gesture", "button") and state.get("intent") in (
    "wake", "sleep", "listen", "approve_music", "reject_music",
  ):
    return state

  text = state.get("transcript", "").lower().strip()
  if not text:
    state["intent"] = "unknown"
    state["response"] = "I didn't catch that. Could you repeat?"
    return state

  if not is_input_safe(text):
    state["intent"] = "unknown"
    state["response"] = "I can't do that — it's not a safe action."
    state["errors"] = state.get("errors", []) + ["blocked unsafe input"]
    return state

  # Active mode from gesture/button (search / study / chat)
  active_mode = state.get("retrieved_context", {}).get("active_mode") or get_preference("active_mode")

  # Pending music recovery — user is answering "what music?"
  if get_preference("pending_music_recovery"):
    state["intent"] = "recovery_music_answer"
    genre = state.get("transcript", "").strip()
    genre = re.sub(
      r"^(i want|play|use|the|a)\s+",
      "",
      genre,
      flags=re.IGNORECASE,
    ).strip()
    if genre:
      state["retrieved_context"] = {
        **state.get("retrieved_context", {}),
        "parsed_music": genre,
      }
    return state

  # Music complaint detection
  if _match_any(text, MUSIC_COMPLAINT_PATTERNS):
    state["intent"] = "recovery_music"
    return state

  # Search / study before loose music patterns (avoid "I want to search..." misfire)
  if _match_any(text, STUDY_PATTERNS) or active_mode == "study":
    state["intent"] = "study_mode"
    return state

  m = _match_any(text, YOUTUBE_PATTERNS)
  if m:
    state["intent"] = "search_youtube"
    state["retrieved_context"] = {**state.get("retrieved_context", {}), "search_query": m.group(1).strip()}
    return state

  m = _match_any(text, GOOGLE_PATTERNS)
  if m:
    state["intent"] = "search_google"
    state["retrieved_context"] = {**state.get("retrieved_context", {}), "search_query": m.group(1).strip()}
    return state

  if active_mode == "search":
    query = _extract_search_query(state.get("transcript", ""))
    state["intent"] = "search_google"
    state["retrieved_context"] = {**state.get("retrieved_context", {}), "search_query": query}
    return state

  m = _match_any(text, MUSIC_REQUEST_PATTERNS)
  if m:
    state["intent"] = "recovery_music_answer"
    state["retrieved_context"] = {
      **state.get("retrieved_context", {}),
      "parsed_music": m.group(1).strip(),
    }
    return state

  if _match_any(text, APPROVAL_PATTERNS):
    state["intent"] = "approve_music"
    return state

  if _match_any(text, THUMBS_DOWN):
    state["intent"] = "reject_music"
    return state

  if _match_any(text, CHAT_GREETINGS):
    state["intent"] = "chat"
    return state

  # Optional LLM for ambiguous input
  llm_resp = _llm_chat(
    "You are MIKU, a friendly desktop assistant. Classify intent as one of: "
    "study_mode, search_google, search_youtube, chat, unknown. Reply with just the intent.",
    text,
  )
  if llm_resp:
    intent = llm_resp.strip().lower().replace(" ", "_")
    if intent in ("study_mode", "search_google", "search_youtube", "chat"):
      state["intent"] = intent
      if intent == "search_google" and not state.get("retrieved_context", {}).get("search_query"):
        state["retrieved_context"] = {
          **state.get("retrieved_context", {}),
          "search_query": _extract_search_query(state.get("transcript", "")),
        }
      return state

  # Chat mode default
  if active_mode == "chat":
    state["intent"] = "chat"
    return state

  # Default to chat for general conversation
  state["intent"] = "chat"
  return state


def _extract_search_query(transcript: str) -> str:
  """Pull a search query from speech — LLM if available, else strip filler words."""
  raw = transcript.strip()
  llm = _llm_chat(
    "Extract only the search query from the user's request. "
    "Reply with just the query, no quotes. Example: 'search up LangGraph tutorials' -> LangGraph tutorials",
    raw,
  )
  if llm:
    return llm.strip().strip('"')
  # Rule-based strip
  q = re.sub(
    r"^(please\s+)?(search\s+(up\s+)?(for\s+)?|google\s+|look\s+up\s+|find\s+)",
    "",
    raw,
    flags=re.IGNORECASE,
  ).strip()
  return q or raw


def retrieve_memory_node(state: MIKUState) -> MIKUState:
  """Retrieve Study Mode preferences and memory context (RAG-lite)."""
  state = dict(state)
  kb = load_study_kb()
  mem = {
    "preferred_music": get_preference("preferred_music"),
    "preferred_timer": get_preference("preferred_timer", "pomofocus"),
    "pending_music_recovery": get_preference("pending_music_recovery", False),
    "active_mode": get_preference("active_mode"),
    "music_query": kb.get("music_query"),
    "backup_music_query": kb.get("backup_music_query"),
    "timer": kb.get("timer"),
    "backup_timer": kb.get("backup_timer"),
    "notes": kb.get("notes"),
    "checklist": kb.get("checklist"),
  }

  preferred = mem.get("preferred_music")
  if preferred:
    mem["music_query"] = f"{preferred} study music"

  ctx = state.get("retrieved_context", {})
  ctx.update(mem)
  state["retrieved_context"] = ctx
  return state


def _score_study_candidate(candidate: dict[str, Any], ctx: dict[str, Any]) -> float:
  """Score a Study Mode candidate plan (ToT-lite)."""
  preferred = ctx.get("preferred_music")
  score = 0.0
  # User preference match (25%)
  if preferred and preferred.lower() in candidate.get("music_query", "").lower():
    score += 25
  elif not preferred and "lofi" in candidate.get("music_query", "").lower():
    score += 18
  elif preferred:
    score += 8
  # Retrieval relevance — KB URLs present (30%)
  if all(candidate.get(k) for k in ("timer", "notes", "checklist")):
    score += 30
  # Tool availability — whitelisted HTTPS URLs (30%)
  if str(candidate.get("timer", "")).startswith("https://"):
    score += 30
  # Recovery readiness — backup timer variant (15%)
  if candidate.get("uses_backup_timer"):
    score += 10
  else:
    score += 15
  return score


def _build_study_candidates(ctx: dict[str, Any]) -> list[dict[str, Any]]:
  """Generate Study Mode candidate plans for ToT selection."""
  preferred = ctx.get("preferred_music")
  return [
    {
      "id": "A",
      "label": "LoFi + Pomofocus + Docs + Keep",
      "music_query": ctx.get("music_query", "lofi study music"),
      "timer": ctx.get("timer", "https://pomofocus.io"),
      "notes": ctx.get("notes", "https://docs.google.com/document/create"),
      "checklist": ctx.get("checklist", "https://keep.google.com"),
      "uses_backup_timer": False,
    },
    {
      "id": "B",
      "label": "Bossa Nova + backup timer",
      "music_query": ctx.get("backup_music_query", "bossa nova study music"),
      "timer": ctx.get("backup_timer", "https://www.online-stopwatch.com"),
      "notes": ctx.get("notes", "https://docs.google.com/document/create"),
      "checklist": ctx.get("checklist", "https://keep.google.com"),
      "uses_backup_timer": True,
    },
    {
      "id": "C",
      "label": "Preferred music + Pomofocus",
      "music_query": (
        f"{preferred} study music" if preferred else ctx.get("music_query", "lofi study music")
      ),
      "timer": ctx.get("timer", "https://pomofocus.io"),
      "notes": ctx.get("notes", "https://docs.google.com/document/create"),
      "checklist": ctx.get("checklist", "https://keep.google.com"),
      "uses_backup_timer": False,
    },
  ]


def plan_node(state: MIKUState) -> MIKUState:
  """Create action plan; Study Mode uses ToT candidate scoring."""
  state = dict(state)
  intent = state.get("intent", "unknown")
  ctx = state.get("retrieved_context", {})
  text = state.get("transcript", "")

  if intent == "study_mode":
    candidates = _build_study_candidates(ctx)
    scored = []
    for c in candidates:
      s = _score_study_candidate(c, ctx)
      scored.append({**c, "score": round(s, 1)})
    scored.sort(key=lambda x: x["score"], reverse=True)
    winner = scored[0]
    ctx["candidate_plans"] = [
      {
        "id": c["id"],
        "label": c["label"],
        "score": c["score"],
        "music_query": c["music_query"],
      }
      for c in scored
    ]
    ctx["selected_plan_id"] = winner["id"]
    ctx["music_query"] = winner["music_query"]
    ctx["timer"] = winner["timer"]
    ctx["notes"] = winner["notes"]
    ctx["checklist"] = winner["checklist"]
    state["retrieved_context"] = ctx
    state["plan"] = [
      f"[ToT selected Plan {winner['id']} score={winner['score']}] {winner['label']}",
      f"search YouTube for {winner['music_query']}",
      f"open timer at {winner['timer']}",
      f"open notes at {winner['notes']}",
      f"open checklist at {winner['checklist']}",
    ]
    return state

  plans: dict[str, list[str]] = {
    "wake": ["set MIKU status to awake", "greet user"],
    "sleep": ["set MIKU status to asleep"],
    "listen": ["wait for user voice command"],
    "study_mode": [
      f"search YouTube for {ctx.get('music_query', 'lofi study music')}",
      f"open timer at {ctx.get('timer')}",
      f"open notes at {ctx.get('notes')}",
      f"open checklist at {ctx.get('checklist')}",
    ],
    "search_google": [
      f"google search for {ctx.get('search_query', text)}",
    ],
    "search_youtube": [
      f"youtube search for {ctx.get('search_query', text)}",
    ],
    "recovery_music": [
      "detect music complaint",
      "ask user what music they want",
      "set pending_music_recovery flag",
    ],
    "recovery_music_answer": [
      "parse desired music genre",
      f"search YouTube for {{genre}} study music",
      "ask if music is better",
    ],
    "approve_music": [
      "save preferred_music from pending",
      "clear pending_music_recovery",
    ],
    "reject_music": [
      "ask user for different music",
      "keep pending_music_recovery",
    ],
    "chat": ["generate friendly response"],
    "unknown": ["ask user to clarify"],
  }

  state["plan"] = plans.get(intent, ["handle unknown intent"])
  return state


def tool_node(state: MIKUState) -> MIKUState:
  """Execute LangChain tools based on intent and plan."""
  state = dict(state)
  state["miku_status"] = "acting"
  intent = state.get("intent", "unknown")
  ctx = state.get("retrieved_context", {})
  tool_calls = list(state.get("tool_calls", []))
  observations = list(state.get("observations", []))

  def _run(tool_name: str, args: dict) -> str:
    tool = TOOL_MAP.get(tool_name)
    if not tool:
      return f"unknown tool: {tool_name}"
    result = tool.invoke(args)
    tool_calls.append({"tool": tool_name, "args": args, "result": result})
    return result

  if intent == "study_mode":
    music_q = ctx.get("music_query", "lofi study music")
    _run("youtube_search_random_top3", {"query": music_q})
    observations.append("music attempted")
    _run("open_url", {"url": ctx.get("timer", "https://pomofocus.io")})
    observations.append("timer opened")
    _run("open_url", {"url": ctx.get("notes", "https://docs.google.com/document/create")})
    observations.append("notes opened")
    _run("open_url", {"url": ctx.get("checklist", "https://keep.google.com")})
    observations.append("checklist opened")
    set_preference("last_study_mode", datetime.now(timezone.utc).isoformat())

  elif intent == "search_google":
    query = ctx.get("search_query", state.get("transcript", ""))
    _run("google_search", {"query": query})
    observations.append(f"google search: {query}")

  elif intent == "search_youtube":
    query = ctx.get("search_query", state.get("transcript", ""))
    _run("youtube_search", {"query": query})
    observations.append(f"youtube search: {query}")

  elif intent == "recovery_music":
    set_preference("pending_music_recovery", True)
    state["pending_music_recovery"] = True
    observations.append("music recovery initiated — awaiting user preference")

  elif intent == "recovery_music_answer":
    desired = ctx.get("parsed_music") or state.get("transcript", "").strip()
    # Strip filler words
    desired = re.sub(
      r"^(i want|play|use|the|a)\s+",
      "",
      desired,
      flags=re.IGNORECASE,
    ).strip()
    if desired:
      query = f"{desired} study music"
      _run("youtube_search_random_top3", {"query": query})
      observations.append(f"music recovery: searched for {query}")
      set_preference("pending_music_genre", desired)
      state["retrieved_context"]["parsed_music"] = desired

  elif intent == "approve_music":
    genre = get_preference("pending_music_genre")
    if genre:
      _run("save_preference", {"key": "preferred_music", "value": genre})
      set_preference("pending_music_recovery", False)
      set_preference("pending_music_genre", None)
      observations.append(f"saved preferred_music={genre}")
    else:
      observations.append("approve skipped — no pending music genre")

  elif intent == "reject_music":
    set_preference("pending_music_recovery", True)
    observations.append("music still not right — ask again")

  elif intent == "speak":
    pass  # deprecated — user speaks via listen gesture

  state["tool_calls"] = tool_calls
  state["observations"] = observations
  return state


def observe_node(state: MIKUState) -> MIKUState:
  """Record observations from tool execution."""
  state = dict(state)
  if not state.get("observations"):
    state["observations"] = ["no tools executed"]
  return state


def recovery_node(state: MIKUState) -> MIKUState:
  """Handle failure or wrong-music feedback — RecoveryAgent logic."""
  state = dict(state)
  intent = state.get("intent", "")
  recovery = list(state.get("recovery_steps", []))

  if intent == "recovery_music":
    set_preference("pending_music_recovery", True)
    recovery.extend([
      "detected music complaint",
      "asking user for preferred genre",
    ])
    state["pending_music_recovery"] = True

  elif intent == "recovery_music_answer":
    genre = state.get("retrieved_context", {}).get("parsed_music", state.get("transcript"))
    recovery.extend([
      "detected music complaint",
      f"parsed desired genre: {genre}",
      f"searched YouTube for {genre} study music",
    ])

  elif intent == "approve_music":
    recovery.append("user approved music — preference saved")

  elif intent == "reject_music":
    recovery.append("user rejected music — will ask again")

  state["recovery_steps"] = recovery
  return state


def respond_node(state: MIKUState) -> MIKUState:
  """Generate final text response (rule-based or LLM)."""
  state = dict(state)
  intent = state.get("intent", "unknown")
  ctx = state.get("retrieved_context", {})
  text = state.get("transcript", "")

  # Rule-based responses (deterministic, no API key needed)
  responses: dict[str, str] = {
    "wake": "Good morning. MIKU is online and ready.",
    "sleep": "Going to sleep. Show an open hand when you need me.",
    "listen": "I'm listening.",
    "study_mode": (
      "Okay! Starting Study Mode. I'll open your music, timer, notes, and checklist."
    ),
    "search_google": f"I'll search that for you.",
    "search_youtube": (
      f"I'll look for {ctx.get('search_query', 'that')} on YouTube."
    ),
    "recovery_music": "What music do you want instead?",
    "recovery_music_answer": (
      f"Got it. I'll search YouTube for "
      f"{ctx.get('parsed_music', text)} study music and try one. Is this better?"
    ),
    "approve_music": (
      f"Great! I'll remember {get_preference('preferred_music')} for Study Mode."
      if get_preference("preferred_music")
      else "I don't have a music preference to save yet. Tell me what music you want first."
    ),
    "reject_music": "Sorry about that. What music would you like instead?",
    "chat": None,  # filled below
    "unknown": "I'm not sure what you mean. Try 'start study mode' or 'search up LangGraph tutorials'.",
  }

  resp = responses.get(intent)

  if intent == "chat" and resp is None:
    llm = _llm_chat(
      "You are MIKU, a friendly desktop assistant. Be brief and helpful.",
      text,
    )
    if llm:
      resp = llm
    elif _match_any(text, CHAT_GREETINGS):
      resp = "Hello! I'm MIKU, your desktop assistant. How can I help?"
    else:
      resp = (
        f"I heard: \"{text}\". I can start Study Mode, search Google/YouTube, "
        "or help with music preferences. What would you like?"
      )

  if intent == "search_google" and ctx.get("search_query"):
    resp = f"I'll search for {ctx['search_query']}."
  if intent == "search_youtube" and ctx.get("search_query"):
    resp = f"I'll look for {ctx['search_query']} on YouTube."

  # Preserve intent_node responses (e.g. safety blocks) when errors are set
  if state.get("errors") and state.get("response"):
    pass
  else:
    state["response"] = resp or state.get("response", "Done.")
  if intent == "sleep":
    state["miku_status"] = "asleep"
  elif intent == "wake":
    state["miku_status"] = "awake"
  else:
    state["miku_status"] = "awake"
  return state


def log_node(state: MIKUState) -> MIKUState:
  """Append full trace to logs.json."""
  state = dict(state)
  from backend.logger import append_trace

  append_trace(state)
  if state.get("intent") != "sleep":
    state["miku_status"] = state.get("miku_status", "awake")
  return state


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

SKIP_TOOLS = {"wake", "sleep", "listen", "chat", "unknown", "recovery_music"}


def route_after_plan(state: MIKUState) -> str:
  intent = state.get("intent", "unknown")
  if intent == "recovery_music_answer":
    return "tools"
  if intent in SKIP_TOOLS:
    return "recovery" if intent == "recovery_music" else "respond"
  return "tools"


def route_after_recovery(state: MIKUState) -> str:
  return "respond"


# ---------------------------------------------------------------------------
# Build LangGraph
# ---------------------------------------------------------------------------

def build_graph():
  """Construct and compile the MIKU LangGraph workflow."""
  graph = StateGraph(MIKUState)

  graph.add_node("input", input_node)
  graph.add_node("intent", intent_node)
  graph.add_node("retrieve_memory", retrieve_memory_node)
  graph.add_node("plan", plan_node)
  graph.add_node("tools", tool_node)
  graph.add_node("observe", observe_node)
  graph.add_node("recovery", recovery_node)
  graph.add_node("respond", respond_node)
  graph.add_node("log", log_node)

  graph.set_entry_point("input")
  graph.add_edge("input", "intent")
  graph.add_edge("intent", "retrieve_memory")
  graph.add_edge("retrieve_memory", "plan")
  graph.add_conditional_edges(
    "plan",
    route_after_plan,
    {"tools": "tools", "recovery": "recovery", "respond": "respond"},
  )
  graph.add_edge("tools", "observe")
  graph.add_edge("observe", "recovery")
  graph.add_edge("recovery", "respond")
  graph.add_edge("respond", "log")
  graph.add_edge("log", END)

  return graph.compile()


# Singleton compiled graph
_agent = None


def run_agent(
  raw_input: str = "",
  input_type: str = "text",
  gesture: str | None = None,
  transcript: str = "",
  should_speak: bool = False,
  active_mode: str | None = None,
) -> MIKUState:
  """Run the full MIKU agent pipeline and return final state."""
  global _agent
  if _agent is None:
    _agent = build_graph()

  ctx: dict = {}
  if active_mode:
    ctx["active_mode"] = active_mode
    set_preference("active_mode", active_mode)

  initial: MIKUState = {
    "raw_input": raw_input,
    "input_type": input_type,
    "gesture": gesture,
    "transcript": transcript or (raw_input if input_type in ("text", "voice") else ""),
    "should_speak": should_speak,
    "tool_calls": [],
    "observations": [],
    "recovery_steps": [],
    "errors": [],
    "retrieved_context": ctx,
    "plan": [],
  }
  return _agent.invoke(initial)
