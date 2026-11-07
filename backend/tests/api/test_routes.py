from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient

from prooflab.content import Registry, load_registry
from prooflab.engine.models import ReviewStatus
from prooflab.main import Settings, create_app

# The API tests use the calc1 content only, so they don't depend on other courses' content.
REGISTRY = load_registry(courses=["calc1"])
PRODUCT = "calc1.derivatives.product-rule"
SECRET_FIELDS = {"answer", "mistakes", "examples", "solution", "data"}


def make_client(registry: Registry = REGISTRY, **settings) -> TestClient:
    base = {"isolate": False, "busy_wait": 0.05}
    return TestClient(create_app(Settings(**(base | settings)), registry))


@pytest.fixture(scope="module")
def client() -> TestClient:
    return make_client()


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["problems"] == len(REGISTRY.served())


def test_courses_lists_every_track(client):
    body = client.get("/courses").json()
    assert [c["id"] for c in body] == ["proofs", "precalc", "calc1", "calc2", "calc3", "calc4"]
    calc1 = next(c for c in body if c["id"] == "calc1")
    assert [t["topic"] for t in calc1["topics"]] == ["limits", "derivatives"]
    assert calc1["problems"] == sum(t["problems"] for t in calc1["topics"]) > 0
    # MATH 123's topics are Book of Proof's chapters, in book order, even when empty
    proofs = next(c for c in body if c["id"] == "proofs")
    topics = [t["topic"] for t in proofs["topics"]]
    assert topics[:3] == ["sets", "logic", "counting"] and len(topics) == 14


def test_list_and_filter_problems(client):
    everything = client.get("/problems").json()
    assert len(everything) == len(REGISTRY.served())
    assert all(SECRET_FIELDS.isdisjoint(p) for p in everything)

    limits = client.get("/problems", params={"topic": "limits"}).json()
    assert limits and all(p["topic"] == "limits" for p in limits)
    tangent = client.get("/problems", params={"kind": "tangent_line"}).json()
    assert [p["id"] for p in tangent] == ["calc1.derivatives.tangent-cubic"]
    assert client.get("/problems", params={"tag": "lhopital"}).json()
    assert client.get("/problems", params={"course": "calc2"}).json() == []
    assert client.get("/problems", params={"difficulty": 9}).status_code == 422
    assert client.get("/problems", params={"course": "history"}).status_code == 422


def test_problem_detail_hides_the_answer(client):
    body = client.get(f"/problems/{PRODUCT}").json()
    assert SECRET_FIELDS.isdisjoint(body)
    assert body["prompt"] and body["syntax_help"] and body["hint_count"] >= 1
    assert body["reference"]["url"].startswith("https://") and body["reference"]["license"]
    assert body["review"]["status"] == "draft"
    assert "expr" in body["step_kinds"]
    assert body["has_answer"] is True


def test_solution_endpoint(client):
    body = client.get(f"/problems/{PRODUCT}/solution").json()
    assert body["answer"] == REGISTRY.problems[PRODUCT].answer
    assert body["solution"]


def test_unknown_problem_is_404(client):
    assert client.get("/problems/calc1.derivatives.nope").status_code == 404
    assert client.get("/problems/calc1.derivatives.nope/solution").status_code == 404
    assert client.post("/check", json={"problem_id": "nope", "answer": "1"}).status_code == 404


def test_check_correct_and_incorrect(client):
    ok = client.post("/check", json={"problem_id": PRODUCT, "answer": "2x sin(x) + x^2 cos(x)"})
    assert ok.status_code == 200
    assert ok.json()["status"] == "correct" and ok.json()["score"] == 1.0

    wrong = client.post(
        "/check",
        json={
            "problem_id": PRODUCT,
            "steps": [{"kind": "expr", "content": "2x cos(x)"}],
            "answer": "2x cos(x)",
            "hints_revealed": 0,
        },
    ).json()
    assert wrong["status"] == "incorrect" and wrong["score"] == 0
    assert wrong["steps"][0]["status"] == "error"
    hint_codes = {h["code"] for h in wrong["hints"]}
    assert {"PRODUCT_RULE", "AUTHORED_HINT"} <= hint_codes


def test_check_rejects_malformed_requests(client):
    assert client.post("/check", json={"answer": "1"}).status_code == 422
    too_many = [{"content": "x"}] * 41
    assert client.post("/check", json={"problem_id": PRODUCT, "steps": too_many}).status_code == 422
    too_long = {"problem_id": PRODUCT, "answer": "x" * 501}
    assert client.post("/check", json=too_long).status_code == 422
    extra = {"problem_id": PRODUCT, "answer": "1", "cheat": True}
    assert client.post("/check", json=extra).status_code == 422


def test_check_runs_in_an_isolated_worker():
    with make_client(isolate=True, check_timeout=60) as isolated:
        body = isolated.post(
            "/check", json={"problem_id": PRODUCT, "answer": "2x sin x + x^2 cos x"}
        )
        assert body.status_code == 200 and body.json()["status"] == "correct"


def test_busy_server_returns_503():
    c = make_client(max_concurrent_checks=1)
    slots: threading.BoundedSemaphore = c.app.state.check_slots
    slots.acquire()
    try:
        assert c.post("/check", json={"problem_id": PRODUCT, "answer": "1"}).status_code == 503
    finally:
        slots.release()


def test_retired_problems_are_not_served():
    problems = dict(REGISTRY.problems)
    retired = problems[PRODUCT].model_copy(
        update={
            "review": problems[PRODUCT].review.model_copy(update={"status": ReviewStatus.RETIRED})
        }
    )
    problems[PRODUCT] = retired
    c = make_client(Registry(references=REGISTRY.references, problems=problems))
    assert PRODUCT not in {p["id"] for p in c.get("/problems").json()}
    assert c.get(f"/problems/{PRODUCT}").status_code == 404
    assert c.get("/problems", params={"status": "retired"}).json() == []


def test_cors_allows_the_frontend_origin(client):
    r = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
    r = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("PROOFLAB_CORS_ORIGINS", "https://a.example, https://b.example")
    monkeypatch.setenv("PROOFLAB_CHECK_TIMEOUT", "3.5")
    monkeypatch.setenv("PROOFLAB_ISOLATE", "0")
    monkeypatch.setenv("PROOFLAB_MAX_CONCURRENT_CHECKS", "2")
    s = Settings.from_env()
    assert s.cors_origins == ["https://a.example", "https://b.example"]
    assert (s.check_timeout, s.isolate, s.max_concurrent_checks) == (3.5, False, 2)
