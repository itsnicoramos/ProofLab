"""Flashcards from the student's own notes (SPEC §15.2), by written rules, no AI.

The text comes from a paste, or from the reader (:mod:`prooflab.reader`) for photos, PDFs and
documents. Each rule looks for a shape people use when they write down a definition or a fact:

1. ``Q: question`` followed by ``A: answer``.
2. ``Definition 1.2 (Term): text``, ``Theorem 3 (Name). statement`` (also Lemma, Corollary,
   Proposition, Principle, Law, Rule).
3. ``Term: meaning``, ``Term :: meaning``, ``Term - meaning``.
4. ``Name = formula`` (a short name, then math).
5. Sentences: "X is defined as ...", "... is called X", "A X is a ...", "X means ...",
   "We say n is X if ...".

Lines broken by a page or a photo are joined first. Every card says which rule made it, and the
student reviews and edits the list before anything is saved, so a wrong guess costs one tap.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_TEXT = 200_000
MAX_CARDS = 300
MAX_FRONT = 80
MAX_BACK = 400

RULES = {
    "qa": "Q and A",
    "labelled": "Definition or theorem label",
    "colon": "Term: meaning",
    "dash": "Term - meaning",
    "formula": "Name = formula",
    "defined-as": "“... is defined as ...”",
    "is-called": "“... is called ...”",
    "is-a": "“A ... is a ...”",
    "means": "“... means ...”",
    "we-say": "“We say ... if ...”",
    "is-if": "“... is ... if ...”",
}


@dataclass(frozen=True)
class NoteCard:
    front: str
    back: str
    type: str  # definition | theorem | fact
    rule: str
    line: int  # 1-based line in the original text where the card starts


# --------------------------------------------------------------------------- text cleanup

_BULLET = re.compile(r"^\s*(?:[-*•◦▪–·>]|\(?[0-9]{1,2}[.)]|\(?[a-z][.)])\s+")
_ENDS_SENTENCE = re.compile(r"[.:;?!)\]]\s*$")
_LABEL_WORDS = {
    "note",
    "notes",
    "example",
    "examples",
    "ex",
    "exercise",
    "exercises",
    "proof",
    "solution",
    "answer",
    "hint",
    "remark",
    "date",
    "name",
    "page",
    "lecture",
    "chapter",
    "section",
    "week",
    "class",
    "homework",
    "hw",
    "due",
    "todo",
    "q",
    "a",
    "question",
    "step",
    "case",
    "warning",
    "recall",
    "review",
    "summary",
    "goal",
    "idea",
    "e.g",
    "i.e",
    "eg",
    "ie",
    "see",
    "source",
}
_LABELLED = re.compile(
    r"^(?P<label>definition|defn|def|theorem|thm|lemma|corollary|cor|proposition|prop|"
    r"principle|law|rule|axiom|fact)\b\.?\s*(?P<num>[0-9]+(?:\.[0-9]+)*)?\s*"
    r"(?:\((?P<name>[^)]{1,60})\))?\s*[:.\-–]?\s*(?P<body>.*)$",
    re.IGNORECASE,
)
_THEOREMISH = {
    "theorem",
    "thm",
    "lemma",
    "corollary",
    "cor",
    "proposition",
    "prop",
    "principle",
    "law",
    "rule",
    "axiom",
    "fact",
}
_MATH_CHARS = re.compile(r"[=^+*/\\$∑∫√∈≤≥<>]|\d")


def _strip_markup(s: str) -> str:
    return re.sub(r"(\*\*|__|\*|_)(?=\S)(.+?)(?<=\S)\1", r"\2", s).strip()


def _logical_lines(text: str) -> list[tuple[int, str]]:
    """Join lines that a page break or a photo split mid-sentence. Keeps the start line number."""
    out: list[tuple[int, str]] = []
    for number, raw in enumerate(text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), 1):
        line = raw.replace(" ", " ").strip()
        if not line:
            out.append((number, ""))
            continue
        bullet = bool(_BULLET.match(line))
        line = _BULLET.sub("", line).strip()
        prev = out[-1][1] if out else ""
        continues = (
            prev
            and not bullet
            and not _ENDS_SENTENCE.search(prev)
            and (line[:1].islower() or line[:1] in "($\\")
            and not _LABELLED.match(line)
            and not re.match(r"^(q|a)\s*[:.]", line, re.IGNORECASE)
        )
        if continues:
            out[-1] = (out[-1][0], f"{prev} {line}")
        else:
            out.append((number, line))
    return [(n, re.sub(r"\s+", " ", s)) for n, s in out if s]


_ABBREV = re.compile(r"\b(e\.g|i\.e|etc|vs|cf|resp|approx|Fig|Eq|Def|Thm|Prop|Cor|Ex|No)\.$", re.I)


def _sentences(line: str) -> list[str]:
    """Split on sentence ends, but not inside $...$ math or after "e.g." and the like."""
    parts: list[str] = []
    buf = ""
    in_math = False
    i = 0
    while i < len(line):
        ch = line[i]
        buf += ch
        if ch == "$":
            in_math = not in_math
        elif (
            ch in ".?!"
            and not in_math
            and (i + 1 == len(line) or line[i + 1] == " ")
            and not _ABBREV.search(buf)
            and not re.search(r"\d\.$", buf)
        ):
            parts.append(buf.strip())
            buf = ""
        i += 1
    if buf.strip():
        parts.append(buf.strip())
    return parts


# --------------------------------------------------------------------------- rules


def _clean_front(term: str, *, question: bool = False, article: bool = True) -> str | None:
    term = _strip_markup(term).strip(" :;,.–-\"'“”")
    if article:  # "the power set" -> "power set"; off when "a" may be a variable ("a divides b")
        term = re.sub(r"^(?:the|a|an)\s+", "", term, flags=re.IGNORECASE)
    if not term or len(term) > MAX_FRONT:
        return None
    if term.lower().rstrip(".") in _LABEL_WORDS:
        return None
    words = term.split()
    if (len(words) > 7 and not question) or not re.search(r"[A-Za-z$\\]", term):
        return None
    return term


def _clean_back(text: str) -> str:
    text = _strip_markup(text).strip()
    if len(text) > MAX_BACK:
        cut = text[:MAX_BACK]
        end = max(cut.rfind(". "), cut.rfind("; "))
        text = (cut[: end + 1] if end > 80 else cut.rstrip() + "…").strip()
    return text[0].upper() + text[1:] if text and text[0].islower() else text


def _wordy(text: str, minimum: int = 3) -> bool:
    return len(re.findall(r"[A-Za-z]{2,}|\$[^$]+\$", text)) >= minimum


_COLON = re.compile(r"^(?P<term>[^:]{1,80}?)\s*(?:::|:)\s+(?P<def>.+)$")
_DASH = re.compile(r"^(?P<term>[^-–—]{1,80}?)\s+[-–—]{1,2}\s+(?P<def>.+)$")
_FORMULA = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z ']{1,40}?)\s*(?:(?<![<>!=])=(?![=>])|:=)\s*(?P<expr>.+)$"
)
_DEFINED_AS = re.compile(
    r"^(?:an?\s+|the\s+)?(?P<term>.{1,60}?)\s+(?:is|are)\s+(?:defined as|defined to be|"
    r"said to be|known as)\s+(?P<def>.+)$",
    re.IGNORECASE,
)
_IS_CALLED = re.compile(
    r"^(?P<def>.{8,}?)\s+(?:is|are)\s+called\s+(?:an?\s+|the\s+)?(?P<term>[^,;.]{1,50}?)\s*"
    r"(?:\(.*\))?[.]?$",
    re.IGNORECASE,
)
_IS_A = re.compile(
    r"^(?:an?|the)\s+(?P<term>[A-Za-z][\w'\-=>~$\\^ ]{0,40}?)\s+is\s+(?:an?|the|any)\s+"
    r"(?P<rest>.+)$",
    re.IGNORECASE,
)
_MEANS = re.compile(
    r"^(?P<term>.{1,60}?)\s+(?:means|refers to|denotes|stands for)\s+(?P<def>.+)$", re.IGNORECASE
)
_WE_SAY = re.compile(
    r"^we say(?: that)?\s+(?P<phrase>.{1,60}?)\s+(?:if|when|provided|whenever)\b\s*(?P<cond>.+)$",
    re.IGNORECASE,
)
# "An integer n is even if n = 2a ...": the adjective being defined comes before "if".
_IS_IF = re.compile(
    r"^(?:an?\s+|the\s+)?(?P<subj>[A-Za-z][\w ]{0,30}?)(?:\s+\$?[A-Za-z][\w,]*\$?)?\s+"
    r"(?:is|are)\s+(?:said to be\s+|called\s+)?(?:an?\s+)?(?P<term>[A-Za-z][\w\- ]{0,30}?)\s+"
    r"(?:if|when|provided|whenever|exactly when|if and only if)\b\s*(?P<cond>.+)$",
    re.IGNORECASE,
)
_PHRASE_IS = re.compile(r"^.{1,40}?\s+(?:is|are)\s+(?:an?\s+)?(?P<term>.+)$", re.IGNORECASE)


def _labelled(line: str) -> tuple[str, str, str] | None:
    m = _LABELLED.match(line)
    if not m or not m["body"] or not _wordy(m["body"], 2):
        return None
    label = m["label"].lower()
    kind = "theorem" if label in _THEOREMISH else "definition"
    body = m["body"].strip()
    name = (m["name"] or "").strip()
    if not name and kind == "definition":
        inner = _DEFINED_AS.match(body) or _IS_IF.match(body) or _IS_A.match(body)
        if inner:
            name = inner["term"]
        elif said := _we_say_term(body):
            name = said
        else:
            stressed = re.search(r"(\*\*|__|\*|_)(?=\S)(.+?)(?<=\S)\1", body)
            name = stressed[2] if stressed else ""
    shown = {
        "thm": "Theorem",
        "def": "Definition",
        "defn": "Definition",
        "prop": "Proposition",
        "cor": "Corollary",
    }.get(label, label.capitalize())
    if kind == "definition" and name:
        front = name
    else:
        front = " ".join(x for x in (shown, m["num"] or "", f"({name})" if name else "") if x)
    return front, body, kind


def _line_rules(line: str) -> tuple[str, str, str, str] | None:
    """Whole-line shapes. Returns (front, back, type, rule)."""
    if labelled := _labelled(line):
        front, back, kind = labelled
        return front, back, kind, "labelled"
    for pattern, rule in ((_COLON, "colon"), (_DASH, "dash")):
        m = pattern.match(line)
        if m and _wordy(m["def"]) and len(m["term"].split()) <= 6 and "=" not in m["term"]:
            return m["term"], m["def"], "definition", rule
    m = _FORMULA.match(line)
    if m and _MATH_CHARS.search(m["expr"]) and len(m["name"].split()) <= 4:
        name = m["name"].strip()
        if name.lower() not in _LABEL_WORDS and len(name) > 1:
            return name, line, "fact", "formula"
    return None


def _we_say_term(sentence: str) -> str | None:
    m = _WE_SAY.match(sentence)
    if not m:
        return None
    inner = _PHRASE_IS.match(m["phrase"])
    return inner["term"] if inner else m["phrase"]


def _sentence_rules(sentence: str) -> tuple[str, str, str, str] | None:
    s = sentence.strip()
    if term := _we_say_term(s):
        return term, s, "definition", "we-say"
    if m := _DEFINED_AS.match(s):
        return m["term"], s, "definition", "defined-as"
    if m := _IS_CALLED.match(s):
        return m["term"], s, "definition", "is-called"
    if m := _IS_IF.match(s):
        if len(m["term"].split()) <= 3:
            return m["term"], s, "definition", "is-if"
    if m := _MEANS.match(s):
        if len(m["term"].split()) <= 5:
            return m["term"], s, "definition", "means"
    if m := _IS_A.match(s):
        if len(m["term"].split()) <= 4 and len(m["rest"]) >= 12 and _wordy(m["rest"], 1):
            return m["term"], s, "definition", "is-a"
    return None


def extract_cards(text: str) -> list[NoteCard]:
    """Every card the rules find in ``text``, in reading order, without duplicates."""
    text = text[:MAX_TEXT]
    lines = _logical_lines(text)
    cards: list[NoteCard] = []
    seen: set[str] = set()

    def add(front: str, back: str, kind: str, rule: str, number: int) -> None:
        f = _clean_front(front, question=rule == "qa", article=rule != "we-say")
        b = _clean_back(back)
        if not f or not b or not _wordy(b, 2) or f.lower() == b.lower():
            return
        key = f.lower()
        if key in seen or len(cards) >= MAX_CARDS:
            return
        seen.add(key)
        cards.append(NoteCard(front=f, back=b, type=kind, rule=rule, line=number))

    i = 0
    while i < len(lines):
        number, line = lines[i]
        q = re.match(r"^q(?:uestion)?\s*[0-9]*\s*[:.)]\s*(?P<q>.+)$", line, re.IGNORECASE)
        if q and i + 1 < len(lines):
            a = re.match(r"^a(?:nswer)?\s*[:.)]\s*(?P<a>.+)$", lines[i + 1][1], re.IGNORECASE)
            if a:
                question = q["q"].strip()
                if len(question) <= MAX_FRONT:
                    add(question, a["a"], "fact", "qa", number)
                    i += 2
                    continue
        if found := _line_rules(line):
            add(*found, number)
        else:
            for sentence in _sentences(line):
                if found := _sentence_rules(sentence):
                    add(*found, number)
        i += 1
    return cards
