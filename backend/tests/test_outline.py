"""The course outline (content/courses.json) and how the loader applies it (SPEC §4, §8)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from prooflab.content import CONTENT_DIR, ContentLoadError, load_outline, load_registry

BOOK_CHAPTERS = [
    "sets",
    "logic",
    "counting",
    "direct",
    "contrapositive",
    "contradiction",
    "nonconditional",
    "set-proofs",
    "disproof",
    "induction",
    "relations",
    "functions",
    "calculus-proofs",
    "cardinality",
]


def test_proofs_topics_are_the_books_chapters():
    outline = load_outline()
    assert outline["proofs"].topics == BOOK_CHAPTERS
    assert set(outline) == {"proofs", "precalc", "calc1", "calc2", "calc3", "calc4"}


def _problem(path: Path, topic: str, status: str = "draft") -> dict:
    src = CONTENT_DIR / "problems/proofs/direct/ch4-ex01.json"
    data = json.loads(src.read_text(encoding="utf-8"))
    data["id"] = f"proofs.{topic}.t-{path.stem}"
    data["topic"] = topic
    data["review"] = {"status": status}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


@pytest.fixture
def content(tmp_path: Path) -> Path:
    shutil.copy(CONTENT_DIR / "references.json", tmp_path / "references.json")
    shutil.copy(CONTENT_DIR / "courses.json", tmp_path / "courses.json")
    (tmp_path / "problems/proofs").mkdir(parents=True)
    return tmp_path


def test_topics_folders_and_retired_problems(content: Path):
    _problem(content / "problems/proofs/direct/a.json", "direct")
    _problem(content / "problems/proofs/disproof/b.json", "disproof")
    _problem(content / "problems/proofs/retired/c.json", "parity", status="retired")
    registry = load_registry(content)
    assert len(registry.problems) == 3
    # served in outline (book) order, retired problems left out
    assert [p.topic for p in registry.served()] == ["direct", "disproof"]


@pytest.mark.parametrize(
    ("rel", "topic", "status", "message"),
    [
        ("problems/proofs/x.json", "nonsense", "draft", "unknown topic"),
        ("problems/proofs/x.json", "parity", "draft", "is retired"),
        ("problems/proofs/retired/x.json", "direct", "draft", "only retired problems"),
        ("problems/proofs/direct/x.json", "disproof", "draft", "file is under direct/"),
    ],
)
def test_bad_topics(content: Path, rel: str, topic: str, status: str, message: str):
    _problem(content / rel, topic, status)
    with pytest.raises(ContentLoadError, match=message):
        load_registry(content)


def test_bad_outline(content: Path):
    outline = json.loads((content / "courses.json").read_text(encoding="utf-8"))
    outline["courses"] = [c for c in outline["courses"] if c["id"] != "calc4"]
    (content / "courses.json").write_text(json.dumps(outline), encoding="utf-8")
    with pytest.raises(ContentLoadError, match="no outline"):
        load_outline(content)
    outline["courses"][0]["topics"].append("sets")
    (content / "courses.json").write_text(json.dumps(outline), encoding="utf-8")
    with pytest.raises(ContentLoadError, match="unique"):
        load_outline(content)
