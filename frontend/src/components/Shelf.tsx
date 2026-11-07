"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

/**
 * A row of cards scrolled sideways (DESIGN.md: browsing shelves). Arrow buttons page through
 * it on larger screens; "Show all" switches to a wrapped grid when the row is long.
 */
export function Shelf({
  id,
  title,
  meta,
  heading = "h3",
  expandable = false,
  action,
  children,
}: {
  id: string;
  title: string;
  meta?: string;
  heading?: "h2" | "h3";
  expandable?: boolean;
  action?: ReactNode;
  children: ReactNode;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const [edges, setEdges] = useState({ start: true, end: true });
  const [expanded, setExpanded] = useState(false);
  const Heading = heading;
  const headingId = `${id}-heading`;

  const measure = useCallback(() => {
    const el = scroller.current;
    if (!el) return;
    setEdges({
      start: el.scrollLeft <= 4,
      end: el.scrollLeft + el.clientWidth >= el.scrollWidth - 4,
    });
  }, []);

  useEffect(() => {
    const el = scroller.current;
    if (!el || expanded) return;
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [expanded, measure]);

  function page(direction: 1 | -1) {
    // MOTION 1 (DESIGN.md): jump a page instantly; scroll-snap lines the next card up.
    scroller.current?.scrollBy({ left: direction * scroller.current.clientWidth * 0.9 });
    measure(); // instant scrolls update scrollLeft now; don't wait for a (throttled) scroll event
  }

  const overflowing = !(edges.start && edges.end);

  return (
    <section aria-labelledby={headingId} id={id} className="scroll-mt-28">
      <div className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <Heading id={headingId} className={heading === "h2" ? "text-xl" : "text-lg"}>
          {title}
        </Heading>
        {meta && <span className="text-sm text-muted">{meta}</span>}
        <div className="ml-auto flex items-center gap-1">
          {action}
          {expandable && (overflowing || expanded) && (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              aria-expanded={expanded}
              aria-controls={`${id}-items`}
              className="flex h-11 items-center rounded-md px-2.5 text-sm text-muted hover:bg-idle-soft hover:text-ink"
            >
              {expanded ? "Show as a row" : "Show all"}
            </button>
          )}
          {!expanded && overflowing && (
            <span className="hidden items-center gap-1 md:flex">
              <button
                type="button"
                onClick={() => page(-1)}
                disabled={edges.start}
                aria-label={`Scroll ${title} back`}
                className="flex h-11 w-11 items-center justify-center rounded-md border border-line text-lg text-ink hover:bg-idle-soft disabled:opacity-35"
              >
                ‹
              </button>
              <button
                type="button"
                onClick={() => page(1)}
                disabled={edges.end}
                aria-label={`Scroll ${title} forward`}
                className="flex h-11 w-11 items-center justify-center rounded-md border border-line text-lg text-ink hover:bg-idle-soft disabled:opacity-35"
              >
                ›
              </button>
            </span>
          )}
        </div>
      </div>
      <div
        id={`${id}-items`}
        ref={scroller}
        onScroll={measure}
        className={
          expanded
            ? "grid grid-cols-[repeat(auto-fill,minmax(15rem,1fr))] gap-3 [&>*]:w-auto"
            : "shelf relative -mx-4 flex snap-x snap-mandatory scroll-px-4 gap-3 overflow-x-auto px-4 pb-3 sm:-mx-6 sm:scroll-px-6 sm:px-6"
        }
      >
        {children}
      </div>
    </section>
  );
}
