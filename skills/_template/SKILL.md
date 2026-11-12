---
name: example-platform-crawl
description: Template skill for adding a new video platform to this project. Shows the required files and the unified section skeleton every platform skill follows.
---

# Example Platform Crawl (template)

This directory is **not loaded** by the app (`skill.toml` has
`enabled = false` and the `_` prefix is skipped). It is a scaffold: copy it to
`skills/<your_platform>/`, fill in the pieces, and it becomes a working
platform tab.

## Required files

- `skill.toml` — `[platform]` with `id`, `module`, `name_en`, `name_zh`,
  `order`, `enabled = true`.
- `SKILL.md` — this file; keep the same section skeleton as the Bilibili skill.
- `references/strategies.md` — platform-specific notes for the shared strategy
  doc (endpoints per request kind, extra error codes, multi-part rules).
- `core/<package>/` — the copyable core implementing `docs/adapter-contract.md`.

## Section skeleton (mirror the Bilibili skill)

1. Trigger conditions
2. Prerequisites
3. Step 1 — obtain credentials (with a console snippet and a cURL fallback)
4. Step 2 — parse input
5. Step 3 — resolve the video / item
6. Step 4 — collect comments
7. Step 5 — collect danmaku (if the platform has it)
8. Step 6 — project and store
9. Error handling table
10. Copy-into-your-project + a worked example

## Guideline

Keep the core pure: one request per call, no sleeping or retrying. Put all
policy in `references/strategies.md` so the outer engine can implement it. The
UI tab appears automatically once `enabled = true`.
