# AI Development Playbook — Kowel Archive Explorer

How to execute the spec (v2 + Addenda A/B) using budget-tier models, session by session.

---

## 1. The operating model

```
YOU (orchestrator)                      MODELS (contractors)
─ slice spec into task briefs          ─ implement one brief per session
─ freeze interfaces early              ─ write & run tests for that brief
─ carry state between sessions         ─ stay inside the given contracts
─ accept/reject by RUNNING things      ─ flag (not fix) design problems
```

Three rules that prevent 90% of failures:

1. **One brief, one session, one module.** When the task is done and tests pass, end the session. Long sprawling sessions degrade — context fills with debugging noise and the model starts contradicting earlier decisions.
2. **Contracts are frozen.** Implementing sessions may not alter the schema, dataclasses, or CLI signatures. If a contract turns out wrong, that's a *design escalation* (see routing), and you update the contracts doc once, deliberately.
3. **Two strikes → escalate.** If a model fails the same task twice, a third retry usually fails too. Take the failing code + error to a stronger model for *diagnosis only*, then hand the prescribed fix back to the cheap model.

## 2. Model routing

| Work | Route to | Notes |
|---|---|---|
| Freeze contracts (schema, dataclasses, CLI signatures) | Top tier, one session | Highest-leverage spend of the project |
| Implementation: ingest, CLI, web UI, search, tests, exports | Sonnet in Claude Code | The ~90% workhorse |
| `geometry.py`, `verdict.py`, `coregister` math | Sonnet implements → top tier reviews diff | Subtle-failure modules: review the diff, not vibes |
| Debugging that crosses modules | Escalate diagnosis | Then fix downstream with Sonnet |
| Boilerplate, docstrings, README sections | Haiku / Sonnet | |
| Spec changes (any) | Top tier | Then update PROJECT_STATE + contracts |

Prefer **Claude Code** over chat for implementation: it reads/writes the repo and runs pytest itself, eliminating copy-paste loss — the dominant failure mode of chat-based coding. Keep `PROJECT_STATE.md` and `CONTRACTS.md` in the repo root; in Claude Code, a `CLAUDE.md` pointing at both gets loaded automatically every session.

## 3. PROJECT_STATE.md (template — keep under one page)

```markdown
# PROJECT_STATE — updated YYYY-MM-DD
## What this is
One-paragraph project summary. (Write once.)
## Status
Done: M0, M0.5, M1
In progress: M2 (embed_siglip.py works; embed_dino.py not started)
Next brief: T-07
## File tree (actual, not aspirational)
src/kowel_archive/{cli.py, db.py, ingest.py, ...}   tests/{...}
## Decisions log (newest first)
- 2026-06-20: thumbnails are JPEG q85, 512px long side
- 2026-06-18: GPKG layer names: buildings, camera_poses, map_annotations
## Conventions
Python 3.11, type hints everywhere, pytest, no new deps without approval,
RGB everywhere internally, paths via pathlib.
## Known issues / parked
- 1915 aerial fails coregister budget; registered manually, note in rasters table.
```

## 4. Task brief (template)

```markdown
# Brief T-NN: <module name>
## Goal
One sentence.
## Context you need (and nothing else)
<Paste ONLY the relevant spec section(s), e.g. v2 §4.1>
## Frozen contracts
<Paste the exact dataclasses / schema / CLI signature this must conform to>
You may not modify these. If one seems wrong, STOP and explain why instead.
## Definition of done
- [ ] `pytest tests/test_<module>.py` green (write the tests too)
- [ ] <specific behavior, e.g. "re-running ingest on same folder adds 0 rows">
- [ ] No new dependencies beyond: <list>
## Out of scope
<adjacent things it will be tempted to build — name them explicitly>
```

The **Out of scope** line matters more than it looks: models pattern-complete toward "helpful extras" (a config system, a logging framework, a second CLI). Naming the temptations suppresses them.

## 5. The session loop (your checklist, ~5 min overhead per session)

1. Start session → paste/point at `PROJECT_STATE.md` + the one brief.
2. Model implements + writes tests + runs them.
3. **You verify by running:** the brief's tests, plus the milestone behavior on a sample of *your real photos* (synthetic tests pass ≠ works on 1939 scans).
4. Commit with the brief ID in the message (`git` is non-negotiable — it's your undo button when a session goes sideways).
5. Update PROJECT_STATE (status, decisions, parked issues). End session.

## 6. The spec, pre-sliced into briefs (dependency order)

| ID | Brief | Spec source | Route |
|---|---|---|---|
| T-01 | **Contracts:** GPKG schema + `db.py` + all dataclasses + CLI signatures (stubs) | v2 §3, A1 | **Top tier** |
| T-02 | `io.py` + `preprocess.py` (loading, EXIF, thumbnails, CLAHE) | v2 §3.1, §4.1 | Sonnet |
| T-03 | `ingest.py` + `cli.py ingest` (hashing, dedupe, resumable) | v2 §4.1 | Sonnet |
| T-04 | Web app skeleton: FastAPI + grid browser + manual tags/collections | v2 §4.3 (M1 slice) | Sonnet |
| T-05 | `coregister` standalone script (tile→match→GCP→gdalwarp→report) | B3 | Sonnet, **top-tier review** |
| T-06 | `embed_siglip.py` + cache | v2 §4.2 | Sonnet |
| T-07 | `embed_dino.py` + cache | v2 §4.2 | Sonnet |
| T-08 | `search.py` + text-search & more-like-this & crop-to-search UI | v2 §4.3 | Sonnet |
| T-09 | `match/engine.py` + `geometry.py` + `verdict.py` | v1-spec §3.1 | Sonnet, **top-tier review** |
| T-10 | Review queue UI + tag confirmation flow | v2 §4.3 | Sonnet |
| T-11 | Linking flow: similarity → verify → observations → building assign | v2 §4.4 | Sonnet |
| T-12 | Temporal state grid UI + derived 1939 verdicts + nudge offsets | A3, B5 | Sonnet |
| T-13 | Camera-pose proposals + coverage views | A4, A2 | Sonnet |
| T-14 | `export.py` dossiers + full dump + `report coverage` | v2 §4.5 | Sonnet |

(M0 — QGIS work — is yours, no model needed. T-05 can run any time after T-01.)

## 7. Failure modes to expect (so they don't surprise you)

- **Silent contract drift:** the model "improves" a dataclass field name. Catch it in the diff; revert mercilessly. This is why contracts live in one file you can eyeball.
- **Test theater:** tests that mock so much they test nothing, or assert `result is not None`. Skim every new test once; demand at least one test with real fixture images per module.
- **Confident wrong dependencies:** hallucinated package names or APIs (especially around lightglue/kornia, which changed often). Rule: model must run `pip show <pkg>` / import checks before using anything new.
- **Scope creep via helpfulness:** see Out-of-scope note above.
- **The 90%-done illusion:** the last 10% (error handling, the GPKG lock convention, Windows paths) is where sessions stall. Budget specifically for a hardening brief per milestone if needed.

## 8. Budget intuition

Cost concentrates where context is large and iterations are many. You control both: small briefs (less context), frozen contracts + tests (fewer iterations). Expect the contracts session and the two reviews (T-05, T-09) to be your only premium spend; everything else should be cheap-tier. If a cheap session burns long on one bug — two strikes, escalate the diagnosis; that's cheaper than a third blind retry.
