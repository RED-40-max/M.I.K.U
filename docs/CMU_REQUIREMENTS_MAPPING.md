# CMU Requirements Mapping — M.I.K.U. Desktop Assistant

Evidence-based mapping. Run `python scripts/run_eval.py` to reproduce tests.

## Tool Calling — **Satisfied (High)**

| Evidence | Location |
|----------|----------|
| 8 LangChain `@tool` functions | `backend/tools.py` |
| `tool_node` invokes tools, records `tool_calls` | `backend/graph.py` |
| Observations logged | `observe_node`, `logger.py` |
| Trace example | `data/logs.json`, README example trace |

## ReAct / Reasoning — **Partial (Medium-High)**

Pipeline: `input → intent → retrieve_memory → plan → tools → observe → recovery → respond → log`

Recovery from wrong music: `recovery_node` + `pending_music_recovery` flag.

**Limitation:** Single-pass graph, not iterative ReAct.

## Memory / RAG — **Satisfied (Medium-High)**

| Source | Role |
|--------|------|
| `data/memory.json` | User preferences (`preferred_music`) |
| `data/study_mode_kb.json` | Study Mode defaults |
| `retrieve_memory_node` | Merges KB + memory into `retrieved_context` |

**Verified:** Eval Test 4 saves `preferred_music: jazz`.

## Tree of Thought — **Satisfied (Medium)**

Implemented in `plan_node`: `_build_study_candidates`, `_score_study_candidate`, winner in `retrieved_context.candidate_plans`.

## Multi-Agent — **Partial (Low-Medium)**

Specialized **nodes** (planner, memory, tools, recovery) in **one** LangGraph — role-based decomposition, not separate LLM agents.

## Safety — **Satisfied (Medium-High)**

| Control | Location |
|---------|----------|
| URL whitelist | `backend/safety.py` |
| Input keyword block | `is_input_safe`, `intent_node` |
| Human approval | thumbs up/down, music prompts |

**Verified:** Eval Test 5 blocks `sudo rm -rf`.

## Observability — **Satisfied (High)**

Full traces in `data/logs.json` + dashboard trace panel.
