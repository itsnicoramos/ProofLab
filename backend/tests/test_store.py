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
    store.apply(ops({"op": "reset_reviews", "at": 1600}))
    snap = store.snapshot()
    assert [r["uid"] for r in snap["reviews"]] == ["b"]  # only reviews before the reset go
    assert snap["reviews_reset_at"] == 1600
    store.apply(ops({"op": "reset_reviews", "at": 900}))  # an older reset never moves it back
    assert store.snapshot()["reviews_reset_at"] == 1600


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


def activity(uid, type_="solve", at=1000, day="2026-11-08", data=None, item="proofs.direct.p1"):
    event = {
        "op": "activity",
        "uid": uid,
        "type": type_,
        "day": day,
        "at": at,
        "item": item,
        "course": "proofs",
        "topic": "direct",
    }
    if data is not None:
        event["data"] = data
    return event


def test_activity_is_append_only_and_idempotent(store):
    solve = {"difficulty": 2, "checks": 1, "hints": 0}
    test = {
        "kind": "midterm",
        "questions": [{"difficulty": 2, "format": "written", "status": "correct", "blank": False}],
    }
    assert store.apply(ops(activity("a", data=solve), activity("b", "reveal", at=900))) == 2
    assert (
        store.apply(
            ops(
                activity("a", data=solve),
                activity("c", "test", 1500, data=test, item="midterm-abc"),
            )
        )
        == 1
    )
    snap = store.snapshot()
    assert [e["uid"] for e in snap["activity"]] == ["b", "a", "c"]
    assert snap["activity"][1]["data"] == solve
    assert "data" not in snap["activity"][0]  # a reveal has no data
    assert snap["activity_reset_at"] is None
    # Undated earlier work keeps its null day.
    store.apply(
        ops(activity("old", day=None, at=0, data={"difficulty": 0, "checks": 0, "hints": 0}))
    )
    assert store.snapshot()["activity"][0]["day"] is None
    assert store.counts()["activity"] == 4


def test_reset_activity_forgets_everything_before_it(store):
    store.apply(ops(activity("a", at=1000), activity("b", at=2000), activity("z", day=None, at=0)))
    store.apply(ops({"op": "reset_activity", "at": 1500}))
    snap = store.snapshot()
    assert [e["uid"] for e in snap["activity"]] == ["b"]
    assert snap["activity_reset_at"] == 1500
    # An event from before the reset that arrives late (another device) stays forgotten.
    assert store.apply(ops(activity("late", at=1400), activity("old", day=None, at=0))) == 0
    assert store.apply(ops(activity("new", at=1600))) == 1
    # An older reset never moves it back.
    store.apply(ops({"op": "reset_activity", "at": 100}))
    assert store.snapshot()["activity_reset_at"] == 1500


def test_bad_activity_is_rejected(store):
    with pytest.raises(ValidationError):
        ops(activity("x", "bonus"))  # not a kind of event
    with pytest.raises(ValidationError):
        ops(activity("x", day="8 Nov"))
    with pytest.raises(ValidationError):
        ops({**activity("x"), "xp": 999})  # XP is never sent; it's computed from the facts
    with pytest.raises(ValueError, match="too large"):
        store.apply(ops(activity("x", data={"pad": "x" * 30_000})))


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


def test_store_can_be_switched_off(tmp_path):
    path = tmp_path / "off.sqlite3"
    settings = Settings(isolate=False, db_path=str(path), store=False)
    client = TestClient(create_app(settings, load_registry(courses=["proofs"])))
    assert client.get("/store").status_code == 404
    assert client.post("/store", json={"ops": []}).status_code == 404
    assert not path.exists()


def test_serving_problems_never_opens_the_database(tmp_path):
    path = tmp_path / "untouched.sqlite3"
    client = TestClient(
        create_app(Settings(isolate=False, db_path=str(path)), load_registry(courses=["proofs"]))
    )
    assert client.get("/health").status_code == 200
    assert not path.exists()
