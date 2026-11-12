# Adapter contract

Every platform core under `skills/<platform>/core/<package>/` must satisfy this
contract. The engine and UI depend only on these names — never on a specific
platform.

## 1. Purity rules

1. **One request per call.** Each public method performs at most one HTTP
   request. The only allowance is a cached WBI-key fetch plus a single internal
   key-refresh retry (signing mechanics, not a retry policy).
2. **No strategy in the core.** No `time.sleep`, no retry loops, no backoff, no
   file I/O, no logging configuration, no imports of `app.*` or Streamlit.
3. **Typed failures.** Raise errors carrying `kind: str` and `retryable: bool`
   (and `http_status`/`code` when known). The engine classifies via `getattr`,
   so platforms share no base class.
4. **JSON-safe resume state.** Cursors and resume markers are plain
   `str`/`int`/`dict`/`list` values.
5. **Standard model names.** Map raw payloads into the shared dataclasses; a
   field the platform cannot supply is simply absent from its catalog.

## 2. Module-level surface

```python
PLATFORM_ID: str
PLATFORM_NAME_EN: str
PLATFORM_NAME_ZH: str

def credential_fields() -> list[CredentialField]
def field_catalog(kind: str) -> list[FieldSpec]
def default_fields(kind: str) -> list[str]
def parse_input(raw: str) -> ParsedInput          # offline; no network
def create_adapter(credentials: dict[str, str], transport=None) -> Adapter
```

## 3. Adapter methods

| Method | Contract |
|---|---|
| `verify() -> AuthStatus` | Probe credentials; return `is_logged_in` and human-readable `warnings`. |
| `resolve_video(raw) -> VideoRef` | Resolve id/URL to metadata and one `VideoPart` per part (each with its playback id). |
| `comment_page(*, cursor, mode, page_size) -> CommentPage` | One page of root comments; include `next_cursor` and `is_end`. Pinned comments go in `pinned`. |
| `sub_reply_page(*, root_id, page, page_size) -> SubReplyPage` | One page of sub-replies. |
| `danmaku_targets(parts=None) -> list[DanmakuTarget]` | **Deterministic** full list of segments so progress totals and resume are exact. |
| `danmaku_segment(target) -> DanmakuSegment` | One segment; an empty `items` list means "no more data". |
| `item_id(item, kind) -> str` | Stable id used for dedup and resume. |
| `to_row(item, kind, fields) -> dict` | Flat projection in the requested column order. |
| `recover(exc) -> None` | Optional hook (e.g. drop cached signing keys on a stale-signature error). |

## 4. Adding a platform

1. Copy `skills/_template/` to `skills/<platform>/`.
2. Set `skill.toml` (`id`, `module`, names, `order`, `enabled = true`).
3. Implement the module-level functions and adapter methods.
4. Write `SKILL.md` and `references/` mirroring the Bilibili skill's section
   skeleton.
5. Nothing under `app/` changes: the registry discovers the manifest and the
   generic tab renders it.
