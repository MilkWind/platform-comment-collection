# Architecture

## Layers

```
┌───────────────────────────── app/ ─────────────────────────────┐
│  app/ui/          Streamlit, one generic tab per platform       │
│  app/engine/policy.py     rate gate, backoff, classification    │
│  app/engine/job.py        orchestration loops, events, cancel   │
│  app/engine/batch.py      plan -> resolve -> sequential batch    │
│  app/engine/output.py     JSONL / CSV / meta / zip              │
│  app/engine/checkpoint.py atomic resume state                   │
└───────────────▲─────────────────────────────────┬───────────────┘
                │ contract method names           │ Adapter + models
┌───────────────┴────────────── skills/ ──────────▼───────────────┐
│  skills/bilibili/SKILL.md + references/*.md  (abstract strategy) │
│  skills/bilibili/core/bilicrawl/             (copyable core API) │
│      adapter → comments / danmaku / view / wbi / http / input    │
└──────────────────────────────────────────────────────────────────┘
```

Data flows (single video): **input** → `parse_input` → **resolve** → `VideoRef` (aid + parts)
→ **comment cursor loop** (roots + sub-replies) → **danmaku segment loop** →
**writers** (JSONL → CSV + meta + zip).

## Batch layer

The UI accepts a list of links. `app/engine/batch.py` is a supervisor around the
single-video unit, not a second crawler:

```
plan_batch (offline)  ->  ResolveJob (1 resolve per item, preview table)
                      ->  BatchJob   ->  CrawlJob per item, sequentially
                                     ->  batch_manifest.json + batch-<ts>.zip
```

Because every item still runs a full `CrawlJob`, per-video output folders,
checkpoints, resume and dedup are unchanged. Batch only adds: one shared
adapter (verified once), a preset-scaled pause between videos, per-item error
policy (`not_found` continues, `auth_expired` aborts the rest), and the
aggregate manifest/zip. `docs/adapter-contract.md` is unchanged — batch uses
only the methods every adapter already has, so adding a platform still needs no
`app/` edits.

## Why strategy is not in the core

The core must be copyable into arbitrary projects, so it must stay small and
predictable. Sleeping, retrying, checkpointing, and deduplicating are policy
decisions that depend on context (how many videos, how impatient the user is).
Putting them in the core would force that policy on every consumer. Instead the
core exposes *one-request* primitives and the outer engine composes them using
the rules in `skills/<platform>/references/strategies.md`.

## Extensibility

- `app/ui/registry.py` discovers `skills/*/skill.toml`. Adding a manifest adds a
  tab; the tab renderer reads `credential_fields()` and `field_catalog()` so no
  UI code changes.
- The engine loops call only contract method names, so any platform that
  implements the adapter works with the same orchestration, checkpoints, and
  writers.

## Resume and dedup

`checkpoint.json` stores the comment cursor, completed sub-reply root ids, and
completed danmaku targets. JSONL sinks skip ids already written, so a killed run
resumes without duplicates. Cursors replay deterministically, so resume is exact.

## Failure isolation

WBI signing, error-code classification, and the protobuf schema each live in one
file. If any of them changes upstream, it is a one-file fix; the rest of the
stack (engine, UI, writers) is untouched.
