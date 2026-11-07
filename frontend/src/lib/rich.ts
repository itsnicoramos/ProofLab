// A small, safe renderer for problem text: a Markdown subset plus $…$ / $$…$$ LaTeX via KaTeX.
//
// All plain text is HTML-escaped before any tags are added, and KaTeX runs with `trust: false`,
// so content can't inject markup. Supported Markdown: paragraphs, line breaks, "- " and "1. "
// lists, **bold**, *italic* and `code`.

import katex from "katex";

const ESCAPES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

export const escapeHtml = (text: string) => text.replace(/[&<>"']/g, (c) => ESCAPES[c]);

/** `html` drops KaTeX's MathML copy: only for previews hidden from assistive tech. */
export type MathOutput = "htmlAndMathml" | "html";

export function tex(latex: string, display = false, output: MathOutput = "htmlAndMathml"): string {
  return katex.renderToString(latex, {
    displayMode: display,
    throwOnError: false,
    strict: "ignore",
    trust: false,
    output,
  });
}

function formatText(text: string): string {
  return escapeHtml(text)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*\w])\*([^*\s][^*]*?)\*(?![\w*])/g, "$1<em>$2</em>");
}

// $$display$$ first, then $inline$ (a backslash-escaped \$ is not a delimiter).
const MATH_RE = /\$\$([\s\S]+?)\$\$|(?<!\\)\$((?:\\\$|[^$])+?)\$/g;

/** Render one line or run of text: inline Markdown plus math, no block wrappers. */
export function renderInline(text: string, output: MathOutput = "htmlAndMathml"): string {
  let html = "";
  let last = 0;
  for (const match of text.matchAll(MATH_RE)) {
    const start = match.index ?? 0;
    html += formatText(text.slice(last, start).replace(/\\\$/g, "$"));
    html +=
      match[1] !== undefined ? tex(match[1].trim(), true, output) : tex(match[2].trim(), false, output);
    last = start + match[0].length;
  }
  html += formatText(text.slice(last).replace(/\\\$/g, "$"));
  return html;
}

/** Render a block of text: paragraphs and lists. */
export function renderRich(text: string, output: MathOutput = "htmlAndMathml"): string {
  const blocks = text.trim().split(/\n\s*\n/);
  return blocks
    .map((block) => {
      const lines = block.split("\n").filter((l) => l.trim() !== "");
      if (lines.length && lines.every((l) => /^\s*[-*]\s+/.test(l))) {
        const items = lines.map((l) => `<li>${renderInline(l.replace(/^\s*[-*]\s+/, ""), output)}</li>`);
        return `<ul>${items.join("")}</ul>`;
      }
      if (lines.length && lines.every((l) => /^\s*\d+[.)]\s+/.test(l))) {
        const items = lines.map((l) => `<li>${renderInline(l.replace(/^\s*\d+[.)]\s+/, ""), output)}</li>`);
        return `<ol>${items.join("")}</ol>`;
      }
      return `<p>${lines.map((l) => renderInline(l, output)).join("<br/>")}</p>`;
    })
    .join("");
}
