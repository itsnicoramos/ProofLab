import type { Metadata } from "next";
import { Suspense } from "react";

import { type CardCourse, FlashcardsHome } from "@/components/FlashcardsHome";
import { getCourses, getDeckCards } from "@/lib/api";
import { COURSE_ORDER, topicLabel } from "@/lib/labels";

export const metadata: Metadata = { title: "Flashcards" };

export default function CardsPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-10">
      <header className="space-y-3">
        <h1 className="text-3xl sm:text-4xl">Flashcards</h1>
        <p className="text-muted">
          Cards made from the book&apos;s definitions and theorems, from every problem with its
          worked solution, and from your own notes. ProofLab schedules each card for just before
          you&apos;d forget it, and the schedule tunes itself to your answers. No AI.
        </p>
      </header>
      <Suspense fallback={<HomeSkeleton />}>
        <Home />
      </Suspense>
    </div>
  );
}

async function Home() {
  const courses = await getCourses();
  const order = (id: string) => COURSE_ORDER.indexOf(id as (typeof COURSE_ORDER)[number]);
  const usable = courses.filter((c) => c.problems > 0).sort((a, b) => order(a.id) - order(b.id));
  const concepts = await Promise.all(usable.map((c) => getDeckCards(c.id, null, "concepts")));
  const cardCourses: CardCourse[] = usable.map((c, i) => {
    const byTopic = new Map<string, number>();
    for (const card of concepts[i]) byTopic.set(card.topic, (byTopic.get(card.topic) ?? 0) + 1);
    return {
      id: c.id,
      topics: c.topics
        .filter((t) => t.problems > 0 || byTopic.has(t.topic))
        .map((t) => ({
          topic: t.topic,
          label: topicLabel(t.topic, c.id),
          problems: t.problems,
          concepts: byTopic.get(t.topic) ?? 0,
        })),
    };
  });
  return <FlashcardsHome courses={cardCourses} />;
}

function HomeSkeleton() {
  return (
    <div
      aria-busy
      aria-label="Loading decks"
      className="h-96 animate-pulse rounded-xl border border-line bg-surface motion-reduce:animate-none"
    />
  );
}
