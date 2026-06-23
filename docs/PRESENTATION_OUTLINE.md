# Presentation Outline (~10 min) — M.I.K.U.

## 1. Opening (1 min)

**Slide:** M.I.K.U. — Traceable Desktop Assistant

- Gesture + voice control
- LangGraph + LangChain tools
- CMU Agentic AI capstone MVP

**Demo:** Dashboard at `http://127.0.0.1:8000`

## 2. Why This Matters (1 min)

- Fragmented study workflows
- Need safe, observable agents
- Hands-free control for focus sessions

## 3. Architecture (2 min)

**Diagram:** LangGraph node pipeline (README)

- 9 nodes, shared `MIKUState`
- Traces in `logs.json`

**Speaker note:** Walk one Study Mode trace: intent → plan (ToT) → tools → observations.

## 4. Key Design Decisions (2 min)

- Gestures set **mode**, then **listen** (no searching gesture names)
- ToT: 3 Study Mode candidates, scored in code
- Safety whitelist before any browser open
- Rule-based default; optional OpenAI

## 5. Evaluation (2 min)

**Run live or show:** `python scripts/run_eval.py`

- Study mode, search, recovery, jazz save, unsafe block

## 6. Repository (1 min)

- `backend/graph.py` — agent
- `backend/tools.py` — tools
- `docs/` — CMU mapping, gap analysis

## 7. Closing (1 min)

- Strengths: traceable, runnable, safe browser tools
- Honest limits: role-based nodes, not full multi-agent
- Next: CI, local LLM, richer memory
