# Fields and output schema

Field names are the cross-platform standard. A platform that cannot supply a
field simply omits it from its catalog.

## Comments

| Key | Meaning | Default | Needs login |
|---|---|---|---|
| `id` | Comment id (rpid) | ✓ | |
| `root_id` | Root comment id (0 for roots) | ✓ | |
| `parent_id` | Parent comment id | ✓ | |
| `user_id` | User id | ✓ | |
| `user_name` | Display name | ✓ | |
| `content` | Text | ✓ | |
| `like_count` | Likes | ✓ | |
| `reply_count` | Sub-reply count | ✓ | |
| `created_at` | Unix seconds | ✓ | |
| `created_at_iso` | UTC ISO-8601 | ✓ | |
| `location` | IP 属地 | | ✓ |
| `sex` | Gender | | |
| `level` | User level | | |
| `pictures` | Image URLs (`;`-joined) | | |
| `is_pinned` | Pinned by uploader | | |

## Danmaku

| Key | Meaning | Default |
|---|---|---|
| `id` | Danmaku id (dmid) | ✓ |
| `part_index` | Part number | ✓ |
| `progress_ms` | Appearance time in ms | ✓ |
| `content` | Text | ✓ |
| `mode` | 1–3 scroll, 4 bottom, 5 top, … | |
| `fontsize` | Font size | |
| `color` | `#RRGGBB` | |
| `sent_at` | Unix seconds | |
| `sent_at_iso` | UTC ISO-8601 | |
| `pool` | 0 normal, 1 subtitle, 2 special | |
| `weight` | 1–10 | |
| `attr` | Attribute bit field | |
| `user_hash` | Sender hash | |

## Output files

```
output/<platform>/<video_id>/
├── comments.jsonl   # canonical, one row per record, crash-safe append
├── comments.csv     # convenience export (utf-8-sig)
├── danmaku.jsonl
├── danmaku.csv
├── meta.json        # counts, coverage, field selection (no credentials)
├── checkpoint.json  # resume state
└── <video_id>.zip   # download bundle (one level up)
```
