# Strategies (platform-neutral)

These are the abstract strategies the outer layer implements. The core never
sleeps, retries, or writes files; everything below belongs to the caller.

## 1. Rate limiting

- Pace every request kind with a randomized interval (jitter prevents
  synchronized bursts):
  | Kind            | Safe     | Balanced  | Fast     |
  |-----------------|----------|-----------|----------|
  | comment page    | 1.6–3.2s | 0.8–1.6s  | 0.36–0.72s |
  | sub-reply page  | 0.5–1.2s | 0.25–0.6s | 0.11–0.27s |
  | danmaku segment | 0.3–0.9s | 0.15–0.45s| 0.07–0.2s  |
- Keep one request in flight per job (v1 is single-threaded per job). If you
  raise concurrency, add a global semaphore and raise delays.
- Never sleep inside the core.

## 2. Retry and error classification

- Classify by the error's `kind`/`retryable` attributes (duck-typed).
- Retry `risk_control` after a long pause (~12s). Retry `wbi_stale` after
  calling `recover()`. Retry `transient` with exponential backoff
  (base × 2^n, capped) plus jitter. Never retry `auth_expired`, `not_found`,
  or `protocol`.
- Treat unknown exceptions as fatal after one attempt: fail loudly with the URL
  and code rather than looping forever.

## 3. Checkpoint and resume

- Save atomically (`tmp` file + `os.replace`). Store the opaque cursor for root
  comments, the set of completed sub-reply root ids, and the set of completed
  `(part_index, segment_index)` danmaku targets.
- Resume only when platform, input, and selected fields match the saved run.
  `next_offset` cursors replay deterministically, so resuming is exact.
- Never store credentials in checkpoints or metadata.

## 4. Deduplication

- Key every record by `adapter.item_id(item, kind)` (rpid for comments, dmid for
  danmaku). Pinned comments can repeat across pages; skip ids already written.
- Output is append-only JSONL, so a killed run resumes without duplicates.

## 5. Multi-P videos

- Comments are collected **once per video** (aid).
- Danmaku is collected **per part** (cid). Compute targets as
  `ceil(duration_sec / 360)` segments per selected part so progress totals and
  resume are exact.
- Part selection is a collection toggle, not an output field.

## 6. Field selection

- Two independent concerns: *what to fetch* (scope: comments / sub-replies /
  danmaku) and *what to write* (output columns from `field_catalog`).
- Fields marked `requires_auth` (IP location) are empty in anonymous mode; tell
  the user rather than silently omitting the column.

## 7. Completeness accounting

- Write `meta.json` with collected counts and the platform-reported total
  (`all_count` includes sub-replies) so coverage is auditable.
- If a sub-reply request fails, keep the inline preview replies and mark the
  run partial instead of claiming completeness.

## 8. Large videos

- A video with 200k+ comments is a multi-hour job at Balanced pacing. Keep
  checkpoints mandatory, show progress and ETA, and let the user cap roots.

## 9. Cancellation

- Check a cancel event before every request. Make backoff sleeps interruptible
  (wait on the event, not `time.sleep`). On cancel, flush sinks, save a
  checkpoint, and report `cancelled` so the run can resume later.
