"use client";

import { useMemo } from "react";

import { renderRich } from "@/lib/rich";

/**
 * A card's typeset problem statement. A client component on purpose: it is still rendered on
 * the server, but React's hydration data then carries only the short source text instead of
 * the rendered KaTeX HTML (which would otherwise be sent twice). HTML-only KaTeX and
 * `aria-hidden`: it's a visual preview; the card's title names it, the problem page has it all.
 */
export function MathPreview({ text, className = "" }: { text: string; className?: string }) {
  const html = useMemo(() => renderRich(text, "html"), [text]);
  return <div aria-hidden className={`rich ${className}`} dangerouslySetInnerHTML={{ __html: html }} />;
}
