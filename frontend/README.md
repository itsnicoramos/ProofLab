# ProofLab 

The Next.js 16 frontend for ProofLab. See the [root README](../README.md) for running it
alongside the backend, and [SPEC.md](../SPEC.md) for how checking works.

```
src/
├── app/
│   ├── page.tsx                  home: Continue shelf + a shelf per topic
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
│   ├── Badges.tsx, ProgressMark.tsx
└── lib/
    ├── api.ts                    server-side backend client (PROOFLAB_API_URL)
    ├── actions.ts                Server Actions: checkWork, revealSolution, gradeTest,
    │                             getSearchIndex
    ├── search.ts                 search ranking
    ├── scan.ts                   photo shrinking, reader calls, tidying lines into steps
    ├── storage.ts                drafts + progress in localStorage
    ├── rich.ts                   safe Markdown-subset + LaTeX renderer
    ├── labels.ts, types.ts
```

- Pages fetch from the backend at request time inside `<Suspense>` (Cache Components is on),
  so `npm run build` doesn't need the backend running.
- The browser never calls the backend directly: checks go through Server Actions, so the
  backend URL stays server-side and no CORS setup is needed.
- Drafts, revealed hints, your best result per problem, and practice-test answers, scores and
  timings live in this browser's `localStorage` only.
