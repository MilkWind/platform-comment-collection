---
name: bilibili-comment-danmaku
description: Collect Bilibili (B站) video comments (with sub-replies) and danmaku (弹幕) given a BV id or video URL. Use when a user asks to scrape, download, archive, or analyze Bilibili comments/danmaku, or references a bilibili.com / b23.tv video link.
---

# Bilibili Comment & Danmaku Collection

This skill wraps the copyable core package `core/bilicrawl/`. The core exposes
**main APIs only** (one request per call). The *strategies* — pacing, retries,
checkpointing, deduplication, multi-P handling — are documented in
[`references/strategies.md`](references/strategies.md) and are implemented by
the caller (the bundled app's engine, or you).

## Prerequisites

- Python ≥ 3.12
- `pip install -r requirements.txt` (only `requests` and `protobuf`)
- A cookie is **optional**. Anonymous access works for comments and danmaku.
  Logging in unlocks `location` (IP 属地) and fuller results.

## Trigger conditions

- User mentions B站 / Bilibili / 哔哩哔哩 comments, replies (评论), danmaku (弹幕).
- User provides a `BV...` id or a `bilibili.com/video/...` / `b23.tv/...` link.

## Workflow

### Step 1 — Obtain a cookie (optional)

Show the user the console snippet in
[`scripts/sessdata_snippet.js`](scripts/sessdata_snippet.js). `SESSDATA` may be
HttpOnly; if the snippet fails, tell the user to copy a request as cURL from
DevTools → Network → any `api.bilibili.com` request and paste it. The
credential normalizer accepts a full cookie header, `SESSDATA=...`, a bare
value, **or** a cURL command. `bili_jct` is not needed — all calls are read-only.

### Step 2 — Parse the input

```python
import bilicrawl

bilicrawl.parse_input("https://www.bilibili.com/video/BV1GJ411x7h7/?p=2")
# ParsedInput(kind="url", video_id="BV1GJ411x7h7", page_hint=2)
```

Accepted: BV id, av id, full URL, `?p=N`, and `b23.tv` short links.

### Step 3 — Resolve the video

```python
adapter = bilicrawl.create_adapter({"cookie": "<cookie or empty>"})
auth = adapter.verify()  # tells you whether IP location is available
video = adapter.resolve_video("BV1GJ411x7h7")
# video.aid, video.title, video.parts -> each part has a cid
```

Comments are **video-scoped** (one set per video). Danmaku is **part-scoped**.
Never pass a raw cid to a comment call or a raw aid to a danmaku call.

### Step 4 — Collect comments

Apply the pacing rules from `references/strategies.md`:

```python
cursor = None
while True:
    page = adapter.comment_page(cursor=cursor, mode=3)  # mode 2=time, 3=hot
    for c in page.roots:
        ...  # store c.to_row(...) or dataclasses.asdict(c)
        if c.reply_count > 0:
            sub = adapter.sub_reply_page(root_id=c.id, page=1)
            ...
    if page.is_end or not page.next_cursor:
        break
    cursor = page.next_cursor
    # sleep 0.8-1.6s (Balanced) here — the core never sleeps
```

Pinned comments arrive in `page.pinned`. Inline `page.previews[root_id]` is a
fallback if a sub-reply request fails.

### Step 5 — Collect danmaku

```python
for target in adapter.danmaku_targets():  # (part_index, cid, segment_index)
    seg = adapter.danmaku_segment(target)  # empty items => end of video
    for d in seg.items:
        ...
    # sleep 0.15-0.45s here
```

### Step 6 — Project and store

`adapter.to_row(item, kind, fields)` produces a flat dict with a stable column
order. `bilicrawl.default_fields(kind)` returns the default selection. Write
JSONL (crash-safe canonical) and/or CSV (use `utf-8-sig` so Excel shows Chinese
correctly).

## Error handling

| `kind`          | Meaning                        | Action                          |
|-----------------|--------------------------------|---------------------------------|
| `risk_control`  | HTTP 412 risk control          | Back off ~12s, retry, slow down |
| `wbi_stale`     | JSON -412 stale signature      | Call `adapter.recover(exc)` then retry |
| `transient`     | -352 / -509 / -799, HTTP 429/5xx | Backoff and retry             |
| `auth_expired`  | JSON -101 cookie expired       | Ask the user to re-auth         |
| `not_found`     | Video/comment unavailable      | Stop; report                    |
| `protocol`      | Unexpected response            | Stop; log `code` + URL          |

## Copy into your own project

Copy **only** `core/bilicrawl/`. It imports nothing outside the standard
library, `requests`, and `protobuf`. See
[`examples/comments_to_jsonl.py`](examples/comments_to_jsonl.py) for a minimal
paging loop that uses core primitives alone (no engine, no UI).

## Worked example

```bash
uv run python skills/bilibili/examples/quickstart.py BV1GJ411x7h7
```

Expected: the video title, its part count, the first page of comments, and the
first danmaku segment's item count.
