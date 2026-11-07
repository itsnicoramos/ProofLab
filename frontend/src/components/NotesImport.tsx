"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useRef, useState, useTransition } from "react";

import { cardsFromNotes } from "@/lib/actions";
import { saveDeck } from "@/lib/decks";
import { ACCEPT, readDocument } from "@/lib/scan";

interface Draft {
  key: number;
  front: string;
  back: string;
  found: string | null; // which rule found it (null = added by hand)
}

let nextKey = 1;

export function NotesImport() {
  const ids = useId();
  const router = useRouter();
  const fileInput = useRef<HTMLInputElement>(null);
  const photoInput = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const [name, setName] = useState("");
  const [reading, setReading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Draft[] | null>(null);
  const [finding, startFinding] = useTransition();

  async function readFile(file: File | undefined) {
    if (!file) return;
    setError(null);
    setReading(`Reading ${file.name || "your photo"}…`);
    try {
      const res = await readDocument(file, file.name || "photo.jpg");
      setText((t) => (t.trim() ? `${t.trimEnd()}\n\n${res.text}` : res.text));
      if (!name.trim() && file.name) setName(file.name.replace(/\.[a-z0-9]+$/i, ""));
    } catch (e) {
      setError(e instanceof Error ? e.message : "ProofLab couldn't read that file.");
    } finally {
      setReading(null);
    }
  }

  function find() {
    startFinding(async () => {
      const res = await cardsFromNotes(text);
      if (!res.ok) {
        setError(res.error);
        return;
      }
      setError(null);
      setDrafts(
        res.cards.map((c) => ({ key: nextKey++, front: c.front, back: c.back, found: c.rule_label })),
      );
    });
  }

  function update(key: number, change: Partial<Draft>) {
    setDrafts((d) => d?.map((x) => (x.key === key ? { ...x, ...change } : x)) ?? null);
  }

  const keep = drafts?.filter((d) => d.front.trim() && d.back.trim()) ?? [];

  function save() {
    if (!keep.length) return;
    const fallback = `Notes, ${new Date().toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
    const deck = saveDeck(name.trim() || fallback, keep);
    router.push(`/cards/study?deck=${deck.id}`);
  }

  return (
    <div className="space-y-8">
      <section className="space-y-4 rounded-xl border border-line bg-surface p-4 sm:p-6">
        <div>
          <label htmlFor={`${ids}-name`} className="mb-1.5 block text-sm font-medium">
            Deck name
          </label>
          <input
            id={`${ids}-name`}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Lecture 5: divisibility"
            maxLength={80}
            className="h-11 w-full rounded-lg border border-line bg-bg px-3 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent"
          />
        </div>
        <div>
          <label htmlFor={`${ids}-text`} className="mb-1.5 block text-sm font-medium">
            Your notes
          </label>
          <textarea
            id={`${ids}-text`}
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={10}
            placeholder={"Definition 4.1: An integer n is even if n = 2a for some integer a.\nPrime: a natural number p > 1 whose only positive divisors are 1 and p.\nQ: What is |∅|?\nA: 0"}
            className="w-full rounded-lg border border-line bg-bg px-3 py-2.5 font-mono text-sm leading-relaxed outline-none focus:border-accent focus:ring-2 focus:ring-accent"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => photoInput.current?.click()}
            className="flex h-11 items-center rounded-lg border border-line px-4 text-sm hover:border-accent"
          >
            Take a photo
          </button>
          <button
            type="button"
            onClick={() => fileInput.current?.click()}
            className="flex h-11 items-center rounded-lg border border-line px-4 text-sm hover:border-accent"
          >
            Upload a file
          </button>
          <span className="text-xs text-muted">Photos, PDFs, Word, RTF, text. Read on this Mac.</span>
          <input
            ref={photoInput}
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={(e) => {
              void readFile(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
          <input
            ref={fileInput}
            type="file"
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => {
              void readFile(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
        </div>
        <div aria-live="polite" className="space-y-2">
          {reading && <p className="text-sm text-muted">{reading}</p>}
          {error && (
            <p className="rounded-lg border border-bad/40 bg-bad-soft px-4 py-3 text-sm text-bad">{error}</p>
          )}
        </div>
        <div className="border-t border-line pt-4">
          <button
            type="button"
            onClick={find}
            disabled={!text.trim() || finding || reading !== null}
            className="h-11 rounded-lg bg-accent px-5 text-sm font-semibold text-accent-ink shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {finding ? "Looking for cards…" : "Find cards"}
          </button>
        </div>
      </section>

      {drafts !== null && (
        <section aria-labelledby={`${ids}-found`} className="space-y-4">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 id={`${ids}-found`} className="text-xl">
                {drafts.length === 0 ? "No cards found" : `${keep.length} card${keep.length === 1 ? "" : "s"}`}
              </h2>
              <p className="text-sm text-muted">
                {drafts.length === 0
                  ? "Try writing definitions as “Term: meaning”, one per line, or add cards by hand."
                  : "Fix anything the rules got wrong, delete what you don't want, then save."}
              </p>
            </div>
          </div>
          <ol className="space-y-3">
            {drafts.map((d, i) => (
              <li key={d.key} className="space-y-2 rounded-xl border border-line bg-surface p-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs text-muted">
                    Card {i + 1}
                    {d.found ? ` · found by ${d.found}` : " · added by you"}
                  </p>
                  <button
                    type="button"
                    onClick={() => setDrafts((all) => all?.filter((x) => x.key !== d.key) ?? null)}
                    aria-label={`Delete card ${i + 1}`}
                    className="flex h-11 items-center px-2 text-sm text-muted hover:text-bad"
                  >
                    Delete
                  </button>
                </div>
                <label className="block">
                  <span className="mb-1 block text-xs font-medium">Front</span>
                  <input
                    value={d.front}
                    onChange={(e) => update(d.key, { front: e.target.value })}
                    maxLength={120}
                    className="h-11 w-full rounded-lg border border-line bg-bg px-3 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent"
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-xs font-medium">Back</span>
                  <textarea
                    value={d.back}
                    onChange={(e) => update(d.key, { back: e.target.value })}
                    rows={2}
                    maxLength={400}
                    className="w-full rounded-lg border border-line bg-bg px-3 py-2 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent"
                  />
                </label>
              </li>
            ))}
          </ol>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => setDrafts((all) => [...(all ?? []), { key: nextKey++, front: "", back: "", found: null }])}
              className="h-11 rounded-lg border border-dashed border-line px-4 text-sm text-muted hover:border-accent hover:text-accent"
            >
              + Add a card
            </button>
            <button
              type="button"
              onClick={save}
              disabled={keep.length === 0}
              className="h-11 rounded-lg bg-accent px-5 text-sm font-semibold text-accent-ink shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Save {keep.length} card{keep.length === 1 ? "" : "s"} and study
            </button>
            <Link href="/cards" className="flex h-11 items-center px-1 text-sm text-muted hover:text-ink">
              Cancel
            </Link>
          </div>
        </section>
      )}
    </div>
  );
}
