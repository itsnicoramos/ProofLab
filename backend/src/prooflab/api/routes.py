"""HTTP endpoints (SPEC §7): /health, /courses, /problems, /problems/{id}[/solution], /check,
/practice-tests, /quiz/answer, /cards, /cards/from-notes, /read, /store."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool

from prooflab import __version__
from prooflab.api.schemas import (
    CheckRequest,
    ChoiceAnswerIn,
    ChoiceAnswerOut,
    ChoiceOptionOut,
    ChoiceOut,
    CitationOut,
    CourseSummary,
    DeckCardOut,
    Health,
    NoteCardOut,
    NotesIn,
    NotesOut,
    PracticeTestOut,
    ProblemDetail,
    ProblemSummary,
    QuestionOut,
    ReaderCapabilities,
    ReadLineOut,
    ReadOut,
    ReviewOut,
    SolutionOut,
    SpotStepOut,
    TopicSummary,
)
from prooflab.cards import build_deck
from prooflab.content import Registry
from prooflab.engine import hints
from prooflab.engine.checker import check, check_isolated, get_handler
from prooflab.engine.models import COURSE_TITLES, Course, Problem, ReviewStatus, Submission, Verdict
from prooflab.notes import RULES, extract_cards
from prooflab.practice import MAX_LENGTH, MINUTES_RULE, PracticeTestError, build_practice_test
from prooflab.quiz import ChoiceQuestion, build_question, grade
from prooflab.reader import MAX_BYTES, ReaderError, capabilities, read_document
from prooflab.store import Store, SyncIn, default_path, open_store

router = APIRouter()


def _registry(request: Request) -> Registry:
    return request.app.state.registry


def _variant(registry: Registry, problem_id: str) -> Problem | None:
    """A ProofLab-made version ("<base id>-v<seed>"), rebuilt from its id (SPEC §13.3)."""
    try:
        from prooflab.variants import make_variant, parse_variant_id
    except ImportError:  # pragma: no cover
        return None
    parsed = parse_variant_id(problem_id)
    if parsed is None:
        return None
    base = registry.get(parsed[0])
    return make_variant(base, parsed[1]) if base is not None else None


def _problem_or_404(request: Request, problem_id: str) -> Problem:
    registry = _registry(request)
    problem = registry.get(problem_id) or _variant(registry, problem_id)
    if problem is None:
        raise HTTPException(status_code=404, detail=f"No problem with id {problem_id!r}.")
    return problem


def _runner(request: Request):  # noqa: ANN202 - a Runner for prooflab.quiz
    settings = request.app.state.settings
    if not settings.isolate:
        return lambda problem, submission: check(problem, submission)
    timeout = min(5.0, settings.check_timeout)
    return lambda problem, submission: check_isolated(problem, submission, timeout=timeout)


def _choice_out(q: ChoiceQuestion) -> ChoiceOut:
    return ChoiceOut(
        format=q.format,
        seed=q.seed,
        stem=q.stem,
        choices=[ChoiceOptionOut(key=c.key, latex=c.latex, text=c.text) for c in q.choices],
        steps=[SpotStepOut(kind=s.kind, content=s.content, latex=s.latex) for s in q.steps],
        attempt_answer=q.attempt_answer,
    )


def _summary(p: Problem) -> ProblemSummary:
    return ProblemSummary(
        id=p.id,
        course=p.course,
        topic=p.topic,
        kind=p.kind,
        title=p.title,
        prompt=p.prompt,
        difficulty=p.difficulty,
        tags=p.tags,
        review_status=p.review.status,
        variant_of=_base_id(p),
    )


def _base_id(p: Problem) -> str | None:
    if "prooflab-variant" not in p.tags:
        return None
    base, _, _ = p.id.rpartition("-v")
    return base or None


@router.get("/health", response_model=Health, tags=["meta"])
def health(request: Request) -> Health:
    return Health(status="ok", version=__version__, problems=len(_registry(request).served()))


@router.get("/courses", response_model=list[CourseSummary], tags=["problems"])
def courses(request: Request) -> list[CourseSummary]:
    registry = _registry(request)
    served = registry.served()
    out = []
    for course in Course:
        in_course = [p for p in served if p.course is course]
        out.append(
            CourseSummary(
                id=course,
                title=COURSE_TITLES[course],
                problems=len(in_course),
                topics=[
                    TopicSummary(topic=t, problems=sum(p.topic == t for p in in_course))
                    for t in registry.topics.get(course.value, [])
                ],
            )
        )
    return out


@router.get("/problems", response_model=list[ProblemSummary], tags=["problems"])
def list_problems(
    request: Request,
    course: Course | None = None,
    topic: str | None = None,
    kind: str | None = None,
    tag: str | None = None,
    difficulty: Annotated[int | None, Query(ge=1, le=3)] = None,
    status: ReviewStatus | None = None,
) -> list[ProblemSummary]:
    if status is ReviewStatus.RETIRED:
        return []
    problems = _registry(request).served()
    return [
        _summary(p)
        for p in problems
        if (course is None or p.course is course)
        and (topic is None or p.topic == topic)
        and (kind is None or p.kind == kind)
        and (tag is None or tag in p.tags)
        and (difficulty is None or p.difficulty == difficulty)
        and (status is None or p.review.status is status)
    ]


@router.get("/problems/{problem_id}", response_model=ProblemDetail, tags=["problems"])
def get_problem(request: Request, problem_id: str) -> ProblemDetail:
    p = _problem_or_404(request, problem_id)
    book = _registry(request).references[p.reference.book]
    handler = get_handler(p.kind)
    has_answer = handler.has_answer(p, handler.params(p))
    return ProblemDetail(
        **_summary(p).model_dump(),
        answer_format=p.answer_format,
        syntax_help=handler.syntax_help,
        step_kinds=sorted(handler.step_kinds),
        has_answer=has_answer,
        reference=CitationOut(
            book_id=book.id,
            title=book.title,
            authors=book.authors,
            edition=book.edition,
            section=p.reference.section,
            note=p.reference.note,
            url=book.url,
            license=book.license,
            license_url=book.license_url,
        ),
        review=ReviewOut(status=p.review.status, reviewed_on=p.review.reviewed_on),
        hint_count=len(p.hints),
    )


@router.get("/problems/{problem_id}/solution", response_model=SolutionOut, tags=["problems"])
def get_solution(request: Request, problem_id: str) -> SolutionOut:
    p = _problem_or_404(request, problem_id)
    return SolutionOut(problem_id=p.id, answer=p.answer, solution=p.solution)


def _weights(raw: str | None) -> dict[str, float]:
    out: dict[str, float] = {}
    for part in (raw or "").split(","):
        topic, _, value = part.partition(":")
        try:
            if topic.strip():
                out[topic.strip()] = float(value)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Bad weight {part!r}.") from None
    return out


TEST_LABELS = {"midterm": "Practice midterm", "final": "Practice final", "quiz": "Quick quiz"}


@router.get("/practice-tests", response_model=PracticeTestOut, tags=["practice tests"])
def practice_test(
    request: Request,
    course: Course,
    kind: Annotated[str, Query(pattern="^(midterm|final|quiz)$")] = "midterm",
    seed: Annotated[int, Query(ge=0, le=2**31 - 1)] = 1,
    topics: Annotated[str | None, Query(max_length=500)] = None,
    length: Annotated[int | None, Query(ge=1, le=MAX_LENGTH)] = None,
    style: Annotated[str, Query(pattern="^(written|mixed|choice)$")] = "written",
    variants: bool = False,
    weights: Annotated[str | None, Query(max_length=1000)] = None,
    prefer: Annotated[str | None, Query(max_length=4000)] = None,
) -> PracticeTestOut:
    """A midterm, final or quiz assembled from existing problems; same inputs, same test.

    ``style`` mixes in multiple-choice questions, ``weights`` (``topic:1.5,...``) and
    ``prefer`` (problem ids due for review) come from the student's own results, and
    ``variants`` swaps some questions for ProofLab-made versions with new numbers.
    """
    registry = _registry(request)
    chosen = [t for t in (topics or "").split(",") if t.strip()] or None
    due = [i.strip() for i in (prefer or "").split(",") if i.strip()][:200]
    try:
        test = build_practice_test(
            registry,
            course,
            kind,  # type: ignore[arg-type]
            seed=seed,
            topics=chosen,
            length=length,
            style=style,  # type: ignore[arg-type]
            weights=_weights(weights),
            prefer=due,
            variants=variants,
        )
    except PracticeTestError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    run = _runner(request)
    siblings = [p for p in registry.served() if p.course is course]
    questions: list[QuestionOut] = []
    for i, q in enumerate(test.questions):
        choice = None
        if q.format == "choice":
            made = build_question(q.problem, seed + i, run, siblings)
            choice = _choice_out(made) if made is not None else None
        questions.append(
            QuestionOut(
                problem=_summary(q.problem),
                format="choice" if choice is not None else "written",
                choice=choice,
            )
        )
    return PracticeTestOut(
        id=test.id,
        course=test.course,
        kind=test.kind,
        title=f"{COURSE_TITLES[course]}: {TEST_LABELS[kind]}",
        seed=test.seed,
        topics=test.topics,
        style=style,
        variants=variants,
        suggested_minutes=test.suggested_minutes,
        minutes_rule=MINUTES_RULE,
        problems=[_summary(p) for p in test.problems],
        questions=questions,
    )


@router.post("/quiz/answer", response_model=ChoiceAnswerOut, tags=["practice tests"])
def answer_choice(request: Request, body: ChoiceAnswerIn) -> ChoiceAnswerOut:
    """Grade a multiple-choice answer by rebuilding the question from its problem and seed."""
    registry = _registry(request)
    problem = _problem_or_404(request, body.problem_id)
    siblings = [p for p in registry.served() if p.course is problem.course]
    question = build_question(problem, body.seed, _runner(request), siblings, body.format)  # type: ignore[arg-type]
    if question is None:
        raise HTTPException(status_code=404, detail="That question can't be rebuilt any more.")
    correct, explanation = grade(question, body.choice)
    return ChoiceAnswerOut(
        problem_id=problem.id,
        correct=correct,
        choice=body.choice,
        correct_choice=question.correct,
        explanation=explanation,
        solution=problem.solution,
    )


@router.get("/cards", response_model=list[DeckCardOut], tags=["flashcards"])
def cards(
    request: Request,
    course: Course,
    topics: Annotated[str | None, Query(max_length=500)] = None,
    parts: Annotated[str, Query(pattern="^(concepts|problems)(,(concepts|problems))?$")] = (
        "concepts,problems"
    ),
) -> list[DeckCardOut]:
    """A course's flashcards: concept cards (cited) and one card per problem (SPEC §15)."""
    registry = _registry(request)
    chosen = [t for t in (topics or "").split(",") if t.strip()] or None
    deck = build_deck(
        registry.cards,
        registry.served(),
        {b.id: b.title for b in registry.references.values()},
        course,
        topics=chosen,
        parts=parts.split(","),  # type: ignore[arg-type]
        topic_order=registry.topics.get(course.value, []),
    )
    return [DeckCardOut(**c.model_dump()) for c in deck]


@router.post("/cards/from-notes", response_model=NotesOut, tags=["flashcards"])
def cards_from_notes(body: NotesIn) -> NotesOut:
    """Turn the student's notes into draft flashcards with written rules (SPEC §15.2)."""
    found = extract_cards(body.text)
    return NotesOut(
        cards=[
            NoteCardOut(
                front=c.front,
                back=c.back,
                type=c.type,
                rule=c.rule,
                rule_label=RULES.get(c.rule, c.rule),
                line=c.line,
            )
            for c in found
        ],
        lines=body.text.count("\n") + 1 if body.text else 0,
    )


@router.post("/check", response_model=Verdict, tags=["check"])
def check_work(request: Request, body: CheckRequest) -> Verdict:
    problem = _problem_or_404(request, body.problem_id)
    settings = request.app.state.settings
    submission = Submission(steps=body.steps, answer=body.answer)
    slots = request.app.state.check_slots
    if not slots.acquire(timeout=settings.busy_wait):
        raise HTTPException(status_code=503, detail=hints.message("BUSY"))
    try:
        if settings.isolate:
            return check_isolated(
                problem,
                submission,
                hints_revealed=body.hints_revealed,
                timeout=settings.check_timeout,
            )
        return check(problem, submission, hints_revealed=body.hints_revealed)
    finally:
        slots.release()


def _store(request: Request) -> Store:
    return open_store(request.app.state.db_path or default_path())


@router.get("/store", tags=["progress"])
def store_snapshot(request: Request) -> dict:
    """Everything saved about the student's progress (SPEC §17), for a browser to merge."""
    return _store(request).snapshot()


@router.post("/store", tags=["progress"])
def store_sync(request: Request, body: SyncIn) -> dict:
    """Apply a batch of changes from a browser. Safe to resend: every change is idempotent."""
    try:
        applied = _store(request).apply(body.ops)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"applied": applied, "received": len(body.ops)}


@router.get("/read", response_model=ReaderCapabilities, tags=["reader"])
def reader_capabilities() -> ReaderCapabilities:
    """What this server can read: photos and PDFs need macOS (Apple Vision)."""
    return ReaderCapabilities(**capabilities())


@router.post("/read", response_model=ReadOut, tags=["reader"])
async def read_upload(request: Request) -> ReadOut:
    """Transcribe the raw request body (a photo, PDF, document or text file) into lines.

    Send the file bytes as the body. Optional ``X-Filename`` header helps with documents.
    The text is for the student to review; nothing here decides right or wrong.
    """
    length = int(request.headers.get("content-length") or 0)
    if length > MAX_BYTES:
        raise HTTPException(status_code=413, detail="That file is too big (the limit is 15 MB).")
    data = await request.body()
    try:
        result = await run_in_threadpool(
            read_document,
            data,
            request.headers.get("x-filename"),
            request.headers.get("content-type"),
        )
    except ReaderError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc
    return ReadOut(
        kind=result.kind,
        engine=result.engine,
        pages=result.pages,
        lines=[
            ReadLineOut(text=ln.text, confidence=ln.confidence, page=ln.page) for ln in result.lines
        ],
        text=result.text,
    )
