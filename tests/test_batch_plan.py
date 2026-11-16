"""Offline tests for batch planning: line numbers, dedupe, canonical inputs."""

from __future__ import annotations

from bilicrawl.models import ParsedInput

from app.engine.batch import plan_batch, split_input_lines


class StubModule:
    """Minimal stand-in for a platform module's parse_input."""

    @staticmethod
    def parse_input(raw: str) -> ParsedInput:
        text = raw.strip()
        if text.startswith("BV"):
            return ParsedInput(kind="bvid", video_id=text)
        if "/video/BV" in text:
            bv = text.split("/video/")[1].split("/")[0].split("?")[0]
            return ParsedInput(kind="url", video_id=bv)
        if text.startswith("av"):
            return ParsedInput(kind="avid", aid=int(text[2:]))
        if "b23.tv" in text:
            return ParsedInput(kind="shortlink")
        return ParsedInput(kind="unknown", error="no BV id or av id found")


def test_split_keeps_original_line_numbers():
    text = "\n# comment\nBV1\n\n  BV2  \n"
    lines = split_input_lines(text)
    assert [(line.line_no, line.raw) for line in lines] == [(3, "BV1"), (5, "BV2")]


def test_plan_dedupes_bv_url_and_page_hint():
    plan = plan_batch(
        StubModule,
        "BV1aaaaaaaaa\nhttps://www.bilibili.com/video/BV1aaaaaaaaa/?p=2\nBV1bbbbbbbbb",
    )
    assert [item.resolve_input for item in plan.items] == ["BV1aaaaaaaaa", "BV1bbbbbbbbb"]
    assert plan.duplicates == ((2, 1),)
    assert plan.invalid == ()


def test_plan_keeps_av_and_reports_invalid():
    plan = plan_batch(StubModule, "av170001\nnot a link\nhttps://b23.tv/xyz")
    assert plan.items[0].resolve_input == "av170001"
    assert plan.items[1].raw == "https://b23.tv/xyz"
    assert [(line.line_no, line.raw) for line in plan.invalid] == [(2, "not a link")]


def test_signature_tracks_content_not_blank_lines():
    a = plan_batch(StubModule, "BV1aaaaaaaaa\nBV1bbbbbbbbb")
    b = plan_batch(StubModule, "\nBV1aaaaaaaaa\n\nBV1bbbbbbbbb\n")
    c = plan_batch(StubModule, "BV1aaaaaaaaa\nBV1ccccccccc")
    assert a.signature == b.signature
    assert a.signature != c.signature
