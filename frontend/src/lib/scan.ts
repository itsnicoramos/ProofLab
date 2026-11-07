// Client helpers for scanning work: shrink photos before upload, send files to the reader, and
// turn the lines it reads into steps. Reading is transcription only: the student edits the text
// before anything is checked, and verdicts still come from the checkers.

import type { StepInput } from "./types";

export interface ReadResponse {
  kind: "image" | "pdf" | "document" | "text";
  engine: string;
  pages: number;
  lines: { text: string; confidence: number | null; page: number }[];
  text: string;
}

export const ACCEPT =
  "image/*,application/pdf,.pdf,.docx,.doc,.rtf,.odt,.html,.htm,.txt,.md,.tex,.csv";

const MAX_SIDE = 2200;

/** Re-encode a photo at a sensible size (and the right way up). Falls back to the original. */
export async function prepareImage(file: Blob): Promise<Blob> {
  if (!file.type.startsWith("image/") || typeof createImageBitmap === "undefined") return file;
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch {
    return file; // e.g. HEIC in Chrome: the reader on the Mac decodes it natively
  }
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  if (scale === 1 && file.size < 3 * 1024 * 1024) {
    bitmap.close();
    return file;
  }
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, "image/jpeg", 0.9),
  );
  return blob ?? file;
}

export async function readDocument(file: Blob, filename: string): Promise<ReadResponse> {
  const body = await prepareImage(file);
  let res: Response;
  try {
    res = await fetch("/api/read", {
      method: "POST",
      body,
      headers: {
        "content-type": body.type || "application/octet-stream",
        "x-filename": encodeURIComponent(filename).slice(0, 200),
      },
    });
  } catch {
    throw new Error("Couldn't reach ProofLab. Check that the site is still running.");
  }
  const data = (await res.json().catch(() => null)) as (ReadResponse & { detail?: string }) | null;
  if (!res.ok || !data) {
    throw new Error(data?.detail ?? "ProofLab couldn't read that file.");
  }
  return data;
}

// ---------------------------------------------------------------- tidying what was read

const SUPERSCRIPTS: Record<string, string> = {
  "⁰": "0",
  "¹": "1",
  "²": "2",
  "³": "3",
  "⁴": "4",
  "⁵": "5",
  "⁶": "6",
  "⁷": "7",
  "⁸": "8",
  "⁹": "9",
};

/** Kinds whose variables are lowercase, so a stray capital (K for k) is a misread. */
const LOWERCASE_KINDS = new Set([
  "parity_proof",
  "divisibility_proof",
  "impossibility_proof",
  "induction",
  "counterexample",
  "existence",
  "count",
]);

/** Kinds where × is the Cartesian product, not multiplication. */
const KEEP_TIMES = new Set(["set_identity", "finite_set"]);

/** Cyrillic letters the text recognizer sometimes returns for identical-looking Latin ones. */
const LOOKALIKES: Record<string, string> = {
  а: "a",
  в: "b",
  е: "e",
  к: "k",
  м: "m",
  н: "h",
  о: "o",
  р: "p",
  с: "c",
  т: "t",
  у: "y",
  х: "x",
  А: "A",
  В: "B",
  Е: "E",
  К: "K",
  М: "M",
  Н: "H",
  О: "O",
  Р: "P",
  С: "C",
  Т: "T",
  Х: "X",
};

/** Kinds where ~ means "not" (logic and set statements), so it must stay as typed. */
const TILDE_IS_NOT = new Set(["truth_table", "logical_equivalence", "set_identity"]);

/**
 * Exponents are the hardest part of handwriting to read: the caret comes back as "~", merges
 * into the letter as an accent ("á 2"), or vanishes ("a 2"). Put it back where the shape is
 * unambiguous: a power right after a letter or a closing bracket.
 */
function restoreCarets(line: string): string {
  return line
    .normalize("NFD")
    .replace(/([A-Za-z])[\u0300-\u036f]+\s*(?=\d)/g, "$1^") // á 2 → a^2
    .replace(/[\u0300-\u036f]/g, "") // other stray accents: drop them
    .replace(/([A-Za-z0-9)])\s*~\s*(?=[\w(])/g, "$1^") // 4a~2 → 4a^2
    .replace(/((?<![A-Za-z])[A-Za-z]|\)) (\d)(?![\d.])/g, "$1^$2") // a 2 → a^2 (not "Assume 1")
    .normalize("NFC");
}

function tidy(line: string, problemKind: string): string {
  let out = (TILDE_IS_NOT.has(problemKind) ? line : restoreCarets(line))
    .replace(/[а-яА-Я]/g, (c) => LOOKALIKES[c] ?? c)
    .replace(/\s*\^\s*/g, "^")
    .replace(/[“”]/g, '"')
    .replace(/[‘’]/g, "'")
    .replace(/[−–—]/g, "-")
    .replace(/÷/g, "/")
    .replace(/√/g, "sqrt")
    .replace(/[⁰¹²³⁴⁵⁶⁷⁸⁹]+/g, (run) => "^" + [...run].map((c) => SUPERSCRIPTS[c]).join(""))
    .replace(/^(Let|Case|So|Thus|Then|Hence|Assume|Suppose)(?=[a-z0-9])/, "$1 ")
    .replace(/\s+/g, " ")
    .trim();
  if (!KEEP_TIMES.has(problemKind)) out = out.replace(/[×·•]/g, "*");
  return out;
}

/**
 * Tidy what the reader returned: plain-keyboard symbols (² → ^2, − → -, × → *), a space after
 * "Let"/"Case", and, where variables are lowercase, capitals that are misread lowercase letters
 * used elsewhere on the page (K → k when k appears).
 */
export function cleanLines(lines: string[], problemKind: string): string[] {
  const tidied = lines.map((l) => tidy(l, problemKind)).filter(Boolean);
  if (!LOWERCASE_KINDS.has(problemKind)) return tidied;
  const known = new Set(tidied.join(" ").match(/(?<![A-Za-z])[a-z](?![A-Za-z])/g) ?? []);
  const fix = (c: string) => (known.has(c.toLowerCase()) ? c.toLowerCase() : c);
  return tidied.map((l) =>
    l.replace(/(?<![A-Za-z])([A-Z])(?![A-Za-z])/g, (_m, c: string) => fix(c)),
  );
}

const WORDY =
  /\b(?!(?:sin|cos|tan|sec|csc|cot|log|ln|sqrt|binom|exp|and|or|not|in)\b)[A-Za-z]{2,}\b/g;

/** One step per line, guessing the step kind from words like "Let", "Case", "Base case". */
/** Kinds whose plain steps are a chain of expressions, each equal to the one before. */
const CHAIN_KINDS = new Set([
  "parity_proof",
  "divisibility_proof",
  "impossibility_proof",
  "induction",
]);

export function linesToSteps(
  lines: string[],
  stepKinds: string[],
  fallback: string,
  problemKind = "",
): StepInput[] {
  const allowed = new Set(stepKinds);
  const steps: StepInput[] = [];
  for (const raw of lines) {
    let content = raw.trim();
    if (!content) continue;
    let kind = fallback;
    const rules: [RegExp, string][] = [
      [/^base(\s+case)?\s*[:.)-]?\s*/i, "base"],
      [/^(assume|suppose|inductive hypothesis)\s*[:,]?\s*(that\s+)?/i, "assume"],
      [/^(let|suppose)\s+/i, "let"],
      [/^case\s*\d*\s*[:.)-]?\s*/i, "case"],
      [/^witness\s*[:=]?\s*/i, "witness"],
      [/^form\s*[:=]?\s*/i, "form"],
      [/^(note|nb)\s*[:.-]\s*/i, "note"],
    ];
    for (const [pattern, target] of rules) {
      if (
        allowed.has(target) &&
        pattern.test(content) &&
        (target === "note" || /[=\d]/.test(content))
      ) {
        content = content.replace(pattern, "");
        kind = target;
        break;
      }
    }
    if (kind === fallback) {
      content = content.replace(/^=\s*/, ""); // a continued chain: "= 2(2k^2 + 2k) + 1"
      const words = content.match(WORDY) ?? [];
      if (allowed.has("note") && words.length >= 2 && !/[=<>+*/]/.test(content)) kind = "note";
    }
    if (kind === "expr" && CHAIN_KINDS.has(problemKind) && /(?<![<>!=])=(?!=)/.test(content)) {
      // Handwritten chains are equations ("x^2 = 4a^2"); the checker wants each expression.
      content =
        content
          .split(/(?<![<>!=])=(?!=)/)
          .pop()
          ?.trim() || content;
    }
    steps.push({ kind, content: content.slice(0, 500) });
  }
  return steps.slice(0, 40);
}
