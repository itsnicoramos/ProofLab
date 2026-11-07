"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  type KeyboardEvent as ReactKeyboardEvent,
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  useTransition,
} from "react";

import { getSearchIndex, type SearchEntry } from "@/lib/actions";
import { search, TYPE_LABEL } from "@/lib/search";

function MagnifierIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden className={className}>
      <circle cx="8.5" cy="8.5" r="5.5" stroke="currentColor" strokeWidth="1.8" />
      <path d="M12.6 12.6 17 17" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

const isTypingTarget = (target: EventTarget | null) =>
  target instanceof HTMLElement &&
  (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));

/** Navbar search over topics, problems and practice tests. Opens with "/" or ⌘/Ctrl + K. */
export function SearchDialog() {
  const router = useRouter();
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const listId = useId();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [entries, setEntries] = useState<SearchEntry[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, startLoading] = useTransition();
  // Browsers send a mousemove when the list re-renders under a still cursor; only a pointer
  // that really moved should take the highlight away from the keyboard.
  const lastPointer = useRef<string | null>(null);

  const load = useCallback(() => {
    startLoading(async () => {
      const res = await getSearchIndex();
      if (res.ok) {
        setEntries(res.entries);
        setLoadError(null);
      } else {
        setLoadError(res.error);
      }
    });
  }, []);

  const open = useCallback(() => {
    const d = dialog.current;
    if (!d || d.open) return;
    d.showModal();
    input.current?.focus();
    if (entries === null && !loading) load();
  }, [entries, loading, load]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const k = event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey);
      const slash = event.key === "/" && !event.metaKey && !event.ctrlKey && !event.altKey;
      if (k || (slash && !isTypingTarget(event.target))) {
        event.preventDefault();
        open();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const results = useMemo(() => (entries ? search(entries, query) : []), [entries, query]);
  const current = Math.min(active, Math.max(results.length - 1, 0));
  const optionId = (i: number) => `${listId}-option-${i}`;

  useEffect(() => {
    document.getElementById(optionId(current))?.scrollIntoView({ block: "nearest" });
  });

  function close() {
    dialog.current?.close();
  }

  function onInputKey(event: ReactKeyboardEvent<HTMLInputElement>) {
    if (results.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((current + 1) % results.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((current - 1 + results.length) % results.length);
    } else if (event.key === "Enter") {
      event.preventDefault();
      close();
      router.push(results[current].href);
    }
  }

  const trimmed = query.trim();

  return (
    <>
      <button
        type="button"
        onClick={open}
        aria-label="Search topics, problems and tests"
        aria-keyshortcuts="/ Control+K Meta+K"
        className="flex h-11 min-w-11 shrink-0 items-center justify-center gap-2 rounded-lg border border-line px-2.5 text-sm text-muted transition-colors hover:border-accent hover:text-ink md:px-3"
      >
        <MagnifierIcon className="h-4 w-4" />
        <span className="hidden md:inline">Search</span>
        <kbd className="hidden rounded border border-line px-1.5 font-mono text-xs md:inline">
          /
        </kbd>
      </button>

      <dialog
        ref={dialog}
        aria-label="Search"
        onClick={(e) => {
          if (e.target === e.currentTarget) close(); // a click on the backdrop
        }}
        onClose={() => {
          setQuery("");
          setActive(0);
          lastPointer.current = null;
        }}
        className="mx-auto mt-[10vh] w-[calc(100%-2rem)] max-w-xl rounded-xl border border-line bg-surface p-0 text-ink shadow-xl backdrop:bg-black/40"
      >
        <div className="flex items-center gap-2 border-b border-line pl-3">
          <MagnifierIcon className="h-4 w-4 shrink-0 text-muted" />
          <input
            ref={input}
            role="combobox"
            aria-label="Search topics, problems and tests"
            aria-expanded={results.length > 0}
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={results.length ? optionId(current) : undefined}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={onInputKey}
            placeholder="Search a topic, problem or test"
            autoComplete="off"
            spellCheck={false}
            className="h-12 min-w-0 flex-1 bg-transparent text-[15px] outline-none placeholder:text-muted/70"
          />
          <button
            type="button"
            onClick={close}
            aria-label="Close search"
            className="h-12 px-3 text-xs text-muted hover:text-ink"
          >
            Esc
          </button>
        </div>

        <div className="max-h-[60vh] overflow-y-auto p-2" aria-live="polite">
          {loading && entries === null && (
            <p className="px-2 py-3 text-sm text-muted">Loading topics and problems…</p>
          )}
          {loadError && (
            <div className="flex flex-wrap items-center gap-3 px-2 py-3 text-sm">
              <span className="text-bad">{loadError}</span>
              <button
                type="button"
                onClick={load}
                className="h-11 rounded-md border border-line px-3 hover:border-accent"
              >
                Try again
              </button>
            </div>
          )}
          {entries && results.length === 0 && (
            <p className="px-2 py-3 text-sm text-muted">
              No topics, problems or tests match &ldquo;{trimmed}&rdquo;.
            </p>
          )}
          {entries && results.length > 0 && !trimmed && (
            <p className="px-2 pb-1 pt-1 text-xs text-muted">Topics</p>
          )}
          <ul id={listId} role="listbox" aria-label="Results">
            {results.map((r, i) => (
              <li key={`${r.type}:${r.href}:${r.label}`} role="presentation">
                <Link
                  id={optionId(i)}
                  role="option"
                  aria-selected={i === current}
                  tabIndex={-1}
                  href={r.href}
                  onClick={close}
                  onPointerMove={(e) => {
                    const at = `${e.clientX},${e.clientY}`;
                    if (lastPointer.current !== null && lastPointer.current !== at) setActive(i);
                    lastPointer.current = at;
                  }}
                  className={`flex min-h-11 items-center gap-3 rounded-md px-2 py-1.5 ${
                    i === current ? "bg-accent-soft" : ""
                  }`}
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm">{r.label}</span>
                    <span className="block truncate text-xs text-muted">{r.detail}</span>
                  </span>
                  <span className="shrink-0 text-xs text-muted">{TYPE_LABEL[r.type]}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>

        <p className="hidden border-t border-line px-3 py-2 text-xs text-muted sm:block">
          ↑ ↓ to move · Enter to open · Esc to close
        </p>
      </dialog>
    </>
  );
}
