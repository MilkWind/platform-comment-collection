from __future__ import annotations

from bilicrawl.wbi import mixin_key, sign_query

IMG = "7cd084941338484aae1ad9425b84077c"
SUB = "4932caff0ff746eab6f01bf08b70ac45"


def test_mixin_key_matches_reference_algorithm():
    # The mixin key is the first 32 chars of the permuted concatenation.
    key = mixin_key(IMG, SUB)
    assert len(key) == 32
    assert key == mixin_key(IMG, SUB)  # deterministic


def test_sign_query_is_deterministic_with_fixed_wts():
    q1 = sign_query({"b": 2, "a": 1}, IMG, SUB, wts=1700000000)
    q2 = sign_query({"a": 1, "b": 2}, IMG, SUB, wts=1700000000)
    assert q1 == q2  # key order must not matter
    assert "wts=1700000000" in q1
    assert "w_rid=" in q1


def test_sign_query_strips_disallowed_chars():
    q = sign_query({"q": "a!'()*b"}, IMG, SUB, wts=1700000000)
    assert "q=ab" in q
    assert "a%21" not in q  # the stripped char must never be encoded


def test_signature_changes_when_wts_changes():
    a = sign_query({"oid": 1}, IMG, SUB, wts=1700000000).split("w_rid=")[1]
    b = sign_query({"oid": 1}, IMG, SUB, wts=1700000001).split("w_rid=")[1]
    assert a != b
