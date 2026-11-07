import Link from "next/link";

import { COURSE_NAV, COURSE_ORDER } from "@/lib/labels";
import type { CourseId } from "@/lib/types";

/** Every course as a direct link. `active` marks where the student is ("you are here"). */
export function CourseLinks({ active }: { active: CourseId | null }) {
  return (
    <ul className="flex items-stretch gap-1">
      {COURSE_ORDER.map((id) => {
        const current = id === active;
        return (
          <li key={id} className="shrink-0">
            <Link
              href={`/courses/${id}`}
              aria-current={current ? "page" : undefined}
              className={`flex h-11 items-center border-b-2 px-2.5 text-sm transition-colors ${
                current
                  ? "border-accent font-medium text-ink"
                  : "border-transparent text-muted hover:border-line hover:text-ink"
              }`}
            >
              {COURSE_NAV[id]}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
