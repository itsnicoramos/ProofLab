import type { Metadata } from "next";
import { Suspense } from "react";

import { StudySession } from "@/components/StudySession";

export const metadata: Metadata = { title: "Study flashcards" };

export default function StudyPage() {
  return (
    <div className="mx-auto max-w-2xl">
      <Suspense
        fallback={
          <div
            aria-busy
            aria-label="Loading cards"
            className="h-80 animate-pulse rounded-xl border border-line bg-surface motion-reduce:animate-none"
          />
        }
      >
        <StudySession />
      </Suspense>
    </div>
  );
}
