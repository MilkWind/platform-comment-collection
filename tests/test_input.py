from __future__ import annotations

import pytest
from bilicrawl.credentials import normalize
from bilicrawl.input import parse_input


@pytest.mark.parametrize(
    "raw,kind,vid",
    [
        ("BV1GJ411x7h7", "bvid", "BV1GJ411x7h7"),
        ("https://www.bilibili.com/video/BV1GJ411x7h7", "url", "BV1GJ411x7h7"),
        ("https://www.bilibili.com/video/BV1GJ411x7h7/?p=3", "url", "BV1GJ411x7h7"),
        ("av170001", "avid", None),
        ("https://www.bilibili.com/video/av170001", "url", None),
    ],
)
def test_parse_input_forms(raw, kind, vid):
    parsed = parse_input(raw)
    assert parsed.kind == kind
    assert parsed.video_id == vid or kind == "avid"


def test_parse_input_page_hint():
    assert parse_input("https://www.bilibili.com/video/BV1GJ411x7h7/?p=3").page_hint == 3


def test_parse_input_short_link_detected():
    parsed = parse_input("https://b23.tv/AbCdEfG")
    assert parsed.kind == "shortlink"


def test_parse_input_rejects_garbage():
    parsed = parse_input("hello world")
    assert not parsed.ok


def test_normalize_bare_sessdata():
    cookie, ua = normalize("abc123def")
    assert cookie == "SESSDATA=abc123def"
    assert ua is None


def test_normalize_full_cookie_header():
    cookie, _ = normalize("SESSDATA=abc; buvid3=xyz; b_nut=1")
    assert cookie.startswith("SESSDATA=abc")
    assert "buvid3=xyz" in cookie


def test_normalize_cookie_prefix():
    cookie, _ = normalize("Cookie: SESSDATA=abc; b_nut=1")
    assert cookie == "SESSDATA=abc; b_nut=1"


def test_normalize_curl_extracts_cookie_and_ua():
    curl = (
        "curl 'https://api.bilibili.com/x/v2/reply?pn=1' "
        "-H 'accept: application/json' "
        "-H 'cookie: SESSDATA=abc; buvid3=def' "
        "-H 'user-agent: MyBrowser/1.0'"
    )
    cookie, ua = normalize(curl)
    assert cookie == "SESSDATA=abc; buvid3=def"
    assert ua == "MyBrowser/1.0"


def test_normalize_empty():
    assert normalize("") == (None, None)
    assert normalize(None) == (None, None)
