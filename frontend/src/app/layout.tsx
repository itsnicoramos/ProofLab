import "katex/dist/katex.min.css";
import "./globals.css";

import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, Source_Serif_4 } from "next/font/google";
import Link from "next/link";

import { SigmaMark } from "@/components/Logo";
import { BOOK_URL, GITHUB_URL } from "@/lib/site";

// DESIGN.md: serif for headings (textbook voice beside KaTeX), Geist for UI, mono for commands.
const sourceSerif = Source_Serif_4({ variable: "--font-source-serif", subsets: ["latin"] });
const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "ProofLab tutor", template: "%s · ProofLab" },
  description:
    "What a coding agent does when you type /tutor in the ProofLab repo: it teaches Book of Proof, and ProofLab's checker, not AI, decides what's right.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f6f3" },
    { media: "(prefers-color-scheme: dark)", color: "#111210" },
  ],
};

const SECTIONS = [
  { href: "/#how", label: "How it works" },
  { href: "/#session", label: "Session" },
  { href: "/#rules", label: "Rules" },
  { href: "/#setup", label: "Set up" },
];

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${sourceSerif.variable} ${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col font-sans">
        <header className="sticky top-0 z-30 border-b border-line bg-bg">
          <div className="mx-auto flex h-14 max-w-6xl items-center gap-2 px-4 sm:gap-6 sm:px-6">
            <Link
              href="/"
              className="flex h-11 shrink-0 items-center gap-2 font-serif text-[17px] font-semibold"
            >
              <SigmaMark className="h-5 w-5 text-accent" />
              ProofLab
            </Link>
            <nav aria-label="On this page" className="hidden items-center gap-1 md:flex">
              {SECTIONS.map((s) => (
                <Link
                  key={s.href}
                  href={s.href}
                  className="flex h-11 items-center rounded-md px-3 text-sm text-muted hover:text-ink"
                >
                  {s.label}
                </Link>
              ))}
            </nav>
            <div className="ml-auto flex items-center gap-1">
              <Link
                href="/#setup"
                className="flex h-11 items-center rounded-md px-3 text-sm text-muted hover:text-ink md:hidden"
              >
                Set up
              </Link>
              <a
                href={GITHUB_URL}
                className="flex h-11 items-center rounded-lg border border-line bg-surface px-3 text-sm font-semibold"
              >
                GitHub
              </a>
            </div>
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6 sm:py-14">{children}</main>
        <footer className="border-t border-line">
          <div className="mx-auto max-w-6xl space-y-2 px-4 py-5 text-sm text-muted sm:px-6">
            <p>ProofLab is MIT licensed. Copyright 2026 itsnicoramos.</p>
            <p>
              <em>Book of Proof</em> is by Richard Hammack, free from the author under CC BY-NC-ND
              4.0. ProofLab cites it by section and page and copies none of its text.
            </p>
            <div className="flex flex-wrap gap-x-6">
              <a href={GITHUB_URL} className="inline-flex h-11 items-center text-ink hover:text-accent">
                Source on GitHub
              </a>
              <a href={BOOK_URL} className="inline-flex h-11 items-center text-ink hover:text-accent">
                Book of Proof, free PDF
              </a>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
