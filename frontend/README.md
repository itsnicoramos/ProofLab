# ProofLab 

The Next.js 16 frontend for ProofLab. See the [root README](../README.md) for running it
alongside the backend, and [SPEC.md](../SPEC.md) for how checking works.

```
src/
├── app/
│   ├── page.tsx                  home: Today line, Continue shelf + a shelf per topic
│   ├── progress/page.tsx         XP, daily goal, streak, level, chapters, milestones
│   ├── courses/[course]/page.tsx problems grouped by topic, with your progress
│   ├── problems/[id]/page.tsx    prompt, step editor, verdict, hints, solution
│   ├── tests/page.tsx            practice-test builder + your past tests
│   ├── tests/[course]/[kind]/    a practice midterm or final (exam mode, graded on submit)
│   ├── api/read/route.ts         proxies scanned files to the backend reader
│   ├── help/page.tsx             how to type math
│   └── error.tsx, not-found.tsx
├── components/
│   ├── Workspace.tsx             the interactive step editor (practice and exam modes)
│   ├── TestBuilder.tsx, TestRunner.tsx, TestHistory.tsx
│   ├── SearchDialog.tsx          navbar search (/ or ⌘K), index loaded on first open
│   ├── ScanDialog.tsx            "Scan work": camera, files, drop, paste → review → steps
│   ├── Rich.tsx                  Markdown + KaTeX rendering
│   ├── Badges.tsx, ProgressMark.tsx, ChapterSolved.tsx
│   ├── XpNote.tsx, XpLink.tsx    "+20 XP" under a verdict; today's XP in the top bar
│   ├── TodayStrip.tsx, ProgressView.tsx
└── lib/
    ├── api.ts                    server-side backend client (PROOFLAB_API_URL)
    ├── actions.ts                Server Actions: checkWork, revealSolution, gradeTest,
    │                             getSearchIndex
    ├── search.ts                 search ranking
    ├── scan.ts                   photo shrinking, reader calls, tidying lines into steps
    ├── storage.ts                drafts + progress in localStorage
    ├── rich.ts                   safe Markdown-subset + LaTeX renderer
    ├── xp.ts                     the XP activity log, goal, today (synced like reviews)
    ├── xpRules.ts                XP, streak, level and milestone rules (pure; `npm test`)
    ├── labels.ts, types.ts
```

`npm test` runs the XP rule tests with Node's built-in test runner (`node --test`; Node 24
runs TypeScript directly, so nothing extra is installed).

- Pages fetch from the backend at request time inside `<Suspense>` (Cache Components is on),
  so `npm run build` doesn't need the backend running.
- The browser never calls the backend directly: checks go through Server Actions, so the
  backend URL stays server-side and no CORS setup is needed.
- Drafts and revealed hints live in this browser's `localStorage` only. Best results, test
  records, flashcard reviews and the XP activity log are kept there too and synced to the
  progress database (`lib/sync.ts`, SPEC §17) when the backend has one.
