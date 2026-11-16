# Video Comment & Danmaku Collector (platform-comment-collection)

**English** · [简体中文](README.md)

A **mini but useful**, plug-in-style tool to collect video **comments** and **danmaku (弹幕)**. Bilibili first; Douyin and others can be added later.

## Three ways to use it

One project, one source of truth, three consumption modes:

1. **Built-in UI (beginner-friendly)** — a local web app: pick a platform → paste **one or more** video links (one per line) → (optionally) grab a cookie with one click → choose fields → resolve video info → tick the rows to collect → start → watch progress and logs → download results (a single link is just a batch of one).
2. **Skill (for AI agents)** — `skills/bilibili/` is a self-contained skill directory; an agent loads `SKILL.md` and follows the workflow.
3. **Copy the core** — drop `skills/bilibili/core/bilicrawl/` into your own project and call the core APIs. It depends only on the standard library + `requests` + `protobuf`.

The structure follows `{[(core py files) wrapped in a skill] additional UI}`; with multiple platforms it becomes `{[(per-platform cores) per-platform skills] unified tabbed UI}`.

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Python ≥ 3.12.

```bash
uv sync

# 1) Built-in web UI
uv run streamlit run app/streamlit_app.py

# 2) Headless run (several inputs, or --file with one per line)
uv run python examples/run_engine_headless.py BV1GJ411x7h7 BV1xxxxxxxxx --max-roots 40
uv run python examples/run_engine_headless.py --file videos.txt

# 3) Core-only example
uv run python skills/bilibili/examples/quickstart.py BV1GJ411x7h7
```

## Design highlights

- **Core only speaks API**: each core call makes at most one HTTP request — no sleeping, retrying, or file I/O. See [`docs/adapter-contract.md`](docs/adapter-contract.md).
- **Strategy lives outside**: rate limiting, backoff, checkpoint/resume, dedup, and multi-P handling are documented in `skills/bilibili/references/strategies.md` and implemented by `app/engine/`.
- **Uniform and extensible**: a new platform is just `skills/<platform>/` (copy `skills/_template/`); its UI tab appears automatically with no edits under `app/`.
- **Auth is optional**: anonymous access collects comments and danmaku; logging in unlocks IP location and fuller sub-replies.

## About the cookie (optional)

On a logged-in `bilibili.com` page, open DevTools console and run the snippet in `skills/bilibili/scripts/sessdata_snippet.js` to copy `SESSDATA`. If `SESSDATA` is HttpOnly, copy any `api.bilibili.com` request as cURL from the Network panel and paste it into the app. `bili_jct` is **not** needed — all calls are read-only.

## Layout

```
app/        Outer layer: engine (strategy implementation) + Streamlit UI
skills/     Skills: one directory per platform
  bilibili/   SKILL.md + references/ + core/bilicrawl/ (copyable core)
  _template/  Scaffold for a new platform
docs/       Adapter contract and architecture notes
scripts/    Protobuf generation, live smoke test
tests/      Offline unit tests (fixtures, no network)
```

## Output

```
output/bilibili/<bvid>/
├── comments.csv / comments.jsonl
├── danmaku.csv  / danmaku.jsonl
├── meta.json
└── checkpoint.json
output/bilibili/batch-<timestamp>.json   # per-item status/counts/out dir
output/bilibili/batch-<timestamp>.zip    # every collected video of the run
```

Batches run sequentially — one video at a time with a preset-scaled pause between videos — and videos already marked complete in `checkpoint.json` are skipped by default.

CSV files use `utf-8-sig` so Excel displays Chinese correctly.

## Testing

```bash
uv run pytest -q                                   # offline unit tests
uv run python scripts/live_smoke.py --bvid BV1GJ411x7h7   # live smoke test (manual)
```

## License

MIT, see [LICENSE](LICENSE).
