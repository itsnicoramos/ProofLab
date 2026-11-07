"""Flashcards from notes (SPEC §15.2) and the /cards endpoints (§15)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from prooflab.cards import load_cards
from prooflab.content import CONTENT_DIR, load_outline, load_references, load_registry
from prooflab.main import Settings, create_app
from prooflab.notes import extract_cards

NOTES = """MATH 123 Lecture 5 - Sept 30
Definition 4.1. An integer n is even if n = 2a for some integer a.
Definition (Odd): an integer n is odd if n = 2a + 1 for some
integer a.
Theorem 4.2 (Division Algorithm) Given integers a and b with b > 0, there exist
unique integers q and r with a = qb + r and 0 <= r < b.
- Prime: a natural number p > 1 whose only positive divisors are 1 and p.
* Composite - a natural number n > 1 that is not prime.
Power set :: the set of all subsets of a set A.
Note: the exam is on Friday.
We say that a divides b if b = ac for some integer c.
A set is a collection of things called its elements.
The contrapositive of P => Q is the statement ~Q => ~P.
gcd(a, b) means the largest integer that divides both a and b.
Area of circle = pi r^2
Q: What is the cardinality of the empty set?
A: Zero, since it has no elements.
The answer is 5.
Example: 6 is even.
"""


def fronts(text: str) -> dict[str, str]:
    return {c.front: c.rule for c in extract_cards(text)}


def test_each_rule_finds_its_shape():
    found = fronts(NOTES)
    assert found["even"] == "labelled"
    assert found["Odd"] == "labelled"
    assert found["Theorem 4.2 (Division Algorithm)"] == "labelled"
    assert found["Prime"] == "colon"
    assert found["Composite"] == "dash"
    assert found["Power set"] == "colon"
    assert found["a divides b"] == "we-say"
    assert found["set"] == "is-a"
    assert found["gcd(a, b)"] == "means"
    assert found["Area of circle"] == "formula"
    assert found["What is the cardinality of the empty set?"] == "qa"


def test_skips_labels_and_chatter():
    found = fronts(NOTES)
    assert not any(f.lower().startswith(("note", "example", "the answer")) for f in found)


def test_broken_lines_are_joined():
    cards = extract_cards(NOTES)
    odd = next(c for c in cards if c.front == "Odd")
    assert odd.back.endswith("for some integer a.")
    assert odd.line == 3


def test_called_names_the_term():
    [card] = extract_cards("An integer that can be written as 2a is called even.")
    assert card.front == "even" and card.rule == "is-called"


def test_no_duplicates_and_limits():
    cards = extract_cards(NOTES + NOTES)
    assert len({c.front.lower() for c in cards}) == len(cards)
    assert all(len(c.back) <= 400 for c in extract_cards("Term: " + "word " * 300))


def test_math_inside_dollars_is_not_split():
    [card] = extract_cards("Mean: the average $\\bar{x} = 1/n. \\sum x_i$ of the values.")
    assert "\\sum" in card.back


def test_bad_card_files_are_reported(tmp_path):
    (tmp_path / "cards").mkdir()
    bad = {
        "course": "proofs",
        "cards": [
            {
                "id": "proofs.sets.a",
                "topic": "sets",
                "type": "definition",
                "front": "Set",
                "back": "A collection of things.",
                "reference": {"book": "hammack-bop3", "section": "1.1"},
            },
            {
                "id": "proofs.sets.b",
                "topic": "sets",
                "type": "definition",
                "front": "set",
                "back": "Another one — with a dash.",
                "reference": {"book": "nobook", "section": "1.1"},
            },
        ],
    }
    (tmp_path / "cards" / "proofs.json").write_text(json.dumps(bad))
    _, errors = load_cards(tmp_path, load_outline(CONTENT_DIR), load_references(CONTENT_DIR))
    text = "\n".join(errors)
    assert "share the front" in text and "unknown reference" in text and "em dash" in text


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(Settings(isolate=False), load_registry(courses=["proofs"])))


def test_cards_endpoint(client):
    r = client.get("/cards", params={"course": "proofs", "topics": "direct"})
    assert r.status_code == 200
    deck = r.json()
    assert deck and all(c["topic"] == "direct" for c in deck)
    problems = [c for c in deck if c["type"] == "problem"]
    assert problems and all(c["back"] and c["citation"] for c in problems)
    concepts = [c for c in deck if c["type"] != "problem"]
    if concepts:  # concept cards come first inside a topic
        assert deck.index(concepts[-1]) < deck.index(problems[0])
    only = client.get("/cards", params={"course": "proofs", "parts": "problems"}).json()
    assert all(c["type"] == "problem" for c in only)


def test_from_notes_endpoint(client):
    r = client.post("/cards/from-notes", json={"text": NOTES})
    assert r.status_code == 200
    body = r.json()
    assert body["lines"] == NOTES.count("\n") + 1
    assert {"front", "back", "rule", "rule_label", "line"} <= set(body["cards"][0])
    assert client.post("/cards/from-notes", json={"text": "x" * 200_001}).status_code == 422
