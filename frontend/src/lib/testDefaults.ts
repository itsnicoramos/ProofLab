// Test defaults shared by the server-rendered test page and the browser-side builder.

import type { TestKind, TestStyle } from "./types";

export const DEFAULT_LENGTH: Record<TestKind, number> = { midterm: 8, final: 12, quiz: 10 };
export const DEFAULT_STYLE: Record<TestKind, TestStyle> = {
  midterm: "written",
  final: "written",
  quiz: "choice",
};
