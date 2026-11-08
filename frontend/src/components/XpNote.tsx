"use client";

// The XP an action just earned, said plainly (DESIGN.md: ProofLab acknowledges earned XP, with
// no confetti, sounds or mascots). Shows the amount, how it was worked out, why it was less
// when it was, and one line when this action finished the daily goal.

import { useXpToday } from "@/lib/xp";
import type { XpPart } from "@/lib/xpRules";

const signed = (n: number) => (n < 0 ? `−${-n}` : `+${n}`);

export function partsText(parts: XpPart[]): string {
  return parts.map((p, i) => (i === 0 ? `${p.label} ${p.xp}` : `${p.label} ${signed(p.xp)}`)).join(", ");
}

/** XP earned by one or more recorded events (their uids), or nothing until they're scored. */
export function XpNote({
  uids,
  breakdown = true,
  className = "",
}: {
  uids: string[];
  breakdown?: boolean;
  className?: string;
}) {
  const { summary, ready, today, todayXp, goal, streak } = useXpToday();
  if (!ready || uids.length === 0) return null;
  const entries = uids.map((u) => summary.byUid[u]).filter((e) => e !== undefined);
  if (entries.length === 0) return null;
  const xp = entries.reduce((s, e) => s + e.xp, 0);
  const gainedToday = entries.filter((e) => e.day === today).reduce((s, e) => s + e.xp, 0);
  const finishedGoal = gainedToday > 0 && todayXp >= goal && todayXp - gainedToday < goal;
  const single = entries.length === 1 ? entries[0] : null;
  const note = single?.note ?? null;

  return (
    <div className={`space-y-0.5 text-sm ${className}`}>
      {xp > 0 ? (
        <p>
          <span className="font-semibold tabular-nums">+{xp} XP</span>
          {breakdown && single && single.parts.length > 1 && (
            <span className="ml-2 text-muted">{partsText(single.parts)}</span>
          )}
        </p>
      ) : (
        <p className="font-medium">{note ?? "No XP this time."}</p>
      )}
      {xp > 0 && note && <p className="text-muted">{note}</p>}
      {finishedGoal && (
        <p className="font-medium">
          Daily goal done: {todayXp} XP today
          {streak && streak.current > 1 ? `. ${streak.current}-day streak.` : "."}
        </p>
      )}
    </div>
  );
}
