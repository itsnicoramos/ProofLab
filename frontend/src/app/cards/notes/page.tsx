import type { Metadata } from "next";

import { NotesImport } from "@/components/NotesImport";

export const metadata: Metadata = { title: "Make cards from notes" };

export default function NotesPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <header className="space-y-3">
        <h1 className="text-3xl sm:text-4xl">Make cards from your notes</h1>
        <p className="text-muted">
          Paste your notes, or upload a photo, PDF or document. ProofLab looks for the shapes people
          use to write things down (&ldquo;Term: meaning&rdquo;, &ldquo;Definition 4.1&rdquo;,
          &ldquo;... is called ...&rdquo;, &ldquo;Q: / A:&rdquo;, formulas) using written rules, not
          AI. You check and edit every card before saving. Decks are saved in ProofLab&apos;s database
          on your Mac, so your phone and laptop share them.
        </p>
      </header>
      <NotesImport />
    </div>
  );
}
