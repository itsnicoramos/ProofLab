"use client";

// Phone navigation (DESIGN.md, Navigation): below the sm breakpoint the top bar keeps the Σ
// mark, Search and a labelled Menu button. The menu is a side sheet with the study sections
// (Progress shows today's XP), every course and the typing guide. From sm up the top bar shows everything in one row.

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRef } from "react";

import { COURSE_ORDER, COURSE_SHORT, courseOfProblemId, isCourseId } from "@/lib/labels";
import { useXpToday } from "@/lib/xp";

function courseFromPath(pathname: string) {
  const [, section, id] = pathname.split("/");
  if (section === "courses" && id && isCourseId(id)) return id;
  if (section === "problems" && id) return courseOfProblemId(decodeURIComponent(id));
  return null;
}

const SECTIONS = [
  {
    href: "/",
    label: "Practice",
    match: (p: string) => p === "/" || p.startsWith("/problems"),
  },
  { href: "/cards", label: "Flashcards", match: (p: string) => p.startsWith("/cards") },
  { href: "/tests", label: "Tests", match: (p: string) => p.startsWith("/tests") },
  { href: "/progress", label: "Progress", match: (p: string) => p.startsWith("/progress") },
];

/** Today's XP beside the Progress row (blank until the browser's copy is read). */
function TodayXp() {
  const { ready, todayXp, goal, streak } = useXpToday();
  if (!ready) return null;
  const days = streak?.current ?? 0;
  return (
    <span className="ml-auto pl-3 text-sm tabular-nums text-muted">
      {todayXp} / {goal} XP{days > 0 ? ` · ${days}-day streak` : ""}
    </span>
  );
}

function MenuIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-5 w-5" aria-hidden>
      <path
        d="M3.5 5.5h13M3.5 10h13M3.5 14.5h13"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}

const rowClass = (current: boolean) =>
  `flex min-h-12 items-center rounded-md px-3 text-[15px] ${
    current ? "bg-accent-soft font-medium" : "hover:bg-surface-2"
  }`;

/** The phone's hamburger menu: a labelled button that opens a side sheet. */
export function MobileMenu({ pathname }: { pathname: string | null }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const course = pathname ? courseFromPath(pathname) : null;
  const close = () => dialog.current?.close();

  return (
    <>
      <button
        type="button"
        onClick={() => dialog.current?.showModal()}
        aria-haspopup="dialog"
        className="flex h-11 items-center gap-2 rounded-lg border border-line px-3 text-sm text-ink"
      >
        <MenuIcon />
        Menu
      </button>
      <dialog
        ref={dialog}
        aria-label="Menu"
        onClick={(e) => {
          if (e.target === e.currentTarget) close(); // a tap on the backdrop
        }}
        className="fixed inset-y-0 right-0 left-auto m-0 h-dvh max-h-none w-[min(20rem,86vw)] overflow-y-auto border-l border-line bg-surface p-0 text-ink backdrop:bg-black/40"
      >
        <div className="flex min-h-full flex-col px-3 pb-[max(1rem,env(safe-area-inset-bottom))] pt-3">
          <div className="flex items-center justify-between pb-2 pl-3">
            <p className="font-serif text-lg font-semibold">ProofLab</p>
            <button
              type="button"
              onClick={close}
              className="flex h-11 items-center rounded-lg px-3 text-sm text-muted hover:text-ink"
            >
              Close
            </button>
          </div>

          <nav aria-label="Sections">
            <ul>
              {SECTIONS.map((s) => {
                const current = pathname !== null && s.match(pathname);
                return (
                  <li key={s.href}>
                    <Link
                      href={s.href}
                      onClick={close}
                      aria-current={current ? "page" : undefined}
                      className={rowClass(current)}
                    >
                      {s.label}
                      {s.href === "/progress" && <TodayXp />}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          <nav aria-label="Courses" className="mt-4 border-t border-line pt-3">
            <p className="px-3 pb-1 text-xs text-muted">Courses</p>
            <ul>
              {COURSE_ORDER.map((id) => (
                <li key={id}>
                  <Link
                    href={`/courses/${id}`}
                    onClick={close}
                    aria-current={id === course ? "page" : undefined}
                    className={rowClass(id === course)}
                  >
                    {COURSE_SHORT[id]}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <div className="mt-4 border-t border-line pt-3">
            <Link
              href="/help"
              onClick={close}
              aria-current={pathname === "/help" ? "page" : undefined}
              className={rowClass(pathname === "/help")}
            >
              Typing math
            </Link>
          </div>
        </div>
      </dialog>
    </>
  );
}

/** The menu with the current page marked. Wrap in <Suspense> (usePathname suspends). */
export function ActiveMobileMenu() {
  return <MobileMenu pathname={usePathname()} />;
}
