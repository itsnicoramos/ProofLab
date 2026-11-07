// Flashcard decks made from the student's own notes (SPEC §15.2). Kept in this browser and
// queued for the SQLite progress database (SPEC §17), so every device sees the same decks.

import { useMemo, useSyncExternalStore } from "react";

import { enqueue } from "./outbox";
import { emit, readRaw, subscribe, writeRaw } from "./storage";

const KEY = "prooflab:v1:decks";

export interface NoteCard {
  id: string;
  front: string;
  back: string;
}

export interface NoteDeck {
  id: string;
  name: string;
  createdAt: number;
  /** Last change (ms), so the newest copy wins when devices sync. */
  updatedAt?: number;
  cards: NoteCard[];
}

function readRawDecks(): string {
  return readRaw(KEY) ?? "[]";
}

function parse(raw: string): NoteDeck[] {
  try {
    const data = JSON.parse(raw) as unknown;
    return Array.isArray(data)
      ? (data as NoteDeck[]).filter((d) => d && typeof d.id === "string" && Array.isArray(d.cards))
      : [];
  } catch {
    return [];
  }
}

/** Every notes deck in this browser, newest first. Empty during server rendering. */
export function useDecks(): NoteDeck[] {
  const raw = useSyncExternalStore(subscribe, readRawDecks, () => "[]");
  return useMemo(() => parse(raw).sort((a, b) => b.createdAt - a.createdAt), [raw]);
}

export function getDeck(id: string): NoteDeck | null {
  return parse(readRawDecks()).find((d) => d.id === id) ?? null;
}

const newId = () => Math.random().toString(36).slice(2, 10);

export const deckOp = (d: NoteDeck) =>
  ({
    op: "deck",
    id: d.id,
    name: d.name,
    created_at: d.createdAt,
    cards: d.cards,
    updated_at: d.updatedAt ?? d.createdAt,
  }) as const;

export function saveDeck(name: string, cards: { front: string; back: string }[]): NoteDeck {
  const now = Date.now();
  const deck: NoteDeck = {
    id: newId(),
    name: name.trim().slice(0, 80) || "My notes",
    createdAt: now,
    updatedAt: now,
    cards: cards
      .map((c) => ({ id: newId(), front: c.front.trim(), back: c.back.trim() }))
      .filter((c) => c.front && c.back),
  };
  writeRaw(KEY, JSON.stringify([...parse(readRawDecks()), deck]));
  emit();
  enqueue(deckOp(deck));
  return deck;
}

export function deleteDeck(id: string): void {
  writeRaw(KEY, JSON.stringify(parse(readRawDecks()).filter((d) => d.id !== id)));
  emit();
  enqueue({ op: "deck_delete", id, updated_at: Date.now() });
}

/** Every deck in this browser (for the sync agent). */
export function readAllDecks(): NoteDeck[] {
  return parse(readRawDecks());
}

/** Replace the local decks with a merged list (the sync agent). */
export function writeDecks(decks: NoteDeck[]): void {
  writeRaw(KEY, JSON.stringify(decks));
  emit();
}

/** The id a notes card uses in the study model. */
export const noteItemId = (deckId: string, cardId: string) => `note:${deckId}:${cardId}`;
