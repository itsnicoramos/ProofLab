import "katex/dist/katex.min.css";
import "./globals.css";

import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, Source_Serif_4 } from "next/font/google";
import Link from "next/link";
import { Suspense } from "react";

import { ActiveCourseLinks } from "@/components/ActiveCourseLinks";
import { CourseLinks } from "@/components/CourseLinks";
import { SigmaMark } from "@/components/Logo";
import { ActiveMobileMenu, MobileMenu } from "@/components/MobileNav";
import { SearchDialog } from "@/components/SearchDialog";
import { SyncAgent } from "@/components/SyncAgent";
import { ActiveSectionLink, SectionLink } from "@/components/TestsLink";
import { ActiveXpLink, XpLink } from "@/components/XpLink";

// DESIGN.md: serif for headings (textbook voice beside KaTeX), Geist for UI, mono for input.
const sourceSerif = Source_Serif_4({ variable: "--font-source-serif", subsets: ["latin"] });
const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "ProofLab", template: "%s · ProofLab" },
  description: "Check your math one step at a time. Verdicts come from written rules, not AI.",
};

export const viewport: Viewport = {
  // Lets the phone menu sheet keep clear of the home indicator (env(safe-area-inset-bottom)).
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f6f3" },
    { media: "(prefers-color-scheme: dark)", color: "#111210" },
  ],
};

const SECTIONS = [
  { href: "/cards", label: "Flashcards" },
  { href: "/tests", label: "Tests" },
];

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${sourceSerif.variable} ${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col font-sans">
        <header className="sticky top-0 z-30 border-b border-line bg-bg">
          <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4 sm:gap-6 sm:px-6">
            <Link
              href="/"
              className="flex h-11 shrink-0 items-center gap-2 font-serif text-[17px] font-semibold"
            >
              <SigmaMark className="h-5 w-5 text-accent" />
              ProofLab
            </Link>
            <nav aria-label="Courses" className="shelf hidden min-w-0 flex-1 overflow-x-auto sm:block">
              <Suspense fallback={<CourseLinks active={null} />}>
                <ActiveCourseLinks />
              </Suspense>
            </nav>
            <div className="ml-auto flex shrink-0 items-center gap-2 sm:ml-0 sm:gap-3">
              <nav aria-label="Study" className="hidden items-center gap-1 sm:flex">
                {SECTIONS.map((s) => (
                  <Suspense key={s.href} fallback={<SectionLink {...s} active={false} />}>
                    <ActiveSectionLink {...s} />
                  </Suspense>
                ))}
                <Suspense fallback={<XpLink active={false} />}>
                  <ActiveXpLink />
                </Suspense>
              </nav>
              <SearchDialog />
              <div className="sm:hidden">
                <Suspense fallback={<MobileMenu pathname={null} />}>
                  <ActiveMobileMenu />
                </Suspense>
              </div>
            </div>
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 sm:py-10">
          {children}
        </main>
        <footer className="border-t border-line">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-1 px-4 py-4 text-xs text-muted sm:px-6">
            <Link
              href="/help"
              className="flex h-11 items-center text-sm text-ink hover:text-accent"
            >
              Typing math
            </Link>
            <p>&copy; 2026 ProofLab. All rights reserved.</p>
          </div>
        </footer>
        <SyncAgent />
      </body>
    </html>
  );
}
