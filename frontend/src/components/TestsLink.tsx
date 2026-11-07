"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** A top-bar link to a section (Tests, Flashcards), underlined in the accent when current. */
export function SectionLink({
  href,
  label,
  active,
}: {
  href: string;
  label: string;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`flex h-11 shrink-0 items-center border-b-2 px-2.5 text-sm transition-colors ${
        active
          ? "border-accent font-medium text-ink"
          : "border-transparent text-muted hover:border-line hover:text-ink"
      }`}
    >
      {label}
    </Link>
  );
}

/** A section link with "you are here" marking. Wrap in <Suspense> (usePathname suspends). */
export function ActiveSectionLink({ href, label }: { href: string; label: string }) {
  return <SectionLink href={href} label={label} active={usePathname().startsWith(href)} />;
}
