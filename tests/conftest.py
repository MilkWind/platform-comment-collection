"""Shared fixtures: an offline transport and a no-network guard.

Any test that forgets to inject a transport fails loudly instead of hitting
Bilibili. Live tests must be marked and are run explicitly via ``--live``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "bilibili"
CORE = ROOT / "skills" / "bilibili" / "core"
for path in (str(ROOT), str(CORE)):
    if path not in sys.path:
        sys.path.insert(0, path)

from bilicrawl.http import TransportResponse  # noqa: E402


def pytest_addoption(parser):
    parser.addoption("--live", action="store_true", help="run live network tests")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--live"):
        return
    skip = pytest.mark.skip(reason="live network test; pass --live to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Fail loudly on any real network attempt during unit tests."""
    import requests

    def _blocked(*args, **kwargs):
        raise AssertionError("unit test attempted real network access")

    monkeypatch.setattr(requests.Session, "request", _blocked)


class FixtureTransport:
    """Routes a URL to a recorded fixture by path fragment."""

    def __init__(
        self, routes: dict[str, Path] | None = None, *, json_routes: dict[str, dict] | None = None
    ):
        self.routes = routes or {}
        self.json_routes = json_routes or {}
        self.calls: list[str] = []

    def request(self, method, url, *, params=None, headers=None, timeout=20.0) -> TransportResponse:
        self.calls.append(url)
        for fragment, path in self.routes.items():
            if fragment in url:
                return TransportResponse(200, Path(path).read_bytes(), url, {})
        for fragment, payload in self.json_routes.items():
            if fragment in url:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                return TransportResponse(200, body, url, {})
        raise AssertionError(f"no fixture route for {url}")


@pytest.fixture
def fx() -> dict[str, Path]:
    return {
        "view.json": FIXTURES / "view.json",
        "comment_page_1.json": FIXTURES / "comment_page_1.json",
        "sub_reply_page_1.json": FIXTURES / "sub_reply_page_1.json",
        "dm_seg_1.bin": FIXTURES / "dm_seg_1.bin",
    }


@pytest.fixture
def bilibili_transport(fx) -> FixtureTransport:
    return FixtureTransport(
        routes={
            "/x/web-interface/view": fx["view.json"],
            "/x/v2/reply/wbi/main": fx["comment_page_1.json"],
            "/x/v2/reply/reply": fx["sub_reply_page_1.json"],
            "/x/v2/dm/web/seg.so": fx["dm_seg_1.bin"],
        },
        json_routes={
            "/x/web-interface/nav": {
                "code": -101,
                "message": "账号未登录",
                "data": {
                    "isLogin": False,
                    "wbi_img": {
                        "img_url": "https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png",
                        "sub_url": "https://i0.hdslb.com/bfs/wbi/4932caff0ff746eab6f01bf08b70ac45.png",
                    },
                },
            }
        },
    )
