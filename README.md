# M.I.K.U. Desktop Assistant

**M.I.K.U.** = **M**achine **I**ntelligence for **K**nowledge & **U**ser-assistance

A simple "Siri for my computer" MVP built for the CMU Agentic AI capstone. MIKU is controlled by **hand gestures** and **voice**, powered by a **LangGraph** agent workflow with **LangChain tools**, full **trace logging**, and **safety guardrails**.


---

## Quick Start

### 1. Install

```bash
cd miku-desktop-assistant
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

> **Note:** `pyaudio` may need system deps. On macOS: `brew install portaudio`

### 2. Run Backend

```bash
# From miku-desktop-assistant/
python -m backend.main
```

Server starts at **http://127.0.0.1:8000**

### Mic & Camera

- **Listen** uses your **browser microphone** (Chrome Web Speech API) — no server mic required
- **Webcam** runs **MediaPipe Hands in the browser** with a live skeleton overlay (low latency)
- Grant camera + mic permissions when prompted


## Demo Walkthrough

1. Open the dashboard.
2. Click **Wake** (or show open hand to webcam).
3. Click **Listen** (or do a closed pinch gesture).
4. Say or type: **"start study mode"**
5. MIKU opens music, timer, notes, and checklist tabs.
6. Trace appears in the dashboard.
7. Say or type: **"the music is wrong"**
8. MIKU asks what music you want.
9. Say or type: **"jazz"**
10. MIKU searches YouTube for jazz study music.
11. Click **Thumbs Up** — MIKU saves jazz as your preference.
12. Next Study Mode uses jazz automatically.

---

## Gesture Mapping

| Gesture | Action |
|---------|--------|
| ✋ Open hand | **Wake** MIKU |
| ✊ Closed fist | **Sleep** MIKU |
| 🤏 Closed pinch | **Listen** — speak your command |
| ☝️ 1 finger | **Study mode** — listen, then run Study Mode from speech |
| ✌️ 2 fingers | **Search mode** — listen, then Google search your query |
| 🤟 3 fingers | **Chat mode** — listen, then conversational reply |

Dashboard buttons mirror every gesture. Mode gestures **wait for your voice** — they do not search gesture names.

---

## Voice (TTS)

MIKU uses **edge-tts** with `en-GB-RyanNeural` (Jarvis-style British voice). Fallback: `pyttsx3`.

---

## Tool List

| Tool | Description |
|------|-------------|
| `open_url(url)` | Opens a whitelisted URL in the browser |
| `google_search(query)` | Opens Google search for query |
| `youtube_search(query)` | Opens YouTube search for query |
| `youtube_search_random_top3(query)` | Opens one of top 3 YouTube results (scrape or fallback) |
| `start_study_mode()` | Opens music, timer, notes, checklist |
| `save_preference(key, value)` | Updates `memory.json` |
| `log_event(event)` | Appends to `logs.json` |
| `speak_text(text)` | Speaks via pyttsx3 / edge-tts |

---

## Safety Guardrails

All browser actions pass through `backend/safety.py`:

**Allowed URL patterns:**
- `https://www.google.com/search?q=`
- `https://www.youtube.com/results?search_query=`
- `https://www.youtube.com/watch`
- `https://pomofocus.io`
- `https://www.online-stopwatch.com`
- URLs in `config.json` and `study_mode_kb.json`

**Blocked:**
- Shell commands, file deletion, email, payments
- System admin actions, arbitrary downloads
- Opening unknown local files

If MIKU is unsure, it asks the user instead of acting.

---

## LangGraph Architecture

```
input → intent → retrieve_memory → plan → [tools] → observe → recovery → respond → log → END
                                              ↘ recovery ↗ (music complaints)
                                              ↘ respond  ↗ (chat/wake/listen)
```

### Nodes

| Node | Purpose |
|------|---------|
| `input_node` | Receives gesture/text/voice input |
| `intent_node` | Maps input to intent (wake, listen, study_mode, etc.) |
| `retrieve_memory_node` | Loads Study Mode KB + user preferences |
| `plan_node` | Creates a simple action plan |
| `tool_node` | Executes LangChain `@tool` functions |
| `observe_node` | Records tool results |
| `recovery_node` | Handles wrong-music feedback |
| `respond_node` | Generates final chatbot response |
| `log_node` | Appends full trace to `logs.json` |

### State Fields

`raw_input`, `input_type`, `gesture`, `transcript`, `intent`, `retrieved_context`, `plan`, `tool_calls`, `observations`, `recovery_steps`, `response`, `errors`, `timestamp`

---

## CMU Module Mapping

| CMU Concept | MIKU Implementation |
|-------------|---------------------|
| **Tool calling** | LangChain `@tool` functions in `tools.py`, invoked by `tool_node` |
| **ReAct** | Plan → Act (tools) → Observe loop in LangGraph |
| **RAG / Memory** | `retrieve_memory_node` reads `study_mode_kb.json` + `memory.json` |
| **ToT / Planning** | `plan_node` scores Study Mode candidate plans A/B/C and selects highest score |
| **Multi-agent coordination** | Specialized LangGraph nodes (planner, memory, tools, recovery) in one workflow — role-based, not separate LLM agents |
| **Safety / Human intervention** | `safety.py` whitelist; MIKU asks before uncertain actions |
| **Observability** | Full trace logged to `logs.json` and displayed on dashboard |

---

## Tree-of-Thought / Candidate Planning

`plan_node` in `backend/graph.py` generates **three Study Mode candidates**, scores them, and selects the winner before tool execution.

| Candidate | Music | Timer | Score factors |
|-----------|-------|-------|---------------|
| Plan A | KB default (lofi) | Pomofocus | Baseline |
| Plan B | Backup (bossa nova) | Online stopwatch | Backup path |
| Plan C | `preferred_music` if saved | Pomofocus | User preference boost |

Scoring weights (implemented in `_score_study_candidate`):
- Retrieval relevance: 30%
- Tool availability (HTTPS URLs): 30%
- User preference match: 25%
- Recovery readiness: 15%

The selected plan id and all candidate scores appear in `retrieved_context.candidate_plans` in each trace.

---

## Example Trace

This trace proves agentic behavior: intent classification → memory retrieval → planning → tool execution → observation → response → logging.

```json
{
  "timestamp": "2026-06-22T12:00:00+00:00",
  "raw_input": "start study mode",
  "input_type": "voice",
  "gesture": null,
  "transcript": "start study mode",
  "intent": "study_mode",
  "retrieved_context": {
    "preferred_music": null,
    "preferred_timer": "pomofocus",
    "pending_music_recovery": false,
    "music_query": "lofi study music",
    "backup_music_query": "bossa nova study music",
    "timer": "https://pomofocus.io",
    "backup_timer": "https://www.online-stopwatch.com",
    "notes": "https://docs.google.com/document/create",
    "checklist": "https://keep.google.com"
  },
  "plan": [
    "search YouTube for lofi study music",
    "open timer at https://pomofocus.io",
    "open notes at https://docs.google.com/document/create",
    "open checklist at https://keep.google.com"
  ],
  "tool_calls": [
    {
      "tool": "youtube_search_random_top3",
      "args": {"query": "lofi study music"},
      "result": "opened https://www.youtube.com/results?search_query=lofi+study+music (fallback: top-3 selection simulated — picked result #2)"
    },
    {
      "tool": "open_url",
      "args": {"url": "https://pomofocus.io"},
      "result": "opened https://pomofocus.io"
    },
    {
      "tool": "open_url",
      "args": {"url": "https://docs.google.com/document/create"},
      "result": "opened https://docs.google.com/document/create"
    },
    {
      "tool": "open_url",
      "args": {"url": "https://keep.google.com"},
      "result": "opened https://keep.google.com"
    }
  ],
  "observations": [
    "music attempted",
    "timer opened",
    "notes opened",
    "checklist opened"
  ],
  "recovery_steps": [],
  "response": "Okay! Starting Study Mode. I'll open your music, timer, notes, and checklist.",
  "errors": []
}
```

### How This Trace Proves Agentic Behavior

1. **Perception** — `input_node` receives "start study mode" as voice input.
2. **Reasoning** — `intent_node` classifies intent as `study_mode`; `plan_node` decomposes into 4 steps.
3. **Memory** — `retrieve_memory_node` pulls KB defaults and checks `preferred_music` (null → uses lofi).
4. **Action** — `tool_node` calls 4 LangChain tools with safety-checked URLs.
5. **Observation** — `observe_node` records what succeeded.
6. **Response** — `respond_node` generates a friendly confirmation.
7. **Observability** — `log_node` persists the full trace for audit.

---

## Project Structure

```
miku-desktop-assistant/
├── backend/
│   ├── main.py        # FastAPI server
│   ├── graph.py       # LangGraph workflow
│   ├── state.py       # Agent state schema
│   ├── tools.py       # LangChain tools
│   ├── gestures.py    # MediaPipe hand detection
│   ├── voice.py       # Speech recognition
│   ├── tts.py         # Text-to-speech
│   ├── memory.py      # memory.json persistence
│   ├── logger.py      # Trace logging
│   └── safety.py      # URL whitelist
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
├── data/
│   ├── config.json
│   ├── memory.json
│   ├── logs.json
│   ├── study_mode_kb.json
│   └── sample_trace.md
├── README.md
└── requirements.txt
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Dashboard |
| GET | `/api/status` | MIKU status |
| POST | `/api/command` | Text/button command |
| POST | `/api/listen` | Voice capture + agent |
| POST | `/api/gesture` | Gesture trigger |
| POST | `/api/gestures/start` | Start webcam |
| POST | `/api/gestures/stop` | Stop webcam |
| GET | `/api/traces` | Recent traces |
| GET | `/api/memory` | User preferences |
| POST | `/api/speak` | TTS |

---

## License

CMU Agentic AI Capstone — educational MVP.

## Capstone Documentation

- [CMU Requirements Mapping](docs/CMU_REQUIREMENTS_MAPPING.md)
- [Final Report](docs/FINAL_REPORT.md)
- [Evaluation Results](docs/EVALUATION_RESULTS.md)
- [Gap Analysis](docs/GAP_ANALYSIS.md)
- [Presentation Outline](docs/PRESENTATION_OUTLINE.md)

Run evaluation: `python scripts/run_eval.py`
