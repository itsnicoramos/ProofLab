// Keeps this browser's copy of the student's progress in step with the SQLite progress
// database on the Mac (SPEC §17). Push first (the outbox), then pull and merge:
//
// - reviews: union by uid (an append-only log, so devices never conflict);
// - best verdicts: the better one wins;
// - notes decks and test records: the newer copy wins; a deletion on any device removes the
//   copy everywhere; anything still waiting in the outbox is left alone.
//
// Nothing here decides anything about the math; it only moves the student's own records.

import { useSyncExternalStore } from "react";

import { deckOp, type NoteDeck, readAllDecks, writeDecks } from "./decks";
import { readReviews, type Review, writeReviews } from "./learn";
import { dropSent, enqueue, pendingSlots, readOutbox, type StoreOp } from "./outbox";
import {
  mergeProgress,
  readAllProgress,
  readAllTestRecords,
  recordTime,
  saveTestRecord,
  type TestRecord,
} from "./storage";

const FIRST_SYNC = "prooflab:v1:synced";
const BATCH = 500;

export type SyncStatus = "idle" | "syncing" | "saved" | "offline";

interface Snapshot {
  reviews: Review[];
  progress: Record<string, string>;
  decks: {
    id: string;
    name: string;
    created_at: number;
    cards: { id: string; front: string; back: string }[];
    updated_at: number;
    deleted: boolean;
  }[];
  tests: { id: string; record: TestRecord | null; updated_at: number; deleted: boolean }[];
}

// ---------------------------------------------------------------- status (for the UI)

let status: SyncStatus = "idle";
let lastSaved: number | null = null;
const listeners = new Set<() => void>();

function setStatus(next: SyncStatus): void {
  status = next;
  if (next === "saved") lastSaved = Date.now();
  for (const l of listeners) l();
}

/** Where this browser's progress stands: saved in the database, syncing, or offline. */
export function useSyncStatus(): { status: SyncStatus; lastSaved: number | null } {
  const s = useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => `${status}|${lastSaved ?? ""}`,
    () => "idle|",
  );
  const [st, saved] = s.split("|");
  return { status: st as SyncStatus, lastSaved: saved ? Number(saved) : null };
}

// ---------------------------------------------------------------- push

/** First run on this browser: send everything it already had before the database existed. */
function seedOnce(): void {
  try {
    if (window.localStorage.getItem(FIRST_SYNC)) return;
  } catch {
    return;
  }
  const ops: StoreOp[] = [
    ...readReviews().map((r) => ({ op: "review" as const, ...r })),
    ...Object.entries(readAllProgress()).map(([problem_id, s]) => ({
      op: "progress" as const,
      problem_id,
      status: s,
      at: Date.now(),
    })),
    ...readAllDecks().map((d) => deckOp(d)),
    ...Object.entries(readAllTestRecords()).map(([id, record]) => ({
      op: "test" as const,
      id,
      record,
      updated_at: recordTime(record),
    })),
  ];
  enqueue(...ops);
  try {
    window.localStorage.setItem(FIRST_SYNC, String(Date.now()));
  } catch {
    // fine: it would only resend idempotent changes
  }
}

async function push(): Promise<boolean> {
  for (let guard = 0; guard < 50; guard++) {
    const batch = readOutbox().slice(0, BATCH);
    if (batch.length === 0) return true;
    const res = await fetch("/api/store", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ ops: batch }),
    });
    if (res.status === 422) {
      dropSent(batch.length); // malformed changes would block the queue forever
      continue;
    }
    if (!res.ok) return false;
    dropSent(batch.length);
  }
  return true;
}

// ---------------------------------------------------------------- pull and merge

function mergeReviews(server: Review[]): void {
  const local = readReviews();
  const seen = new Set(local.map((r) => r.uid));
  const extra = server.filter((r) => !seen.has(r.uid));
  // The database is the full log once our outbox is empty, so it also carries resets.
  const serverUids = new Set(server.map((r) => r.uid));
  const pending = new Set(readOutbox().flatMap((op) => (op.op === "review" ? [op.uid] : [])));
  const kept = local.filter((r) => serverUids.has(r.uid) || pending.has(r.uid));
  if (extra.length || kept.length !== local.length) writeReviews([...kept, ...extra]);
}

function mergeDecks(server: Snapshot["decks"]): void {
  const pending = pendingSlots();
  const local = new Map(readAllDecks().map((d) => [d.id, d]));
  let changed = false;
  for (const d of server) {
    if (pending.has(`deck:${d.id}`)) continue;
    const mine = local.get(d.id);
    if (d.deleted) {
      if (mine) {
        local.delete(d.id);
        changed = true;
      }
      continue;
    }
    if (!mine || (mine.updatedAt ?? mine.createdAt) < d.updated_at) {
      const deck: NoteDeck = {
        id: d.id,
        name: d.name,
        createdAt: d.created_at,
        updatedAt: d.updated_at,
        cards: d.cards,
      };
      local.set(d.id, deck);
      changed = true;
    }
  }
  if (changed) writeDecks([...local.values()]);
}

function mergeTests(server: Snapshot["tests"]): void {
  const pending = pendingSlots();
  const local = readAllTestRecords();
  for (const t of server) {
    if (pending.has(`test:${t.id}`)) continue;
    const mine = local[t.id];
    if (t.deleted) {
      if (mine) saveTestRecord(t.id, null, { sync: false });
      continue;
    }
    if (t.record && (!mine || recordTime(mine) < t.updated_at)) {
      saveTestRecord(t.id, { ...t.record, updatedAt: t.updated_at }, { sync: false });
    }
  }
}

async function pull(): Promise<boolean> {
  const res = await fetch("/api/store", { headers: { accept: "application/json" } });
  if (!res.ok) return false;
  const snap = (await res.json()) as Snapshot;
  mergeReviews(snap.reviews ?? []);
  mergeProgress((snap.progress ?? {}) as Parameters<typeof mergeProgress>[0]);
  mergeDecks(snap.decks ?? []);
  mergeTests(snap.tests ?? []);
  return true;
}

// ---------------------------------------------------------------- the loop

let running: Promise<void> | null = null;
let again = false;

/** Push queued changes, then pull everything; safe to call as often as you like. */
export function syncNow(): Promise<void> {
  if (running) {
    again = true;
    return running;
  }
  running = (async () => {
    setStatus("syncing");
    try {
      seedOnce();
      const pushed = await push();
      // Only merge once our own changes are in: then the database is the full picture.
      const pulled = pushed ? await pull() : false;
      setStatus(pushed && pulled ? "saved" : "offline");
    } catch {
      setStatus("offline");
    } finally {
      running = null;
      if (again) {
        again = false;
        void syncNow();
      }
    }
  })();
  return running;
}
