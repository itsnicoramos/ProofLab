// Ranking for the navbar search. Plain substring matching over a small index (a few hundred
// entries), so it runs on every keystroke without a library.

import type { SearchEntry } from "./actions";

const TYPE_RANK: Record<SearchEntry["type"], number> = { topic: 0, test: 1, page: 2, problem: 3 };

export const TYPE_LABEL: Record<SearchEntry["type"], string> = {
  topic: "Topic",
  test: "Test",
  page: "Page",
  problem: "Problem",
};

/** Lowercase, accents and symbols removed: "Ex 1.4 #8 · 𝒫({1, 2})" becomes "ex 1 4 8 1 2". */
export function normalize(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

/**
 * Every word of the query must appear somewhere in the entry. Topics rank first (the search is
 * mainly for finding a topic), then tests, pages and problems; inside a type, a match at the
 * start of the label beats one in the middle, which beats a match only in the details.
 */
export function search(entries: SearchEntry[], query: string, limit = 12): SearchEntry[] {
  const q = normalize(query);
  if (!q) return entries.filter((e) => e.type === "topic" && !e.soon).slice(0, 8);
  const words = q.split(" ");
  const scored: { entry: SearchEntry; score: number; order: number }[] = [];
  entries.forEach((entry, order) => {
    const label = normalize(entry.label);
    const haystack = `${label} ${normalize(entry.detail)} ${normalize(entry.keywords)}`;
    if (!words.every((w) => haystack.includes(w))) return;
    let score = TYPE_RANK[entry.type] * 10 + (entry.soon ? 5 : 0);
    if (label.startsWith(q)) score -= 8;
    else if (label.includes(q)) score -= 5;
    else if (words.every((w) => label.includes(w))) score -= 3;
    score -= words.filter((w) => ` ${label}`.includes(` ${w}`)).length * 0.5;
    scored.push({ entry, score, order });
  });
  scored.sort((a, b) => a.score - b.score || a.order - b.order);
  return scored.slice(0, limit).map((s) => s.entry);
}
