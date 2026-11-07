"use client";

import { usePathname } from "next/navigation";

import { CourseLinks } from "@/components/CourseLinks";
import { courseOfProblemId, isCourseId } from "@/lib/labels";
import type { CourseId } from "@/lib/types";

function courseFromPath(pathname: string): CourseId | null {
  const [, section, id] = pathname.split("/");
  if (section === "courses" && id && isCourseId(id)) return id;
  if (section === "problems" && id) return courseOfProblemId(decodeURIComponent(id));
  return null;
}

/** Course links with the current course marked. Wrap in <Suspense> (usePathname suspends). */
export function ActiveCourseLinks() {
  return <CourseLinks active={courseFromPath(usePathname())} />;
}
