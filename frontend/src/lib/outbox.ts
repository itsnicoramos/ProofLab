// Changes waiting to reach ProofLab's progress database (SPEC §17). Every change is written to
// this browser first (so the page stays instant and works offline), then queued here; the sync
// agent (lib/sync.ts) sends the queue to the SQLite store on the Mac. The queue itself lives in
// localStorage, so nothing is lost if the tab closes before it's sent.

const KEY = "prooflab:v1:outbox";
const MAX = 5000;
export const OUTBOX_EVENT = "prooflab:outbox";

export type StoreOp =
  | {
      op: "review";
      uid: string;
      item: string;
      kind: "card" | "problem" | "note";
      course: string;
      topic: string;
      difficulty: number | null;
      grade: number;
      at: number;
    }
  | { op: "reset_reviews"; at: number }
  | { op: "progress"; problem_id: string; status: string; at: number }
  | {
      op: "deck";
      id: string;
      name: string;
      created_at: number;
      cards: { id: string; front: string; back: string }[];
      updated_at: number;
    }
  | { op: "deck_delete"; id: string; updated_at: number }
  | { op: "test"; id: string; record: unknown; updated_at: number }
  | { op: "test_delete"; id: string; updated_at: number };

export function readOutbox(): StoreOp[] {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(KEY) ?? "[]") as unknown;
    return Array.isArray(parsed) ? (parsed as StoreOp[]) : [];
  } catch {
    return [];
  }
}

function writeOutbox(ops: StoreOp[]): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(ops.slice(-MAX)));
  } catch {
    // Storage full or blocked: the change is still saved locally, it just won't sync.
  }
}

/** A key for changes where only the latest matters (one deck, one test, one problem). */
function slot(op: StoreOp): string | null {
  switch (op.op) {
    case "deck":
    case "deck_delete":
      return `deck:${op.id}`;
    case "test":
    case "test_delete":
      return `test:${op.id}`;
    case "progress":
      return null; // the store keeps the best verdict, so every one is worth sending
    default:
      return null;
  }
}

/** Queue changes for the database and nudge the sync agent. */
export function enqueue(...ops: StoreOp[]): void {
  if (typeof window === "undefined" || ops.length === 0) return;
  let queue = readOutbox();
  for (const op of ops) {
    const key = slot(op);
    if (key) queue = queue.filter((q) => slot(q) !== key);
    if (op.op === "reset_reviews") queue = queue.filter((q) => q.op !== "review");
    queue.push(op);
  }
  writeOutbox(queue);
  window.dispatchEvent(new Event(OUTBOX_EVENT));
}

/** Remove the first `n` changes once the database has confirmed them. */
export function dropSent(n: number): void {
  writeOutbox(readOutbox().slice(n));
}

/** Ids with a change still waiting, so a pull doesn't overwrite them with older copies. */
export function pendingSlots(): Set<string> {
  return new Set(readOutbox().flatMap((op) => slot(op) ?? []));
}
