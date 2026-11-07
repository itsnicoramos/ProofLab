"""The progress database (SPEC §17): sync semantics and the /store endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from prooflab.content import load_registry
from prooflab.main import Settings, create_app
from prooflab.store import Store, SyncIn


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "p.sqlite3")
    yield s
    s.close()


def ops(*items):
    return SyncIn.model_validate({"ops": list(items)}).ops


def review(uid, item="proofs.sets.def-set", grade=3, at=1000):
    return {
        "op": "review",
        "uid": uid,
        "item": item,
        "kind": "card",
        "course": "proofs",
        "topic": "sets",
        "grade": grade,
        "at": at,
    }


def test_reviews_are_idempotent_and_merge(store):
    assert store.apply(ops(review("a"), review("b", at=2000))) == 2
    assert store.apply(ops(review("a"), review("c", at=1500))) == 1  # "a" again is ignored
    assert [r["uid"] for r in store.snapshot()["reviews"]] == ["a", "c", "b"]
    store.apply(ops({"op": "reset_reviews"}))
    assert store.snapshot()["reviews"] == []


def test_progress_only_goes_up(store):
    p = {"op": "progress", "problem_id": "proofs.sets.ch1-01-ex03", "at": 1}
    store.apply(ops({**p, "status": "partial"}))
    store.apply(ops({**p, "status": "incorrect"}))
    assert store.snapshot()["progress"] == {"proofs.sets.ch1-01-ex03": "partial"}
    store.apply(ops({**p, "status": "correct"}))
    assert store.snapshot()["progress"]["proofs.sets.ch1-01-ex03"] == "correct"


def test_decks_newest_write_wins_and_deletes_leave_tombstones(store):
    deck = {
        "op": "deck",
        "id": "d1",
        "name": "Lecture 5",
        "created_at": 10,
        "cards": [{"id": "c1", "front": "Prime", "back": "Only divisors 1 and itself."}],
        "updated_at": 20,
    }
    store.apply(ops(deck))
    store.apply(ops({**deck, "name": "Old name", "updated_at": 15}))  # older: ignored
    [d] = store.snapshot()["decks"]
    assert d["name"] == "Lecture 5" and d["cards"][0]["front"] == "Prime"
    store.apply(ops({"op": "deck_delete", "id": "d1", "updated_at": 30}))
    [d] = store.snapshot()["decks"]
    assert d["deleted"] and d["cards"] == []
    store.apply(ops({**deck, "updated_at": 25}))  # a stale copy can't bring it back
    assert store.snapshot()["decks"][0]["deleted"]


def test_tests_round_trip(store):
    record = {"title": "Quiz", "href": "/tests/proofs/quiz?seed=1", "questions": 3, "startedAt": 5}
    store.apply(ops({"op": "test", "id": "quiz-abc", "record": record, "updated_at": 5}))
    store.apply(
        ops({"op": "test", "id": "quiz-abc", "record": {**record, "score": 2}, "updated_at": 9})
    )
    [t] = store.snapshot()["tests"]
    assert t["record"]["score"] == 2 and not t["deleted"]
    store.apply(ops({"op": "test_delete", "id": "quiz-abc", "updated_at": 10}))
    assert store.snapshot()["tests"][0]["deleted"]


def test_bad_operations_are_rejected():
    with pytest.raises(ValidationError):
        ops({**review("x"), "grade": 7})
    with pytest.raises(ValidationError):
        ops({"op": "drop_table"})
    with pytest.raises(ValidationError):
        ops({**review("x"), "item": "bad id with spaces"})


def test_store_endpoints(tmp_path):
    app = create_app(
        Settings(isolate=False, db_path=str(tmp_path / "api.sqlite3")),
        load_registry(courses=["proofs"]),
    )
    client = TestClient(app)
    assert client.get("/store").json()["reviews"] == []
    r = client.post("/store", json={"ops": [review("u1"), review("u2", at=5)]})
    assert r.json() == {"applied": 2, "received": 2}
    snap = client.get("/store").json()
    assert [x["uid"] for x in snap["reviews"]] == ["u2", "u1"]
    assert client.post("/store", json={"ops": [{"op": "nope"}]}).status_code == 422
    assert (tmp_path / "api.sqlite3").exists()


def test_serving_problems_never_opens_the_database(tmp_path):
    path = tmp_path / "untouched.sqlite3"
    client = TestClient(
        create_app(Settings(isolate=False, db_path=str(path)), load_registry(courses=["proofs"]))
    )
    assert client.get("/health").status_code == 200
    assert not path.exists()
