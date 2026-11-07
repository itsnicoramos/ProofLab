import { renderInline, renderRich, tex } from "@/lib/rich";

/** Problem text with Markdown and $LaTeX$, rendered to safe HTML (see lib/rich.ts). */
export function Rich({
  text,
  inline = false,
  className = "",
}: {
  text: string;
  inline?: boolean;
  className?: string;
}) {
  const html = inline ? renderInline(text) : renderRich(text);
  const Tag = inline ? "span" : "div";
  return <Tag className={`rich ${className}`} dangerouslySetInnerHTML={{ __html: html }} />;
}

/** A single LaTeX expression, e.g. how the checker read a step. */
export function Tex({ latex, className = "" }: { latex: string; className?: string }) {
  return <span className={className} dangerouslySetInnerHTML={{ __html: tex(latex) }} />;
}
