// One place that turns test settings into a test URL, so the builder, "New test, same
// settings" and the test page agree (SPEC.md §13).

import { focusFor, type LearnState } from "./learn";
import { DEFAULT_LENGTH } from "./testDefaults";
import type { TestKind, TestStyle } from "./types";

export { DEFAULT_LENGTH, DEFAULT_STYLE } from "./testDefaults";
const MAX_SEED = 2 ** 31 - 1;

export interface TestSettings {
  course: string;
  kind: TestKind;
  /** Chapters, or null for the kind's usual chapters. */
  topics: string[] | null;
  length: number | null;
  style: TestStyle;
  variants: boolean;
  focus: boolean;
}

export const randomSeed = () => (crypto.getRandomValues(new Uint32Array(1))[0] % MAX_SEED) + 1;

/**
 * The URL of a test. With `focus`, the student's own results (in this browser) become the
 * chapter weights and the due problems, written into the URL so the test can be rebuilt.
 */
export function testHref(
  s: TestSettings,
  seed: number,
  learn: LearnState | null,
  allTopics: string[],
): string {
  const query = new URLSearchParams({ seed: String(seed) });
  if (s.topics) query.set("topics", s.topics.join(","));
  if (s.length !== null && s.length !== DEFAULT_LENGTH[s.kind]) query.set("length", String(s.length));
  if (s.style !== "written") query.set("style", s.style);
  if (s.variants) query.set("variants", "1");
  if (s.focus && learn) {
    const { weights, prefer } = focusFor(learn, s.course, s.topics ?? allTopics);
    query.set("focus", "1");
    if (weights) query.set("weights", weights);
    if (prefer.length) query.set("prefer", prefer.join(","));
  }
  return `/tests/${s.course}/${s.kind}?${String(query).replaceAll("%2C", ",").replaceAll("%3A", ":")}`;
}
