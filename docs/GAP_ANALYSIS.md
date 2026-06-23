# Gap Analysis — M.I.K.U. (post-fix)

| Requirement | Satisfied? | Evidence | Weakness | Priority |
|-------------|------------|----------|----------|----------|
| Tool calling | Yes | `tools.py`, eval Test 1 | `start_study_mode` tool unused by graph | Low |
| ReAct | Partial | plan→tools→observe | Single pass only | Medium |
| Memory | Yes | eval Test 4b, `memory.json` | No vector RAG | Low |
| ToT | Yes | `_score_study_candidate` in `graph.py` | Study Mode only | Low |
| Multi-agent | Partial | Named nodes | Not separate agents | Medium |
| Safety | Yes | eval Test 5, `safety.py` | Keyword-only blocking | Low |
| Observability | Yes | `logs.json`, dashboard | Large noisy logs | Low |
| README accuracy | Yes | Updated gesture/ToT sections | — | Done |
| Formal report | Partial | `docs/` deliverables | User must customize narrative | Medium |

**Submission readiness:** Runnable MVP with eval script; suitable for capstone with honest framing of multi-agent as role-based nodes.
