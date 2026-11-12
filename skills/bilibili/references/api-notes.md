# Bilibili API notes

Verified against live responses on 2026-11-12.

## Endpoints

| Purpose | Endpoint | Auth | Notes |
|---|---|---|---|
| Video meta + cid | `GET /x/web-interface/view?bvid=` (or `?aid=`) | none | `data.aid`, `data.cid`, `data.pages[].cid` |
| Root comments | `GET /x/v2/reply/wbi/main` | WBI | cursor API; works logged-out |
| Sub-replies | `GET /x/v2/reply/reply?root=` | none | page-number; `ps=20` |
| Danmaku | `GET /x/v2/dm/web/seg.so` | none | protobuf; 360s segments |
| WBI keys / login | `GET /x/web-interface/nav` | none | `wbi_img`; `isLogin`; `-101` when anonymous |

All under `https://api.bilibili.com`. Send `Referer: https://www.bilibili.com`
and a browser `User-Agent`.

## Comment cursor API

Params: `oid=<aid>`, `type=1`, `mode=2|3` (2 time, 3 hot), `plat=1`,
`seek_rpid=`, `web_location=1315875`, `ps=20|30`,
`pagination_str={"offset":"..."}` (a **pre-serialized JSON string**), plus WBI
`wts`/`w_rid`.

Response: `data.cursor.pagination_reply.next_offset`, `data.cursor.is_end`,
`data.cursor.all_count`; records in `data.replies`, pinned in
`data.top_replies`. Each record uses `mid`, `rpid`, `root`, `parent`, `rcount`,
`like`, `ctime`, `content.message`, `member.uname`,
`member.level_info.current`, and `reply_control.location` (login-only).

## Danmaku

`GET /x/v2/dm/web/seg.so?type=1&oid=<cid>&pid=<aid>&segment_index=N`.

> **Footgun:** comment `oid` = **aid**; danmaku `oid` = **cid** and `pid` = aid.

Each segment covers 360 seconds. An empty body or zero elems means the video has
ended. The WBI-signed variant `/x/v2/dm/wbi/web/seg.so` exists for logged-in
sessions.

## WBI signing

1. Fetch `nav`; take the basenames of `wbi_img.img_url` and `sub_url`.
2. Mixin key = first 32 chars of `(img_key + sub_key)` permuted by a fixed
   64-entry table.
3. Add `wts = unix seconds`; strip `!'()*` from values; sort keys; urlencode;
   `w_rid = md5(query + mixin_key)`.
4. Send the exact signed query string.

## Error codes

| Code | Meaning | Class |
|---|---|---|
| HTTP 412 | risk control | `risk_control` (back off) |
| -412 | stale WBI signature | `wbi_stale` (refresh keys) |
| -352 / -509 / -799 | rate limiting | `transient` |
| -101 | not logged in / cookie expired | `auth_expired` |
| -400 | offset exhausted | end of data |

## Deprecated

The legacy `/x/v2/reply?pn=` page API is **not used**: it returns 3 or 0 items
when anonymous and is hard-capped near offset 5000.
