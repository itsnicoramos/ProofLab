// Keeps this browser's copy of the student's progress in step with the SQLite progress
// database on the Mac (SPEC §17). Push first (the outbox), then pull and merge:
//
// - reviews: union by uid (an append-only log, so devices never conflict); a recorded reset
//   removes the reviews made before it;
// - best verdicts: the better one wins;
// - notes decks and test records: the newer copy wins; a deletion on any device removes the
//   copy everywhere; anything still waiting in the outbox is left alone.
//
// Nothing the database merely lacks is ever deleted here: a new, replaced or empty database
// file just gets this browser's copy sent again. If the server keeps no database at all (the
// Vercel deployment), progress simply stays in each browser.
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

export type SyncStatus = "idle" | "syncing" | "saved" | "offline" | "local";

interface Snapshot {
  reviews: Review[];
  reviews_reset_at: number | null;
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

/** The server keeps no progress database (404 from /store): nothing to sync with. */
class NoDatabase extends Error {}

async function push(): Promise<boolean> {
  for (let guard = 0; guard < 50; guard++) {
    const batch = readOutbox().slice(0, BATCH);
    if (batch.length === 0) return true;
    const res = await fetch("/api/store", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ ops: batch }),
    });
    if (res.status === 404) throw new NoDatabase();
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

function mergeReviews(server: Review[], resetAt: number | null): void {
  const local = readReviews();
  const seen = new Set(local.map((r) => r.uid));
  const extra = server.filter((r) => !seen.has(r.uid));
  // A recorded reset removes the reviews made before it, on every device.
  const kept = resetAt === null ? local : local.filter((r) => r.at > resetAt);
  // Anything else the database lacks (a new or replaced file) is sent again, never dropped.
  const serverUids = new Set(server.map((r) => r.uid));
  const pending = new Set(readOutbox().flatMap((op) => (op.op === "review" ? [op.uid] : [])));
  const missing = kept.filter((r) => !serverUids.has(r.uid) && !pending.has(r.uid));
  if (missing.length) enqueue(...missing.map((r) => ({ op: "review" as const, ...r })));
  if (extra.length || kept.length !== local.length) writeReviews([...kept, ...extra]);
}

function mergeAllProgress(server: Record<string, string>): void {
  mergeProgress(server as Parameters<typeof mergeProgress>[0]);
  const rank: Record<string, number> = { invalid: 0, incorrect: 1, partial: 2, correct: 3 };
  const better = Object.entries(readAllProgress()).filter(
    ([id, s]) => !(id in server) || rank[s] > (rank[server[id]] ?? -1),
  );
  if (better.length) {
    enqueue(
      ...better.map(([problem_id, s]) => ({
        op: "progress" as const,
        problem_id,
        status: s,
        at: Date.now(),
      })),
    );
  }
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
  const known = new Set(server.map((d) => d.id));
  const unsent = [...local.values()].filter((d) => !known.has(d.id) && !pending.has(`deck:${d.id}`));
  if (unsent.length) enqueue(...unsent.map((d) => deckOp(d)));
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
  const known = new Set(server.map((t) => t.id));
  const unsent = Object.entries(local).filter(
    ([id]) => !known.has(id) && !pending.has(`test:${id}`),
  );
  if (unsent.length) {
    enqueue(
      ...unsent.map(([id, record]) => ({
        op: "test" as const,
        id,
        record,
        updated_at: recordTime(record),
      })),
    );
  }
}

async function pull(): Promise<boolean> {
  const res = await fetch("/api/store", { headers: { accept: "application/json" } });
  if (res.status === 404) throw new NoDatabase();
  if (!res.ok) return false;
  const snap = (await res.json()) as Snapshot;
  mergeReviews(snap.reviews ?? [], snap.reviews_reset_at ?? null);
  mergeAllProgress(snap.progress ?? {});
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
    } catch (error) {
      if (error instanceof NoDatabase) {
        // Nothing will ever take the queue on this server; progress stays in this browser.
        dropSent(readOutbox().length);
        setStatus("local");
      } else {
        setStatus("offline");
      }
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
