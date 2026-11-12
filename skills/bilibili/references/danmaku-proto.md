# Danmaku protobuf schema

The danmaku endpoint returns a protobuf `DmSegMobileReply`. The schema lives at
`core/bilicrawl/proto/dm_v1.proto`, copied from
[bilibili-API-collect](https://github.com/SocialSisterYi/bilibili-API-collect)
(`grpc_api/bilibili/community/service/dm/v1/dm.proto`).

## Fields used

`DmSegMobileReply.elems` (`DanmakuElem`):

| Proto field | Number | Meaning |
|---|---|---|
| `id` | 1 | numeric danmaku id |
| `progress` | 2 | appearance time (ms) |
| `mode` | 3 | 1–3 scroll, 4 bottom, 5 top, 6 reverse, 7 advanced |
| `fontsize` | 4 | font size |
| `color` | 5 | packed RGB |
| `midHash` | 6 | sender hash |
| `content` | 7 | text (UTF-8) |
| `ctime` | 8 | send time (unix seconds) |
| `weight` | 9 | 1–10 |
| `pool` | 11 | 0 normal, 1 subtitle, 2 special |
| `idStr` | 12 | id as string |
| `attr` | 13 | attribute bits |

## Segments

Each segment covers 360 seconds. Fetch `segment_index` 1, 2, 3, … until a
response has an empty body or zero `elems` (the video has ended). Total segments
= `ceil(part_duration_sec / 360)`.

## Regenerating the bindings

The generated `dm_v1_pb2.py` is checked in. Regenerate only with the pinned
toolchain (generated-by-newer-than-runtime fails at import):

```bash
uv sync                    # installs protobuf>=7.35,<8 and grpcio-tools
uv run python scripts/gen_proto.py
```

If a project cannot depend on `protobuf` 7.x, the wire format only needs varint
and length-delimited reading, so a small stdlib decoder can replace the
generated module.
