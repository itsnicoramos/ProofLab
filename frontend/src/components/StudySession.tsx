"use client";

// A flashcard session (SPEC §15): cards due for review first, then up to 20 new ones; or a
// multiple-choice quiz over the terms. Every grade goes to the study model (lib/learn.ts),
// which schedules the card and keeps tuning itself to these answers.

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ChoiceView } from "@/components/ChoiceView";
import { Rich } from "@/components/Rich";
import { XpNote } from "@/components/XpNote";
import { loadDeck } from "@/lib/actions";
import { getDeck, noteItemId } from "@/lib/decks";
import {
  formatInterval,
  type Grade,
  GRADE_LABEL,
  type ItemMeta,
  type LearnState,
  previewIntervals,
  recordProblem,
  review,
  useLearn,
} from "@/lib/learn";
import { COURSE_SHORT, isCourseId, topicLabel } from "@/lib/labels";
import type { DeckCard } from "@/lib/types";
import { recordCard } from "@/lib/xp";

const NEW_PER_SESSION = 20;
const QUIZ_LENGTH = 10;

interface SessionCard {
  id: string;
  meta: ItemMeta;
  difficulty: number | null;
  /** "Definition · Chapter 4: Direct proof" */
  label: string;
  title: string | null;
  front: string;
  back: string[];
  citation: string | null;
  isProblem: boolean;
}

const TYPE_LABEL: Record<string, string> = {
  definition: "Definition",
  notation: "Notation",
  theorem: "Theorem",
  fact: "Fact",
  problem: "Problem",
};

function fromDeck(card: DeckCard): SessionCard {
  return {
    id: card.id,
    meta: { kind: card.type === "problem" ? "problem" : "card", course: card.course, topic: card.topic },
    difficulty: card.difficulty,
    label: `${TYPE_LABEL[card.type] ?? "Card"} · ${topicLabel(card.topic, card.course)}`,
    title: card.title,
    front: card.front,
    back: card.back,
    citation: card.citation,
    isProblem: card.type === "problem",
  };
}

function notesCards(deckId: string): SessionCard[] {
  const deck = getDeck(deckId);
  if (!deck) return [];
  return deck.cards.map((c) => ({
    id: noteItemId(deck.id, c.id),
    meta: { kind: "note", course: "notes", topic: deck.id },
    difficulty: null,
    label: deck.name,
    title: null,
    front: c.front,
    back: [c.back],
    citation: null,
    isProblem: false,
  }));
}

type Loaded = { status: "loading" } | { status: "error"; error: string } | { status: "ready"; cards: SessionCard[] };

function shuffle<T>(items: T[]): T[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

export function StudySession() {
  const search = useSearchParams();
  const learn = useLearn();
  const mode = search.get("mode") === "quiz" ? "quiz" : search.get("mode") === "due" ? "due" : "study";
  const deckId = search.get("deck");
  const course = search.get("course");
  const topics = (search.get("topics") ?? "").split(",").filter(Boolean);
  const parts = (search.get("parts") ?? "concepts,problems")
    .split(",")
    .filter((p): p is "concepts" | "problems" => p === "concepts" || p === "problems");
  const key = `${mode}|${deckId}|${course}|${topics.join(",")}|${parts.join(",")}`;
  const [loaded, setLoaded] = useState<Loaded>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    async function load(): Promise<Loaded> {
      if (deckId) {
        const cards = notesCards(deckId);
        return cards.length ? { status: "ready", cards } : { status: "error", error: "That notes deck isn't in this browser." };
      }
      if (mode === "due") {
        const now = Date.now();
        const due = Object.entries(learn.items).filter(([, it]) => it.due <= now);
        const courses = [...new Set(due.map(([, it]) => it.course).filter(isCourseId))];
        const decks = await Promise.all(courses.map((c) => loadDeck(c, [], ["concepts", "problems"])));
        const byId = new Map<string, SessionCard>();
        for (const d of decks) if (d.ok) for (const c of d.cards) byId.set(c.id, fromDeck(c));
        for (const [id, it] of due) {
          if (it.kind === "note") for (const c of notesCards(it.topic)) byId.set(c.id, c);
          void id;
        }
        const cards = due
          .sort((a, b) => a[1].due - b[1].due)
          .flatMap(([id]) => (byId.has(id) ? [byId.get(id)!] : []));
        return { status: "ready", cards };
      }
      if (!course || !isCourseId(course) || parts.length === 0) {
        return { status: "error", error: "Pick a course and some cards first." };
      }
      const res = await loadDeck(course, topics, parts);
      return res.ok ? { status: "ready", cards: res.cards.map(fromDeck) } : { status: "error", error: res.error };
    }
    load().then((l) => {
      if (!cancelled) setLoaded(l);
    });
    return () => {
      cancelled = true;
    };
    // The deck is chosen once per visit: `learn` changing as cards are graded mustn't reload it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const heading =
    deckId && loaded.status === "ready"
      ? (loaded.cards[0]?.label ?? "Your notes")
      : mode === "due"
        ? "Reviews due"
        : course && isCourseId(course)
          ? `${COURSE_SHORT[course]}${topics.length === 1 ? `: ${topicLabel(topics[0], course)}` : ""}`
          : "Flashcards";

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <Link href="/cards" className="inline-flex min-h-11 items-center text-sm text-muted hover:text-ink">
          ← Flashcards
        </Link>
        <h1 className="text-2xl sm:text-3xl">
          {mode === "quiz" ? "Quiz: " : ""}
          {heading}
        </h1>
      </header>
      {loaded.status === "loading" && <p className="text-muted">Loading cards…</p>}
      {loaded.status === "error" && <p className="text-bad">{loaded.error}</p>}
      {loaded.status === "ready" &&
        (mode === "quiz" ? <Quiz cards={loaded.cards} /> : <Review cards={loaded.cards} cram={mode === "due"} />)}
    </div>
  );
}

// ---------------------------------------------------------------- review

/** Due cards first (most overdue first), then up to 20 never-seen ones, in deck order. */
function buildQueue(cards: SessionCard[], learn: LearnState, cram: boolean): SessionCard[] {
  if (cram) return cards;
  const now = Date.now();
  const due = cards
    .filter((c) => learn.items[c.id] && learn.items[c.id].due <= now)
    .sort((a, b) => learn.items[a.id].due - learn.items[b.id].due);
  const fresh = cards.filter((c) => !learn.items[c.id]).slice(0, NEW_PER_SESSION);
  return [...due, ...fresh];
}

function Review({ cards, cram }: { cards: SessionCard[]; cram: boolean }) {
  const learn = useLearn();
  // Built once, from the schedule as it stood when the session started. (This component only
  // mounts in the browser, after the deck has loaded, so reading the clock here is safe.)
  const [queue, setQueue] = useState<SessionCard[]>(() => buildQueue(cards, learn, cram));
  const [position, setPosition] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [graded, setGraded] = useState(0);
  const [xpUids, setXpUids] = useState<string[]>([]);

  const card = queue?.[position] ?? null;
  const previews = useMemo(() => (card ? previewIntervals(learn, card.id) : []), [learn, card]);
  // The grade button just pressed disappears with the last card: move focus to the summary
  // heading so keyboard and screen-reader users land on the result (and the XP earned).
  const endHeading = useRef<HTMLHeadingElement>(null);
  const finished = !card;
  useEffect(() => {
    if (finished) endHeading.current?.focus();
  }, [finished]);

  const grade = useCallback(
    (g: Grade) => {
      if (!card) return;
      if (card.isProblem && card.difficulty) {
        recordProblem({ id: card.id, course: card.meta.course, topic: card.meta.topic, difficulty: card.difficulty }, g);
      } else {
        review(card.id, card.meta, g);
      }
      // 1 XP a card a day, whatever the grade: you grade yourself, so honesty costs nothing.
      const uid = recordCard({ item: card.id, course: card.meta.course, topic: card.meta.topic });
      setXpUids((u) => [...u, uid]);
      setGraded((n) => n + 1);
      // "Again" comes back later in this same session (a short learning step).
      if (g === 1) setQueue([...queue, card]);
      setPosition((p) => p + 1);
      setFlipped(false);
    },
    [card, queue],
  );

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLElement && ["INPUT", "TEXTAREA", "SELECT", "BUTTON", "A"].includes(e.target.tagName)) return;
      if (!card) return;
      if (!flipped && (e.key === " " || e.key === "Enter")) {
        e.preventDefault();
        setFlipped(true);
      } else if (flipped && ["1", "2", "3", "4"].includes(e.key)) {
        e.preventDefault();
        grade(Number(e.key) as Grade);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [card, flipped, grade]);

  if (!card) {
    const nothing = queue.length === 0;
    return (
      <section className="space-y-4 rounded-xl border border-line bg-surface p-5 sm:p-6">
        <h2 ref={endHeading} tabIndex={-1} className="text-xl outline-none">
          {nothing ? "All caught up" : "Session done"}
        </h2>
        <p className="text-muted">
          {nothing
            ? `None of these ${cards.length} cards are due, and you've seen them all before. They'll come back when they're due.`
            : `You graded ${graded} card${graded === 1 ? "" : "s"}. Each one is scheduled for its next review.`}
        </p>
        <XpNote uids={xpUids} breakdown={false} />
        <div className="flex flex-wrap gap-3">
          {nothing && cards.length > 0 && (
            <button
              type="button"
              onClick={() => {
                setQueue(cards);
                setPosition(0);
              }}
              className="h-11 rounded-lg border border-line px-4 text-sm font-medium hover:border-accent"
            >
              Study them anyway
            </button>
          )}
          <Link href="/cards" className="flex h-11 items-center rounded-lg bg-accent px-5 text-sm font-semibold text-accent-ink">
            Back to flashcards
          </Link>
        </div>
      </section>
    );
  }

  const left = queue.length - position;
  return (
    <section aria-live="polite" className="space-y-4">
      <p className="text-sm text-muted">
        {left} left · {graded} done
      </p>
      <article className="space-y-5 rounded-xl border border-line bg-surface p-5 sm:p-7">
        <p className="text-xs text-muted">{card.label}</p>
        {card.isProblem ? (
          <div className="space-y-3">
            {card.title && <h2 className="text-lg">{card.title}</h2>}
            <Rich text={card.front} className="text-[17px] leading-relaxed" />
          </div>
        ) : (
          <h2 className="font-serif text-2xl sm:text-3xl">
            <Rich text={card.front} inline />
          </h2>
        )}
        {flipped ? (
          <div className="space-y-2 border-t border-line pt-5 text-[16px] leading-relaxed">
            {card.back.map((line, i) => (
              <Rich key={i} text={line} />
            ))}
            {card.citation && <p className="pt-2 text-xs text-muted">{card.citation}</p>}
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setFlipped(true)}
            className="h-12 w-full rounded-lg border border-line text-sm font-medium hover:border-accent"
          >
            {card.isProblem ? "Show the worked solution" : "Show the answer"}
            <span className="ml-2 text-xs text-muted pointer-coarse:hidden">Space</span>
          </button>
        )}
      </article>
      {flipped && (
        <div className="space-y-2">
          <p className="text-sm text-muted">
            {card.isProblem ? "Could you have solved it?" : "How well did you know it?"}
          </p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {previews.map(({ grade: g, ms }) => (
              <button
                key={g}
                type="button"
                onClick={() => grade(g)}
                className={`flex min-h-14 flex-col items-center justify-center rounded-lg border px-2 text-sm transition-colors hover:border-accent ${
                  g === 3 ? "border-accent" : "border-line"
                }`}
              >
                <span className="font-medium">{GRADE_LABEL[g]}</span>
                <span className="text-xs text-muted">
                  {formatInterval(ms)}
                  <span className="pointer-coarse:hidden"> · {g}</span>
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- quiz

interface QuizQuestion {
  card: SessionCard;
  choices: { key: string; latex: null; text: string }[];
  correct: string;
}

function buildQuiz(cards: SessionCard[]): QuizQuestion[] {
  const terms = cards.filter((c) => !c.isProblem);
  const fronts = [...new Map(terms.map((c) => [c.front.toLowerCase(), c])).values()];
  if (fronts.length < 4) return [];
  return shuffle(fronts)
    .slice(0, QUIZ_LENGTH)
    .map((card) => {
      const sameTopic = fronts.filter((c) => c !== card && c.meta.topic === card.meta.topic);
      const others = fronts.filter((c) => c !== card && c.meta.topic !== card.meta.topic);
      const wrong = [...shuffle(sameTopic), ...shuffle(others)].slice(0, 3);
      const options = shuffle([card, ...wrong]);
      const keys = "abcd";
      return {
        card,
        choices: options.map((o, i) => ({ key: keys[i], latex: null, text: o.front })),
        correct: keys[options.indexOf(card)],
      };
    });
}

function Quiz({ cards }: { cards: SessionCard[] }) {
  // Browser-only (mounts after the deck loads), so the random shuffle can't mismatch the server.
  const [questions, setQuestions] = useState<QuizQuestion[]>(() => buildQuiz(cards));
  const [position, setPosition] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [score, setScore] = useState(0);
  const [xpUids, setXpUids] = useState<string[]>([]);
  const endHeading = useRef<HTMLHeadingElement>(null);
  const finished = questions.length > 0 && position >= questions.length;
  useEffect(() => {
    if (finished) endHeading.current?.focus();
  }, [finished]);

  if (questions.length === 0) {
    return <p className="text-muted">A quiz needs at least four cards with different terms.</p>;
  }
  const q = questions[position];
  if (!q) {
    return (
      <section className="space-y-4 rounded-xl border border-line bg-surface p-5 sm:p-6">
        <h2 ref={endHeading} tabIndex={-1} className="text-xl outline-none">
          Quiz done
        </h2>
        <p className="font-serif text-4xl">
          {score} <span className="text-2xl text-muted">/ {questions.length}</span>
        </p>
        <p className="text-sm text-muted">Every answer was added to your review schedule.</p>
        <XpNote uids={xpUids} breakdown={false} />
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => {
              setQuestions(buildQuiz(cards));
              setPosition(0);
              setPicked(null);
              setScore(0);
              setXpUids([]);
            }}
            className="h-11 rounded-lg bg-accent px-5 text-sm font-semibold text-accent-ink"
          >
            Quiz again
          </button>
          <Link href="/cards" className="flex h-11 items-center rounded-lg border border-line px-4 text-sm font-medium hover:border-accent">
            Back to flashcards
          </Link>
        </div>
      </section>
    );
  }

  function pick(key: string) {
    if (picked) return;
    setPicked(key);
    const right = key === q.correct;
    if (right) setScore((s) => s + 1);
    review(q.card.id, q.card.meta, right ? 3 : 1);
    // A quiz answer is checked, so only a right one earns XP (1 a card a day).
    if (right) {
      const uid = recordCard({ item: q.card.id, course: q.card.meta.course, topic: q.card.meta.topic });
      setXpUids((u) => [...u, uid]);
    }
  }

  return (
    <section className="space-y-4">
      <p className="text-sm text-muted">
        Question {position + 1} of {questions.length} · {score} right
      </p>
      <div className="space-y-4 rounded-xl border border-line bg-surface p-5 sm:p-6">
        <p className="text-xs text-muted">{q.card.label}</p>
        <Rich text={q.card.back[0]} className="text-[17px] leading-relaxed" />
        <ChoiceView
          question={{ stem: "Which term is this?", choices: q.choices }}
          label={`Question ${position + 1}`}
          picked={picked}
          onPick={picked ? undefined : pick}
          graded={picked ? { correct: q.correct, explanation: null } : null}
        />
      </div>
      {picked && (
        <button
          type="button"
          onClick={() => {
            setPosition((p) => p + 1);
            setPicked(null);
          }}
          className="h-11 rounded-lg bg-accent px-5 text-sm font-semibold text-accent-ink"
        >
          {position + 1 === questions.length ? "See your score" : "Next question"}
        </button>
      )}
    </section>
  );
}
