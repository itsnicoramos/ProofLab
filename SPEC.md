# ProofLab Specification

> **Source of truth.** When code, tests, or content disagree with this file, this file wins
> (or this file gets updated in the same change).

## 1. What ProofLab is

ProofLab is a **deterministic, step-by-step checker for university math work**. A student
picks a problem, types their work one step at a time, and ProofLab tells them *which step*
went wrong and *why*, with rule-based hints.

- **Verdicts never come from AI.** Every verdict (status, score, step results, hint codes)
  comes from SymPy computations, numeric evaluation, and hand-written rules. Same input → same
  verdict. A local LLM assistant (Ollama) is **planned, not wired** (§12): it may explain,
  tutor and give extra hints, but it can never mark work right or wrong.
  The repo tutor (§20) runs in the learner's own coding agent under the same rule: it
  teaches and hints, and the checker grades.
- **First target: MATH 123**, whose textbook is *Book of Proof* (Hammack, 3rd ed.), all 14
  chapters. Then every math/STEM course after it. Content is organised by course track so new
  courses are added as content + topic modules, not rewrites.
- **Two parts.** `backend/` is the Python API that does all checking, plus the tutor's CLI
  (§20). `frontend/` is the Next.js website: since 2026-11-08 a single static page explaining
  what the repo tutor does (§21). The practice site that used to call the API (§13 to §19) is
  in git history up to commit `0eb0d0f`.

### Scope disclaimer

ProofLab is a study aid. It checks a well-defined set of problem *kinds* (§5) and can only
verify what those kinds model. It is **not** a general proof assistant, does not read
natural-language proofs, and is not an official grading tool. A "correct" verdict means the
submitted work passed ProofLab's checks — it is not a substitute for an instructor's judgement.

### Non-goals (v0.1)

- User accounts, persistence, progress tracking (the API is stateless; the frontend can store
  attempts locally).
- Free-form proofs, contradiction/induction proofs, epsilon-delta proofs.
- Graphing.

## 2. Architecture

```
HTTP clients (§7)          prooflab-tutor CLI (§20, calls the checker in-process)
        │  HTTP/JSON                       │
        ▼                                  ▼
FastAPI  (api/routes.py, api/schemas.py)
        │
        ▼
Checker  (engine/checker.py)  ──►  isolated worker process with hard timeout
        │  dispatch by problem.kind
        ▼
Topic modules (engine/topics/<course>/<topic>.py)
        │  use
        ▼
Shared helpers (engine/algebra.py: safe parser, equivalence, sets)  +  hints.py
        ▲
Content (content/problems/**.json, content/references.json) — loaded and validated at startup
```

- **Python 3.12**, FastAPI, SymPy (+ mpmath), Pydantic v2. Dependency management with `uv`.
- Content is JSON, one file per problem, validated on startup. Invalid content = the server
  refuses to start (fail fast), and `tests/test_content.py` fails.

## 3. Math input syntax

Students type plain-text math. The parser is shared by every topic.

| Write | Means |
|---|---|
| `2x`, `3(x+1)`, `(x+1)(x-1)`, `x sin x` | implicit multiplication |
| `x^2`, `x**2`, `x²` | powers (`^` is power, never XOR) |
| `sqrt(x)`, `√x`, `cbrt(x)`, `root(x, 4)` | roots |
| `sin x`, `sin(2x)`, `sin^2(x)`, `sin^-1(x)` | trig; `sin^-1` means arcsin |
| `asin`, `arcsin`, `acos`, `atan`, `sec`, `csc`, `cot`, `sinh`, `cosh`, `tanh` | more functions |
| `ln(x)` | natural log |
| `log(x)` | **base-10** log (calculator convention) |
| `log_2(x)`, `log2(x)`, `log(x, 2)` | log base 2 |
| `e^x`, `exp(x)` | exponential (`e` is always Euler's number) |
| `pi`, `π` | π |
| `oo`, `inf`, `infinity`, `∞` | ∞ |
| `|x|`, `abs(x)` | absolute value |
| `n!` | factorial |
| `int(f, x)` / `int(f, x, a, b)` | an integral, in problems that allow it (integration steps) |

- Multi-letter runs are split greedily into known names and single letters: `xsinx` → `x·sin(x)`.
- Only the problem's declared variables (plus allowed constants such as `C`) may appear;
  anything else is a friendly error ("this problem uses x and y").
- Division binds left to right: `1/2x` means `(1/2)·x`. Every checked step echoes back the
  parsed expression as LaTeX so the student can see how ProofLab read it.
- Labels are allowed where an expression is expected: `f'(x) = 2x` and `dy/dx = 2x` are read
  as `2x`.

### Parser safety

Student input **never** reaches `eval`, `sympify`, or `parse_expr`. A hand-written tokenizer
and recursive-descent parser build SymPy objects directly from an allowlist of functions,
constants and declared variables. Limits: 500 characters per input, 300 tokens, nesting depth
60, numeric exponents ≤ 1000, integer literals ≤ 15 digits, `n!` only for n ≤ 500, numeric
results ≤ 20,000 bits. Checks run in a pool of reusable worker processes (memory-capped at
1 GB on Linux, recycled every 200 checks). A check that exceeds the timeout (default 10 s) has
its worker killed and replaced, and is reported as `invalid` with code `TIMEOUT`.

## 4. Core model (`engine/models.py`)

### Problem (one JSON file)

| Field | Type | Notes |
|---|---|---|
| `id` | str | `<course>.<topic>.<slug>`, e.g. `calc1.derivatives.product-rule-1`; unique |
| `course` | enum | `proofs`, `precalc`, `calc1`, `calc2`, `calc3`, `calc4`; must match folder |
| `topic` | str | must match a topic module name in that course (e.g. `derivatives`) |
| `kind` | str | a registered problem kind (§5) |
| `title`, `prompt` | str | prompt is Markdown with `$…$` LaTeX |
| `answer_format` | str | one line telling the student what to enter |
| `difficulty` | 1–3 | |
| `tags` | list[str] | free-form; course tags like `math123` go here |
| `data` | object | kind-specific parameters, validated by the kind's `Params` model |
| `answer` | str | the answer key, in the kind's answer format (empty for proofs) |
| `mistakes` | list | `{answer, hint}`: known wrong answers with targeted hints |
| `hints` | list[str] | authored progressive hints, revealed one at a time |
| `solution` | list[str] | worked solution, Markdown |
| `reference` | Citation | `{book, section, note?}`; `book` must exist in `references.json` |
| `review` | Review | §4.3 |
| `examples` | list | ≥ 2 sample submissions with expected verdicts (§8) |

**Live courses.** For now the site shows only `proofs`. The other five keep all their problems,
rules and tests, and the API still serves them, but the frontend hides them: `COURSE_ORDER` in
`frontend/src/lib/labels.ts` lists the live courses, `lib/api.ts` drops everything else from
course and problem lists, and their pages answer 404. Adding an id back to `COURSE_ORDER`
shows that course again.

Answer keys, mistakes, examples and solutions are **never** returned by
`GET /problems/{id}`. Solutions are only returned by `GET /problems/{id}/solution`.

### Submission

```json
{ "steps": [{"kind": "expr", "content": "2x sin(x) + x^2 cos(x)"}], "answer": "…" }
```

Step `kind` defaults to `expr`. Some problem kinds define extra step kinds (`let`, `case`,
`witness`, `lhopital`, `sub`, `test`, …) — see §5. Max 40 steps.

### 4.1 Verdict

```json
{
  "problem_id": "…",
  "status": "correct | partial | incorrect | invalid",
  "score": 1.0,
  "steps":  [{"index": 0, "kind": "expr", "status": "ok | warning | error | unchecked",
              "message": "…", "latex": "…", "code": "…"}],
  "answer": {"status": "…", "message": "…", "latex": "…"},
  "hints":  [{"code": "SIGN_ERROR", "message": "…", "step": 2}]
}
```

- `score`: correct 1.0, partial 0.5, otherwise 0.
- Step `error` = the step is wrong. `warning` = valid but risky (e.g. introduces extraneous
  roots). `unchecked` = ProofLab couldn't verify it either way (never counts against you).
- Standard combination rule (kinds may refine it):
  - unparseable answer → `invalid`
  - correct answer, no step errors → `correct`
  - correct answer with a step error → `partial` (`STEP_ERRORS`)
  - acceptable-but-incomplete answer (missing `+ C`, decimal instead of exact) → `partial`
  - no answer, all steps ok → `partial` (`NO_ANSWER`); otherwise → `incorrect`
  - wrong answer → `incorrect`
- When the verdict isn't `correct`, the response includes the next authored hint
  (`AUTHORED_HINT`), based on `hints_revealed` in the request.

### 4.2 Hints (`engine/hints.py`)

Hints are rule-based, identified by a stable `code` (UPPER_SNAKE) with a message template.
Core codes live in `hints.py`; topic modules register their own at import time. Generic
diagnostics run for every expression/number answer:

- `SIGN_ERROR` (answer = −key), `CONSTANT_FACTOR` (answer = k·key), `ADDITIVE_CONSTANT`
  (answer = key + c), `INEXACT` (decimal close to an exact key), `KNOWN_MISTAKE` (matches an
  authored mistake).

Hints must not reveal the answer outright.

### 4.3 Review status

| status | meaning |
|---|---|
| `draft` | written; answer key machine-verified by the test suite; **not yet checked by a person** |
| `reviewed` | a person checked prompt, key, hints and citation (`reviewer` + `reviewed_on` required) |
| `retired` | kept in the repo for history; never served by the API |

The API exposes `review.status` so the frontend can badge draft problems.

### 4.4 References

`content/references.json` is the book registry: `{id, title, authors, edition, publisher,
year, url, license, license_url}`. ProofLab never copies textbook text. Two citation modes:

- **Proofs course (MATH 123): exercise-mapped.** Every served problem *is* one *Book of Proof*
  exercise: same mathematical claim, restated in ProofLab's words, cited as
  `Chapter N exercises, #k (p. P)`. Nothing is invented. (The book is CC BY-NC-ND 4.0, so its
  wording is not reproduced and no modified version of it is shared.) The one exception is
  opt-in: in practice tests the student can ask for ProofLab-made versions with new numbers
  (§13.3). Those are generated on request, never stored as content, and always labelled
  "Made by ProofLab, not from the book".
- **Other courses: section-cited.** Problems are original; the citation points to the open
  textbook section that teaches the topic.

See `REFERENCES.md`.

## 5. Problem kinds

Each kind lives in one topic module, declares a `Params` model for `data`, a checker, and
(where possible) an independent SymPy computation used by the content tests to verify the
answer key.

### 5.1 Proofs — `topics/proofs/`

Structured direct proofs about integers. The student introduces representations, writes a
chain of equal expressions, and names an integer **witness**.

Step kinds: `let` (`n = 2k + 1`), `case` (`n = 3k + 1`, starts a case), `expr` (chain step),
`witness` (`2k^2 + 2k` or `m = 2k^2 + 2k`), `note` (free text, never checked).

| kind | module | data | checks |
|---|---|---|---|
| `parity_proof` | parity.py | `variables`, `hypotheses: [{var, is: even\|odd}]`, `target`, `goal: even\|odd` | `let` matches hypothesis (2k / 2k+1 with a fresh variable); every chain step equals the target under the substitutions; witness is an integer polynomial and `target = 2·w + r`; distinct fresh variables per hypothesis; cases (if used) are exhaustive |
| `divisibility_proof` | divisibility.py | `variables`, `hypotheses: [{var, divisor, remainder?}]`, `target`, `goal: {divisor, remainder?}` | same engine with modulus `d` (integer or symbol): `target = d·w + r` |
| `counterexample` | divisibility.py | `variables`, `domain`, `hypothesis`, `conclusion` (JSON predicates: `divides`, `prime`, `even`, `odd`, `eq`, `ne`, `lt`, `le`, `gt`, `ge`, `and`, `or`, `not`) | answer `a = 4, b = 2, c = 2` must be integers in the domain, make the hypothesis true and the conclusion false; only `expr`/`note` steps (unchecked) |
| `finite_set` | sets.py | Chapter 1 sets | (see the module) |
| `truth_table`, `logical_equivalence` | logic.py | Chapter 2 formulas | every row of the truth table (see the module) |
| `count` | counting.py | `{}`; `answer` is the count | answer is an exact nonnegative integer, typed as a number or an expression (`26^4`, `10!/(3! 7!)`, `binom(10, 3)`, the book's `P(10, 3)` / `C(10, 3)`); steps are evaluated and shown but not judged (a count has many routes); authored `mistakes` catch classic slips |
| `impossibility_proof` | contradiction.py | `variables`, `hypotheses: [{var, is} \| {var, divisor, remainder}]`, `target`, `divisor`, `forbidden`, `conclusion` | Chapter 6 contradiction proofs: the modular engine's `let`/`case`/`expr` steps plus `form` (`4(k^2 - b) + 2`): equal to the target, shaped `d·w + r` with `w` an integer polynomial, and `r ≠ forbidden`; it must be written factored, `(multiple of d)·(integer) + constant`, so the student shows the step that reveals the remainder; every case needs one |
| `existence` | contradiction.py | `variables`, `statement` (predicate) | answer values must make the statement true |
| `set_identity` | set_proofs.py | `sets`, `left`, `right`, `point` (`["x"]`, or `["x","y"]` for products), `universe` | Chapter 8: a chain of lines, each a set expression or an element-chasing statement (`x ∈ A or (x ∈ B and x ∈ C)`); every line is translated to a membership formula and must have the same truth table as the line before; complete when it ends at the right side (as a set, or as its membership statement: the two are the same statement) and shows work (an intermediate line, or membership unpacked into and/or/not) |
| `induction` | induction.py | `base`, and `sum: {index, term, start, rhs}` or `divides: {divisor, expr}` | Chapter 10: `base` (numbers only, must equal the statement at n = base), `assume` (the statement for n = k; for divisibility `f(k) = d·m`), `expr` chain equal to the n = k + 1 case (for a sum, one line must be rhs(k) + term(k + 1), found by matching its terms), `witness` for divisibility (`f(k+1) = d·w`, w a polynomial in k and m that is an integer at every integer point, like `m + k(k + 1)/2`, proved exactly from its values on a small grid); validation re-derives the sum with SymPy |

Proof verdict: `correct` when every step is valid and every case ends with a valid witness
over exhaustive cases (a valid witness proves the claim even if a hypothesis was never
introduced); `partial` when valid but unfinished, including missing cases; `incorrect` when
any step is wrong. The verdict's `answer` slot carries the conclusion message
(`PROOF_COMPLETE`, `PROOF_INCOMPLETE`, `PROOF_HAS_ERRORS`). A `let`/`case` may introduce any
new single letter as an integer variable. Witnesses must use the goal's standard remainder
(0 ≤ r < d), so `2w − 1` for "odd" is rejected; nested cases are not supported.

Hint codes include `SAME_FRESH_VARIABLE`, `BAD_REPRESENTATION`, `WITNESS_NOT_INTEGER`,
`WITNESS_MISMATCH`, `CASES_NOT_EXHAUSTIVE`, `MISSING_LET`, `PROOF_INCOMPLETE`.

Congruence follows *Book of Proof* Definition 5.1: `a ≡ b (mod n)` means `n | (a − b)`, so a
hypothesis `{var: a, divisor: n, remainder: b}` with a symbolic modulus is introduced as
`a = nk + b`. A contrapositive proof (Chapter 5) is checked as a direct proof of the
contrapositive statement; the prompt says so.

Current content: 192 problems for Chapters 1–10, all `math123`, tagged `book-of-proof` and
`chN`, each mapped to one book exercise (or one part, or one direction of an iff) and cited:

| Ch. | Topic | Problems | Exercises |
|---|---|---|---|
| 1 | Sets | 65 | Sections 1.1–1.8 (`finite_set`) |
| 2 | Logic | 25 | every exercise of Sections 2.5 and 2.6 |
| 3 | Counting | 23 | Sections 3.2–3.5, 3.7, 3.8 (keys brute-force verified) |
| 4 | Direct proof | 12 | 1–7, 10, 11, 14, 15, 19 |
| 5 | Contrapositive | 10 | 1, 2, 12, 15, 17, 18, 20, 21, 23, 24 |
| 6 | Contradiction | 9 | 1, 2, 6, 7, 8, 10, 11, 17, 18 |
| 7 | Non-conditional | 16 | 1–5 (each iff as two directions), 10, 17, 19, 20, 24, 27 |
| 8 | Proofs involving sets | 11 | 8–18 |
| 9 | Disproof | 7 | 2, 3, 4, 11, 12, 25, 28 |
| 10 | Induction | 14 | 1–13, 15 |

Not yet checkable (they get a later kind or the planned AI feedback, never an AI verdict):
irrationality proofs (6.3–6.5, 6.9), statements whose hypothesis is about an expression
(7.13, 7.16, 7.23), "or" conclusions (7.22), induction inequalities (10.16, 10.19, 10.21,
10.22), and the English-translation sections of Chapter 2. The 12 earlier invented problems
are `retired`.

### 5.2 Precalculus — `topics/precalc/`

| kind | module | answer | checks / hints |
|---|---|---|---|
| `expression` | functions.py | expression | equivalence; optional `form`: `expanded`, `factored`, `single_fraction`, `exact` (compositions, difference quotients, simplification, exact values) |
| `inverse_function` | functions.py | expression in x | `f(g(x)) = x` and `g(f(x)) = x`; `RECIPROCAL_NOT_INVERSE` |
| `domain` | functions.py | interval notation / inequalities | set equality; `ENDPOINTS` when only boundary points differ |
| `trig_identity` | trig.py | — (steps only) | each step equals the previous; chain starts at LHS and ends at RHS |
| `trig_equation` | trig.py | solution set on an interval (default `[0, 2π)`) | per-step solution-set preservation; `DEGREES_NOT_RADIANS`, `MISSING_SOLUTIONS`, `EXTRA_SOLUTIONS` |
| `log_rewrite` | exp_log.py | expression | equivalence (variables positive) + form `expanded`/`condensed` |
| `equation` | exp_log.py | solution set over ℝ | lost solutions (`LOST_SOLUTION`, error), extraneous (`EXTRANEOUS_SOLUTION`, warning on steps / error in the final answer) |

Solution sets are written `x = 2 or x = -3`, `x = 2, x = -3`, `{2, -3}`, `2, -3`, or
`no solution`.

Details:
- `expression` also supports forms `lowest_terms` and `cancel` (with `cancel_var`: a
  difference quotient no longer divides by h), and data `compose: [f, g]`,
  `difference_quotient: f`, and `forbid: [...]` (raw-text patterns the answer may not contain,
  because SymPy evaluates `sin(4pi/3)` to `-√3/2` while parsing).
- `trig_identity` accepts a final step equal to the other side using only algebra and the
  definitions of tan/sec/csc/cot (real identities must still be applied in the steps). A
  one-step "proof" is `partial` (`IDENTITY_NO_WORK`). Working right-to-left is accepted.
- `inverse_function` takes `domain` and `range` sampling specs (`real` or `real[a, b]`).
- `FORM_NOT_EXPANDED` can't see `4(x²+x+1)`: SymPy distributes numeric factors while parsing.

### 5.3 Calculus 1 — `topics/calc1/`

| kind | module | answer | checks / hints |
|---|---|---|---|
| `limit` | limits.py | value, `oo`, `-oo`, `DNE` | steps must be algebraic rewrites (or `lhopital` steps); `LHOPITAL_NOT_INDETERMINATE`, `LHOPITAL_WRONG_DERIVATIVE`, `INDETERMINATE_IS_NOT_DNE`, `ONE_SIDED_ONLY` |
| `derivative` | derivatives.py | expression | each step equals f′; `PRODUCT_RULE`, `QUOTIENT_RULE`, `CHAIN_RULE` detectors |
| `tangent_line` | derivatives.py | `y = mx + b` | `SLOPE_ONLY`, `WRONG_SLOPE`, `WRONG_POINT` |
| `implicit_derivative` | derivatives.py | expression in x, y | compared on points of the curve |

### 5.4 Calculus 2 — `topics/calc2/`

| kind | module | answer | checks / hints |
|---|---|---|---|
| `antiderivative` | integrals.py | `F(x) + C` | `d/dx` of every step and the answer equals the integrand; steps may use `int(…)`, a `sub` step (`u = g(x)` or `x = g(t)`); `MISSING_C`, `LOG_ABS` |
| `definite_integral` | integrals.py | exact value | antiderivative steps + value steps; `BOUNDS_NOT_CHANGED`, `INEXACT` |
| `series_convergence` | series.py | `converges` / `diverges` (optionally `absolutely` / `conditionally`) | `test` step names the test, `limit` step its limit, `compare` step a comparison series; `DIVERGENCE_TEST_INCONCLUSIVE`, `RATIO_TEST_INCONCLUSIVE`, `WRONG_TEST_LIMIT` |
| `series_sum` | series.py | exact value | `START_INDEX` for geometric series |
| `taylor_polynomial` | series.py | polynomial | `MISSING_FACTORIALS`, `WRONG_CENTER` |

Details:
- Integral steps are checked by differentiating them (never `integrate()` on student input).
  `sub` steps are `u = g(x)` (forward), `x = g(t)` (inverse) or a differential `du = 2x dx`
  (checked against g′). One substitution per attempt. `C`, `K` and `c` count as `+ C`.
- `definite_integral` accepts `diverges` for divergent improper integrals.
- `series_convergence` steps: `test` (ratio, root, divergence, p-series, geometric, integral,
  comparison, limit comparison, alternating), `limit` (the test's limit; for p-series it is
  p, for geometric it is r), `compare` (bₙ), `note`. For mixed-sign series, the p-series,
  integral and comparison tests run on |aₙ| and decide absolute convergence only
  (`SERIES_ABS_DIVERGES_ONLY`). Comparison inequalities are checked numerically at sample n.
- `series_sum` reads a step containing `N` as a partial-sum formula and checks it against
  direct sums.

### 5.5 Calculus 3 — `topics/calc3/`

| kind | module | answer | checks / hints |
|---|---|---|---|
| `partial_derivative` | partials.py | expression | `WRONG_VARIABLE`, `NOT_CONSTANT` |
| `gradient` | partials.py | vector `<a, b>` | component-wise; `COMPONENTS_SWAPPED` |
| `directional_derivative` | partials.py | value | `NOT_UNIT_VECTOR` |
| `tangent_plane` | partials.py | plane equation | compared as planes (scalar multiples allowed) |
| `iterated_integral` | multiple_integrals.py | exact value | inner-integral steps |
| `integral_setup` | multiple_integrals.py | `int(int(f, y, a, b), x, c, d)` | region compared by moments (∫1, ∫x, ∫y, …), required order/coordinates; `MISSING_JACOBIAN` |

Details: `gradient` can be evaluated at a point (`at`); `tangent_plane` takes `function`
(z = f(x, y)) or a level `surface`; `partial_derivative` steps may pass through the
intermediate partials in order (f_x then f_xy); `integral_setup` allows `note` steps and is
2-D (cartesian or polar) with finite bounds. Student integrals are evaluated with a 48-point
Gauss–Legendre rule, never symbolic `integrate`.

### 5.6 Calculus 4 — `topics/calc4/`

| kind | module | answer | checks / hints |
|---|---|---|---|
| `divergence` | vector_calc.py | expression | `CURL_NOT_DIV` |
| `curl` | vector_calc.py | vector | component-wise; `CURL_SIGN` |
| `potential_function` | vector_calc.py | f, or `not conservative` | ∇f = F up to a constant |
| `line_integral` | vector_calc.py | exact value | `MISSING_DERIVATIVE` (forgot r′(t)) |
| `ode_solution` | diff_eq.py | `y = …` (explicit or implicit) | substitution into the ODE; number and independence of constants for general solutions; initial conditions; `IC_NOT_SATISFIED`, `NOT_GENERAL`, `DEPENDENT_SOLUTIONS` |

Details: `ode_solution` step kinds are `expr` (candidate solutions, labels `y_h =`/`y_p =`
allowed), `characteristic` (characteristic equation), `roots` (accepts `±` and `i`) and
`note`. `NOT_GENERAL`, `DEPENDENT_SOLUTIONS` and `CONSTANTS_LEFT` give `partial`;
`IC_NOT_SATISFIED` and `NOT_A_SOLUTION` give `incorrect`. Implicit answers are first-order
only, with the constant appearing linearly. Answer constants: `C`, `C1`, `C2`, `A`, `B`, `K`.
`curl` is 3-D only. In `potential_function`, a step that matches only some components is a
`warning`.

## 6. Equivalence

- Primary test is **numeric**: both expressions are evaluated (mpmath, 30 digits) at
  seeded-random points drawn from each variable's declared domain (`real`, `positive`,
  `integer`, `nonnegative`, or an explicit sampling interval). Points where either side is
  undefined or non-real are skipped; a single mismatch means "not equivalent". At least four
  agreeing points are needed; otherwise fall back to `simplify(a − b) == 0`, otherwise
  "unknown" (→ `unchecked`).
- The seed is fixed, so verdicts are reproducible.
- Exact-form requirements (`exact`, `factored`, …) are separate structural checks on top of
  equivalence.

## 7. HTTP API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | `{status, version, problems}` |
| GET | `/courses` | course tracks with topics and problem counts |
| GET | `/problems` | summaries; filters `course`, `topic`, `kind`, `tag`, `difficulty`, `status` |
| GET | `/problems/{id}` | public problem: prompt, answer format, syntax help, citation (resolved), review, hint count |
| GET | `/problems/{id}/solution` | worked solution + answer key |
| POST | `/check` | `{problem_id, steps, answer, hints_revealed}` → Verdict |
| GET | `/read` | what this server can read: `{images, pdf, documents, text}` (§14) |
| POST | `/read` | raw file bytes (photo, PDF, document, text; optional `X-Filename`) → `{kind, engine, pages, lines, text}` (§14) |
| GET | `/practice-tests` | a practice midterm, final or quiz (§13); params `course`, `kind` (`midterm`/`final`/`quiz`), `seed`, `topics` (comma-separated), `length` (1–30), `style` (`written`/`mixed`/`choice`), `variants` (bool), `weights` (`topic:1.5,…`), `prefer` (problem ids) |
| POST | `/quiz/answer` | `{problem_id, seed, format, choice}` → `{correct, correct_choice, explanation, solution}` (§13.2) |
| GET | `/cards` | a course's flashcards; params `course`, `topics`, `parts` (`concepts`, `problems`) (§15) |
| POST | `/cards/from-notes` | `{text}` → draft cards found by the notes rules, each with the rule that found it (§15.2) |
| GET | `/store` | the student's saved progress: reviews, best verdicts, notes decks, test records (§17) |
| POST | `/store` | `{ops: [...]}`: a batch of changes from a browser, applied in one transaction (§17) |

- Retired problems are never listed and return 404.
- `/practice-tests` returns 404 when the course or topics have no problems to build from.
- Errors: 404 unknown problem, 422 malformed request, 503 when too many checks are already
  running.
- CORS origins from `PROOFLAB_CORS_ORIGINS` (comma-separated; default
  `http://localhost:3000`).
- Settings: `PROOFLAB_CHECK_TIMEOUT` (seconds, default 10), `PROOFLAB_ISOLATE` (`1`/`0`,
  default 1), `PROOFLAB_MAX_CONCURRENT_CHECKS` (default 4), `PROOFLAB_DB` (the progress
  database file, §17).

## 8. Content rules

1. One problem per JSON file under `content/problems/<course>/` (calc4 is split into
   `vector_calc/` and `diff_eq/`).
2. Proofs-course problems must map to one *Book of Proof* exercise (§4.4) and may not be
   invented. Problems in other courses are original and cite the section that teaches them.
3. Every problem has **at least one example that is `correct`** and **at least one that is
   not**, each with the expected `status` (and optionally `first_error` step index and
   `hint_codes` that must appear). `tests/test_content.py` runs every example.
4. Where the kind supports it, the answer key is re-derived independently with SymPy and must
   match.
5. New problems start as `draft`. Moving to `reviewed` requires a person to check the prompt,
   key, hints and citation, and to fill `reviewer` + `reviewed_on`.

## 9. Testing

```
tests/
├── engine/test_algebra.py      parser, safety limits, equivalence, sets
├── engine/test_checker.py      dispatch, verdict combination, isolation/timeout
├── engine/topics/<course>/     one test file per topic module
├── api/test_routes.py          endpoints, no answer leakage, filters, errors
└── test_content.py             every problem: schema, reference, review, key, examples
```

`uv run pytest` must pass before any change lands. The Docker image has a `test` target that
runs the suite on Python 3.12. The website's XP rules (§19) have their own unit tests:
`npm test` in `frontend/` (Node's built-in runner, no extra packages).

## 10. Roadmap

1. ~~**Next.js frontend**~~ (done: `frontend/`). Next: live LaTeX preview while typing, which
   needs a small `/parse` endpoint.
2. MATH 123 = all of *Book of Proof*: follow the chapter plan in §11.
3. More kinds as courses need them: induction proofs, linear algebra (row reduction,
   eigenvalues), probability, physics-style unit checks.
4. Attempt history and spaced repetition (frontend-side first). Practice tests (§13) are the
   first piece: their scores stay in the browser.

## 11. Book of Proof coverage plan (MATH 123)

MATH 123 covers all 14 chapters. The goal is one ProofLab problem per *Book of Proof* exercise
that can be checked **deterministically**. Exercises that can't be (free-form arguments like
Cantor's diagonal proof) get the planned AI *feedback* (§12), never an AI verdict.

Before adding chapters, the proofs course needs one structural change: problem `topic`s
should be the book's chapters (`sets`, `logic`, `counting`, `direct`, `contrapositive`,
`contradiction`, `nonconditional`, `set-proofs`, `disproof`, `induction`, `relations`,
`functions`, `calculus-proofs`, `cardinality`) instead of engine module names. That means
decoupling content topics from topic modules (a course outline file listing each course's
topics), so one engine module can serve several chapters.

| Ch. | Topic | Checkable now? | New kind(s) needed | How it's checked |
|---|---|---|---|---|
| 1 | Sets | **yes** | `finite_set` | compute ∪, ∩, −, complement, ×, power sets, set-builder sets over finite or bounded universes; compare as sets |
| 2 | Logic | **yes** (2.5, 2.6) | `truth_table`, `logical_equivalence`; `negation` later | evaluate formulas on every row; each rewrite step must be equivalent (truth table); negations checked by equivalence after normalising quantifiers over a small model |
| 3 | Counting | **yes** | `count` | numeric answer; steps are arithmetic/binomial expressions; answer keys verified by brute-force enumeration in tests |
| 4 | Direct proof | **partly** (12 exercises) | pair-of-variables cases ("same parity"), non-divisibility goals (r ∈ {1,…,d−1}), real inequalities | extend the modular engine; inequality chains checked step by step |
| 5 | Contrapositive, congruence | **partly** (10 exercises) | disjunctive hypotheses ("x even or y odd"), gcd facts | split into cases; gcd via SymPy |
| 6 | Contradiction | **yes** (integer exercises) | `impossibility_proof` | show the expression always leaves a remainder other than the forbidden one (every case ends with a `form` step) |
| 7 | Non-conditional statements | **yes** (parts) | `existence`; each iff as two problems, one per direction | existence: supplied witness values are checked by evaluating the predicate |
| 8 | Proofs involving sets | **yes** (identities) | `set_identity` | set expressions as Boolean algebra; each step must be an equivalent set expression |
| 9 | Disproof | **partly** (7 exercises) | counterexamples with sets and reals | evaluate the statement on the supplied finite sets / values |
| 10 | Induction | **yes** (sums, divisibility) | `induction` | base case evaluated; inductive step is an algebra chain from P(k+1) that must use P(k) (SymPy checks each step and the substitution) |
| 11 | Relations | no | `relation_properties`, `equivalence_classes` | finite relations: reflexive/symmetric/transitive computed; partitions compared as sets of sets; ℤₙ arithmetic |
| 12 | Functions | no | `injectivity_proof`, `finite_function` | f(a) = f(b) ⟹ a = b as a checked equation chain; finite functions decided directly; composition and inverse reuse precalc kinds |
| 13 | Proofs in calculus | no | `epsilon_delta` | student gives δ(ε); check |x − a| < δ ⟹ |f(x) − L| < ε symbolically where possible, else on dense sampled ε |
| 14 | Cardinality | no | `bijection` | student gives f; injective and surjective checked symbolically (with numeric fallback) on ℕ/ℤ |

Order of work (proposal): 1 → 2 → 10 → 6–8 → 3 → 11–12 → 13–14, interleaved with filling in
the remaining Chapter 4/5/9 exercises the current engine can almost handle.

## 12. Planned: local LLM assistant (Ollama) — not wired yet

Decided with the user on 2026-11-06: all four roles below, small local model. Nothing here is
implemented; this section is the design to agree on before wiring.

### Principles

1. **The checker is the only judge.** The assistant never sets `status`, `score`, step
   statuses or hint codes. Everything it writes is labeled **AI** in the UI, with the model name.
2. **Grounded, not invented.** Each request carries only: the problem (prompt, kind, citation),
   the deterministic verdict JSON, the authored hints already shown, and the text of the cited
   *Book of Proof* section. The system prompt forbids facts or problems from outside that
   material and requires citing the section.
3. **Optional and local.** ProofLab works fully with the assistant off. The model runs in
   Ollama on this Mac; no data leaves the machine.
4. **No answer leaks.** Before the solution is revealed, a deterministic guard parses math in
   the model's output with ProofLab's own parser and drops any reply containing an expression
   equivalent to the answer key or a witness, then retries once.

### Roles

| Role | Endpoint | Input | Output |
|---|---|---|---|
| Explain verdict | `POST /assist/explain` | problem id, submission, verdict | plain-language explanation of what the checker found |
| Tutor chat | `POST /assist/chat` | problem id, short message history | Socratic replies grounded in the cited section |
| Read English proofs | `POST /assist/proof-feedback` | problem id, free-form proof text | structured feedback (`issues[]`, `suggested_steps[]`) labeled "AI feedback, not a verdict"; for checkable kinds it suggests the ProofLab steps to enter |
| Extra hints | `POST /assist/hint` | problem id, submission, hints shown | one more hint, only after the authored hints run out |

Responses stream (server-sent events) so a slow small model still feels responsive.

### Components

- `backend/src/prooflab/assist/ollama.py`: minimal client for Ollama's `/api/chat`
  (timeouts, streaming, health check).
- `assist/prompts.py`: one template per role.
- `assist/grounding.py`: deterministic retrieval. Citations already give chapter and
  exercise, so the cited section's text is looked up by number (no embeddings). The text is
  extracted locally from the user's own PDF into a **gitignored** cache
  (`backend/.cache/book-of-proof/sections.json`) and never committed or served raw.
- `assist/guards.py`: answer-leak check (uses `algebra.equivalent`), length limits, refusal
  on off-topic requests.
- `api/assist.py`: the four endpoints, behind `PROOFLAB_ASSIST=1`, with their own
  concurrency limit (one generation at a time on 8 GB RAM).
- Frontend: "Explain this" under a verdict, a chat drawer on the problem page, a "Write it in
  English" tab on proof problems, and "Ask for an AI hint" once authored hints run out.
- Tests: a fake Ollama server; leak-guard and grounding tests; no network in CI.

### Model and setup

- Hardware: Apple M2, 8 GB RAM. Target a ~3–4B instruction model (≈2–3 GB, 4-bit), context
  4–8k. The exact tag is chosen when wiring, by running a small evaluation set built from
  ProofLab's own verdicts (does it stay grounded, avoid leaking, explain the hint code?).
- Prerequisites: at least 6 GB of free disk (Ollama plus the model plus headroom), then
  `brew install ollama` (or the Ollama app) and `ollama pull <model>`.
- Settings: `PROOFLAB_ASSIST` (`0`/`1`, default `0`), `PROOFLAB_OLLAMA_URL`
  (default `http://localhost:11434`), `PROOFLAB_OLLAMA_MODEL`.

The repo tutor's lesson notes (§20) are a ready source of grounding text in ProofLab's own
words, which may replace extracting the book's section text.

### Open questions (to settle before wiring)

1. May the cited *Book of Proof* section text be extracted from your PDF into the gitignored
   local cache for grounding?
2. Should chat history persist (browser only) or reset each visit?
3. Is the "Read English proofs" feedback shown for every proofs problem, or only ones the
   checker can't verify (most of Chapters 6–8, 10–14 today)?

## 13. Practice tests (midterms, finals and quizzes)

A practice test is a set of problems picked by a fixed algorithm
(`backend/src/prooflab/practice.py`) and checked by the same rules as practice mode. By default
every question is a problem already in the bank. The student can opt in to ProofLab-made
versions with new numbers (§13.3); those are always labelled "Made by ProofLab, not from the
book", so the "invent nothing" rule still holds for anything presented as the book's.

Kinds: **midterm** (first half of the chapters, 8 questions), **final** (every chapter, 12) and
**quick quiz** (every chapter, 10, multiple choice by default).

### Algorithm

1. **Scope.** A final covers every topic of the course that has problems; a midterm covers the
   first half of them in course order, rounded up. An explicit `topics` list replaces either.
2. **Length.** Midterm 8 questions, final 12, unless `length` says otherwise; never more than
   the problems available, and never more than 30.
3. **Allocation.** Every topic in scope gets one question; the rest are shared in proportion to
   each topic's size (largest-remainder rounding, capped by what the topic has). With fewer
   questions than topics, the topics used are spread evenly through the course.
4. **Inside a topic.** Aim for easy : medium : hard = 3 : 5 : 2, falling back to what exists,
   and rotate through problem kinds so one kind doesn't repeat while others are available.
5. **Order.** Topics in course order; inside a topic, easier first, then the bank's order.
6. **Determinism.** A seeded `random.Random(course|kind|seed|topics|length)` makes every choice,
   so the same URL always rebuilds the same test (retake it, or share it). The test id is
   `<kind>-<first 10 hex of sha1(key)>`.
7. **Timing.** Suggested minutes = 5, 8 and 12 per easy, medium and hard question, rounded up
   to a multiple of 5. It's a guide, not a time limit.

### Taking a test (frontend)

> **Removed from the website on 2026-11-08** (§21). This describes the practice site as it
> was up to commit `0eb0d0f`; the backend parts still work.

- `/tests` builds a test: course, midterm or final, chapters, number of questions. Each start
  picks a fresh random seed. Course pages link straight to the default midterm and final.
- `/tests/<course>/<kind>?seed=&topics=&length=` runs it. In exam mode the workspace has no
  Check button, hints or solutions. Drafts save in the browser under a test-specific key, so
  they never mix with practice drafts.
- **Submit test** grades every question in one server action (one `/check` per question,
  `hints_revealed: 0`). Blank questions score 0 and are labelled as blank. Score = 1 per correct
  question, 0.5 per partly-right one, shown overall and by chapter, with the time taken.
- After submitting, answers lock and each question shows its graded steps and offers its worked
  solution. **Retake these questions** clears the drafts and the clock; **New test, same
  settings** draws a new seed. Results, history and progress marks are saved in the progress
  database (§17) and shared by every device; answer drafts stay in the browser.

### 13.1 Self-tuning tests ("focus on my weak spots")

The browser keeps a per-chapter skill rating from every checked attempt (§15.3). When the
student ticks "Focus on my weak spots", the builder turns it into URL parameters, so the test
is still reproducible from its link:

- `weights`: chapter multiplier `0.5 + 2.5 × (1 − mastery)`, where mastery is the predicted
  chance of getting a medium problem right; untried chapters get 1.5. Every chapter in scope
  still gets one question; weights only move the extra ones (step 3 above).
- `prefer`: up to 20 problems due for review (most overdue first). They're picked first inside
  their chapter's quota.

"New test, same settings" recomputes both from the latest results, so the next test adapts.

### 13.2 Multiple choice (no AI)

`backend/src/prooflab/quiz.py` builds two formats. **Answer**: "Which of these is the answer?"
The right choice is the key. Wrong choices come from, in order: the problem's authored
`mistakes`; small slips of the key (a number off by one or doubled, a sign flipped, `sin`↔`cos`,
one or two truth values flipped, a set element dropped or added, order vs. no order and
repetition vs. none for counts, `C`↔`P`); answers of sibling problems of the same kind.
**Each candidate is run through the problem's checker and kept only if the verdict is
incorrect**, and duplicates by rendered LaTeX are dropped; fewer than two survivors means no
question. **Spot**: "Here is an attempt. Where does it first go wrong?" The attempt is one of the
problem's tested examples (mostly flawed ones, sometimes a correct one so "No mistake" is a real
option); the checker's first error step is the right choice and its message the explanation.

Questions are deterministic in `(problem, seed)`; the right key never leaves the server. The
student's choice is graded by `POST /quiz/answer`, which rebuilds the question. A wrong pick
shows the hint for that mistake (authored, or the checker's own hint), and every question shows
the worked solution. **mixed** style makes about half the questions multiple choice. Problems
that can't produce a safe question stay written. In the bank, 254 of 272 problems produce one.

### 13.3 ProofLab-made versions (opt-in)

With `variants` on, about three in four of the picked problems that have a generator are
swapped for a version (77 of the 272 problems are supported: parity proofs, truth tables, simple
finite sets, induction sums, and derivative, integral, limit, gradient, divergence, curl,
tangent-line, geometric-series and second-order ODE problems).
`backend/src/prooflab/variants.py` makes a new version of a problem with different numbers:
same kind, structure and difficulty, new coefficients, bounds or formulas, with the answer key
recomputed by SymPy (or the propositional / finite-set engines), a worked solution and two
examples. Each version is **self-verified before it's used**: the model validates, the kind's
`validate` and `verify_key` pass, and the checker gives each example its expected verdict.
Ids are `<base id>-v<seed>`, so a version is rebuilt from its id anywhere (`/problems/{id}`,
`/check`, `/quiz/answer`). Versions carry the tag `prooflab-variant`, the citation of the
exercise they're based on with the note "ProofLab-made version with new numbers; not an
exercise in the book", and `variant_of` in the API. The study model files their results under
the base problem.

### Search

> **Removed from the website on 2026-11-08** (§21). This describes the practice site as it
> was up to commit `0eb0d0f`; the backend parts still work.

The navbar search (`/` or ⌘/Ctrl + K) finds topics, problems, practice tests and help pages.
Its index comes from `/courses` and `/problems` through a server action, loaded the first time
the dialog opens. Matching is plain: every word of the query must appear in the entry's name,
details or keywords (course names, chapter numbers like "ch 4", tags); topics rank first, then
tests, pages and problems.

## 14. Scanning work (camera, photos, PDFs, documents)

Students can photograph handwritten work or pick a photo, PDF or document; ProofLab reads it
into lines of text, the student corrects the text, and the lines become steps. **Reading is
transcription only.** Nothing is checked until the student presses Check, and every verdict
still comes from the deterministic checkers.

- **Backend** (`backend/src/prooflab/reader.py`, `POST /read`): everything runs on the machine
  running ProofLab, nothing is sent elsewhere.
  - Photos and scans, handwriting or print: Apple Vision's on-device text recognizer (the
    engine behind Live Text), accurate mode, language correction off (it "fixes" math into
    words). Lines are ordered top to bottom.
  - PDFs: each page's text layer (PDFKit) when it has one, otherwise the page is rendered at
    144 dpi and read with Vision. At most 10 pages.
  - Word, RTF, ODT, HTML: macOS's `textutil`. Plain text (`.txt`, `.md`, `.tex`): decoded.
  - Limits: 15 MB per file. On non-macOS hosts (the Docker image) only text files can be read
    and `GET /read` says so; the website explains instead of failing.
- **Website** (removed on 2026-11-08, §21; in git history up to `0eb0d0f`): a "Scan work" button in the step editor (practice and exam mode) opens a dialog
  with a live camera and Capture button (falling back to the phone camera through the file
  picker), "Choose a file", drag and drop, and paste. Photos are shrunk to 2200 px and turned
  the right way up in the browser. `/api/read` proxies to the backend.
- **Tidying before review**: superscripts become `^2`, `−`/`×`/`÷` become `-`/`*`/`/` (× stays
  in set problems), "Letn" gets its space back, and in kinds whose variables are lowercase a
  capital letter becomes lowercase when that lowercase letter appears elsewhere on the page
  (K → k). Each line becomes a step; "Let", "Case", "Base case", "Assume", "Witness" pick the
  step kind when the problem has it, and wordy lines become notes. "Use last line as the
  answer" fills the answer box.
- Exponents are the hardest part of handwriting to read: the caret comes back as `~`, merges
  into the letter as an accent (`á 2`), or vanishes (`a 2`). Outside logic and set problems
  (where `~` means "not") these are restored to `a^2` when they follow a single letter or a
  closing bracket. Cyrillic look-alikes (а, е, о, к, х, …) become Latin letters.
- The camera stream is attached after the preview renders, and Capture stays disabled until
  frames arrive. Tested end to end in headless Chrome with a fake camera (a photo-like page of
  handwriting-font work on lined paper): preview, capture, read, review, steps, verdict.
- Handwriting is read imperfectly (k vs K, 2 vs z, a vs 0, missing `^`), which is why the
  student always reviews the text first. A stronger reader (for example a local vision model) would
  fit §12's plan, still as transcription only.

## 15. Flashcards (no AI)

> **The website side was removed on 2026-11-08** (§21): `/cards` and the study model in
> `frontend/src/lib/learn.ts` are in git history up to commit `0eb0d0f`. The backend's decks and
> cards still work, and the tutor uses the concept cards (§20).

`/cards` on the website; `backend/src/prooflab/cards.py` and `notes.py`; the study model is
`frontend/src/lib/learn.ts`.

### 15.1 Decks from ProofLab's content

- **Concept cards** in `content/cards/<course>.json`: definitions, notation, theorems and facts.
  For MATH 123 there are 98 cards across Chapters 1–10, restated in ProofLab's words and cited
  to the section and page, like the problems. The front is the term (or the theorem's name), the
  back says what it means **without repeating the term**, so the same card works as a quiz
  question. Loading validates them like problems: ids `<course>.<topic>.<slug>`, known topics
  and books, fronts unique per chapter, no em dashes.
- **Problem cards**: every served problem, statement on the front, worked solution on the back.
- A session shows cards due for review first (most overdue first), then up to 20 new ones.
  Grades are Again / Hard / Good / Easy, each button showing when the card would come back.
  "Again" brings the card back later in the same session.
- **Quiz me**: multiple choice over the concept cards ("Which term is this?"), wrong choices
  from other terms in the same chapter first.

### 15.2 Cards from the student's notes

Pasted text, or a photo, PDF or document read by the §14 reader, goes to
`POST /cards/from-notes`. Lines broken by a page or a photo are joined, then written rules look
for: `Q:`/`A:` pairs; `Definition 4.1 (Term): …` and `Theorem … (Name) …` (also Lemma,
Corollary, Proposition, Principle, Law, Rule, Axiom, Fact); `Term: meaning`, `Term :: meaning`,
`Term - meaning`; `Name = formula`; and sentences such as "X is defined as …", "… is called X",
"A X is a …", "X means …", "We say … if …", "An integer n is X if …". Labels such as "Note:" or
"Example:" are skipped, duplicates are dropped, and each card says which rule found it. The
student edits, deletes or adds cards before saving. Notes decks live only in the browser.

### 15.3 The study model that learns from the student's answers

Computed in the browser (`lib/learn.ts`) from the review log, which is saved in the progress
database (§17), so every device gets the same model.

- **Scheduling**: FSRS-4.5 (published, deterministic). Each item (concept card, problem, notes
  card) has a stability S and difficulty D, updated by the grade. A card is due when the
  predicted chance of remembering it, `R(t) = (1 + 19/81 · t / (k·S))^-0.5`, falls to 90%.
- **Training**: `k` is a personal memory factor fitted to every past review by minimising log
  loss (golden-section search on log k between 0.2 and 5) once there are 12 repeat reviews. It
  is refitted after every review, so the schedule tracks how fast this student forgets. The
  flashcards page reports k and how much better it predicts than the starting model.
- **Problems count too**: the first check of a problem on a visit (practice) and every test
  answer becomes a review (correct with no hints = Good, with hints or partly right = Hard,
  wrong or blank = Again), and updates the chapter's Elo-style skill rating used by §13.1.
- "Start the schedule over" forgets everything, after a confirmation.

## 16. Phone layout

> **Removed from the website on 2026-11-08** (§21). This describes the practice site as it
> was up to commit `0eb0d0f`; the backend parts still work.

Below the `sm` breakpoint (640 px) the top bar keeps the Σ mark, Search and a hamburger button
labelled **Menu**. It opens a side sheet (native `<dialog>`, closes on Close, Esc, a link or a
tap on the backdrop) with Practice, Flashcards, Tests and Progress (with today's XP beside it),
every course, and Typing math, the current page marked. There is no bottom bar. Every control is at least 44 px tall, keyboard hints
("Enter adds a step", "Space") are hidden on touch screens, and the step editor's remove button
stays visible on touch screens (hover-only on desktop). From `sm` up the single top bar lists
every course plus Flashcards, Tests and today's XP (a link to Progress; the streak shows from
`md` up).

## 17. Progress database (SQLite)

One student, no accounts, no Postgres. `backend/src/prooflab/store.py` keeps the student's
progress in one SQLite file: by default `~/Library/Application Support/ProofLab/prooflab.sqlite3`
on macOS (deliberately outside the iCloud-synced Desktop, which would offload or corrupt a live
database), `~/.local/share/prooflab/prooflab.sqlite3` elsewhere, or `PROOFLAB_DB`. It is opened
on first use, in WAL mode; serving problems never touches it. Tests point `PROOFLAB_DB` at a
temporary file.

| Table | Holds | Merge rule |
|---|---|---|
| `reviews` | every grade of a card or problem: `uid, item, kind, course, topic, difficulty, grade, at` | append-only, idempotent by `uid`; `reset_reviews` clears it |
| `progress` | best verdict per problem | only goes up (invalid < incorrect < partial < correct) |
| `decks` | notes decks with their cards (JSON) | newest `updated_at` wins; deletes leave a tombstone |
| `tests` | practice-test records (start, submit, score, results) | newest `updated_at` wins; deletes leave a tombstone |
| `activity` | what can earn XP (§19): `uid, type, day, at, item, course, topic, data` (JSON facts, never XP) | append-only, idempotent by `uid`; `reset_activity` clears it, and events from before a reset are refused |

Problems and concept cards stay JSON content files (§4, §15.1); answer drafts stay in each
browser.

**Sync** (removed with the practice site on 2026-11-08, §21; the `/store` endpoints remain but
nothing in the repo calls them now). Each browser kept its own copy (localStorage) so pages stay instant and work
offline. Every change is also queued in an outbox (`lib/outbox.ts`); the sync agent
(`lib/sync.ts`, mounted in the layout) sends the queue to `POST /api/store` (proxied to the
backend) a moment after a change, on load, when the tab becomes visible, when the network
returns, and every 30 s. After the database confirms a batch, exactly the changes that were
sent leave the queue (matched by content, not position), so a reset queued while a batch was in
flight is never lost. Once the queue is empty it pulls `GET /store` and merges: reviews and XP
activity by union (events made before a recorded reset, `reviews_reset_at` or
`activity_reset_at`, are dropped, which is how a reset reaches other devices; anything else the
database lacks is sent again), verdicts by rank, decks and tests by `updated_at` and
tombstones, never overwriting anything still in the queue. The first sync on a browser sends everything it had
from before the database existed.

**The study model is rebuilt from the review log.** `lib/learn.ts` replays the reviews in time
order: FSRS state per item (standard curve), the review log for the fit, and the chapter skill
ratings. The personal factor k is then fitted once and applied to every due date, so a better
fit reschedules everything. Same log, same model, on every device.

Verified with two headless browsers (phone and laptop sizes) against a throwaway database:
reviews and a notes deck made on the phone appear on the laptop, a deck deleted on the laptop
disappears from the phone, and a card graded on the laptop reaches the phone.

## 18. Deployment on Vercel

Two Vercel projects deploy from the same GitHub repository (`itsnicoramos/ProofLab`, branch
`main`); every push redeploys both.

| Project | Root | What runs |
|---|---|---|
| `prooflab` | `frontend/` | the tutor explainer (§21), static, https://prooflab-ruby.vercel.app |
| `prooflab-api` | `backend/` | the FastAPI checker as a Python function (`index.py`, `[tool.vercel] entrypoint = "index:app"`), https://prooflab-api.vercel.app |

The explainer calls no API. The `prooflab` project's `PROOFLAB_API_URL` setting was for the
practice site and is no longer read.

On Vercel the checker runs with `PROOFLAB_ISOLATE=0` (checks run in-process, no worker
processes, and the function's 60 s limit is the backstop) and `PROOFLAB_STORE=0`: Vercel has no
lasting disk, so there is no progress database there and progress stays in each browser
(§17's sync agent sees the 404 and says so). There is no macOS either, so the reader reads text
files only: photos, scanned PDFs and Word files need the checker running on the Mac. Everything
else (checking, tests, quizzes, new versions, flashcards, cards from pasted notes) works the same.
Locally nothing changes: `uvicorn prooflab.main:create_app --factory` with the full feature set.

## 19. XP, streaks and the daily goal

> **Removed from the website on 2026-11-08** (§21). This describes the practice site as it
> was up to commit `0eb0d0f`; the backend parts still work.

Duolingo-style motivation, kept honest: **a right answer earns XP, a wrong one means try
again** and costs nothing. XP comes only from the deterministic checker's verdict, a test's
score, or reviewing flashcards (1 XP a card a day, whatever the self-grade); nothing is decided
by AI. The mechanics are borrowed, not the look: no mascot, gems,
leagues, hearts, sounds or confetti (DESIGN.md: ProofLab acknowledges earned XP plainly).

### What's stored

`frontend/src/lib/xp.ts` keeps an append-only **activity log** in the browser
(`prooflab:v1:activity`), queued for the progress database (§17) like reviews. Each event is a
fact, never an XP amount:

| `type` | Recorded when | `data` |
|---|---|---|
| `solve` | a practice check first says Correct on a visit (once per visit; "Start over" allows another) | `difficulty`, `checks` this visit, `hints` asked for with "Show another hint" (the first hint appears by itself after a wrong check and is free), `variant` for a ProofLab-made version |
| `reveal` | the worked solution is opened in practice | none |
| `test` | a practice test is submitted | `kind`, and per question `item` (the book problem, null for a version), `difficulty`, `format`, `status`, `blank` |
| `card` | a flashcard is graded (any grade), or a quiz card is answered right | none |

Every event carries `day`, the browser's local date when it happened, so devices in different
time zones agree on which day counted. ProofLab-made versions are filed under the base problem.

### XP rules (`frontend/src/lib/xpRules.ts`)

XP is recomputed by replaying the log in time order (same log, same XP, on every device):

- **Solve:** easy 10, medium 15, hard 20; +5 if it was the first check of the visit; −5 for each
  extra hint asked for (never below 5). The first hint, which a wrong check shows by itself, is
  free, so a wrong answer never costs XP. 0 if the solution was opened earlier that day, or if this problem
  already paid that day. Solved on an earlier day before: half, rounded up (a review). A reveal
  after solving doesn't take XP back.
- **Test:** per written question 10/15/20 by difficulty (half for partly right); per
  multiple-choice question 5 if right; blank or wrong 0. If at least half the questions were
  answered: +5 quiz, +20 midterm, +30 final, and +10 more for 70% or more. A test id that
  already paid (Retake these questions) pays only what beats its best; a new seed pays in full.
- **Card:** 1 XP per card per day, whatever the grade (self-graded, so grading honestly costs
  nothing). Quiz answers pay only when right.

### Goal, streak, level, milestones

- **Daily goal:** 20, 50 or 100 XP (default 50), kept in the browser (`prooflab:v1:goal`).
- **Streak:** consecutive days with any XP; today counts once it has XP, and the streak stays
  alive until today ends. Every 7 days in a row earns a **streak freeze** (hold up to 2); a
  missed past day uses one automatically, otherwise the streak resets.
- **Level:** level n starts at 50 × n × (n − 1) XP (2 at 100, 3 at 300, 4 at 600, 5 at 1,000).
- **Milestones**, from real history only: first problem solved, first induction proof, 10
  different problems solved without asking for an extra hint and without opening the solution
  before solving (on any day; opening it afterwards to compare doesn't count against it), a
  perfect quiz, a final at 80% or more, 7- and 30-day streaks, 1,000 XP, and every chapter where
  all problems are Correct (dated by the day its last problem first became Correct: its first
  practice solve of the book problem itself, not a ProofLab-made version, or its first right
  answer in a practice test; the date is left off when a problem has neither on record).

### Where it shows

- Under the Correct verdict that earned it: "+20 XP" and its breakdown ("Medium 15, first try
  +5"; a floored solve adds "minimum +5" so the parts add up), or why it paid less. Later checks
  on the same visit show no XP note. Any other verdict shows **Try again**, which puts the cursor
  on the first step marked wrong, else on the final answer box if it isn't confirmed correct
  (empty included), else on the last step, plus "No XP yet" and what to do (fix the marked step,
  enter or fix the final answer, or use the feedback). Once the problem has been solved today
  (on any visit), "No XP yet" becomes "You already solved this one today, so it pays no more XP
  until tomorrow", and the "Show solution" confirmation stops saying that opening it means no
  XP today.
- Test results: the XP and its breakdown; a note that a retake pays only above the best.
- The end of a flashcard session or quiz: XP earned.
- The top bar (from `sm` up): "35 / 50 XP" linking to `/progress`, the streak from `md` up; in
  the phone menu, the Progress row. The home page: a Today line (XP, streak, problems due for
  review). Every chapter shelf: "3 of 12 solved" or "Chapter complete".
- When an action finishes the daily goal: one line, "Daily goal done: 50 XP today. 13-day
  streak." In practice it is inside the verdict's live region, so screen readers hear it; on the
  flashcard, quiz and test-result screens focus moves to the result heading, and the line
  follows it.
- `/progress`: today and the goal picker, streak and freezes, a 12-week calendar (no XP, some,
  goal met, freeze used), level and XP by source, chapters (solved count and skill from
  §15.3), milestones, recent XP, and **Reset XP and streak** (with a confirmation that keeps
  keyboard focus and says "in this browser" when there is no database; answers, test results,
  the flashcard schedule and chapter completions stay).

### Earlier work and limits

- Once per browser, right after its first sync with the database (or as soon as it learns
  there is none), the browser backfills work from before XP existed (`backfillEvents` in
  `xpRules.ts`), with fixed uids so two devices never count it twice. "Before XP existed" is
  read from the merged log: the earliest live (non-backfill) event on any device is when XP
  started for this student; with none yet (a fresh browser, the Vercel site), everything is
  earlier work. Backfilled: problems already Correct, one per book problem with ProofLab-made
  versions folded in (flat 10 XP, `day: null`, so they count toward the total and level but not
  toward a day or streak), unless the log has a live solve for it, it was first worked on after
  XP started, or a test taken after XP started covers it (a backfilled solve would sort first
  and turn a live solve into a half-XP review); submitted tests from before XP started (dated;
  difficulty unknown, so 10 per written point), unless the log has an event for that test; and
  concept and notes flashcard reviews from before XP started (dated; quiz answers included,
  right or wrong). Problem flashcards are stored like practice checks, so they can't be told
  apart and are skipped; hidden courses are skipped; nothing from before a reset the database
  recorded comes back. The backfill is marked done only once its events are really stored, so
  a full browser storage retries on the next load instead of losing them.
- On the Vercel deployment there is no progress database (§18), so XP stays in each browser
  and a streak doesn't follow the student between devices there.
- The log lives in the student's browser and could be edited. With one student and no
  leaderboards that only fools the student; leaderboards would need accounts and the server
  to recompute XP from its own checks.

## 20. Repo tutor (an AI tutor in the learner's own agent)

Decided with the user on 2026-11-08. Anyone who clones the repo gets a *Book of Proof* tutor
in their own coding agent (Claude Code, Codex, Cursor, others), the way *AI Engineering from
Scratch* ships tutor skills. **The app itself gets no AI:** the API is
unchanged (the website later became the tutor's explainer, §21), and the in-app Ollama assistant (§12) is still not wired. The tutor follows the
same principles: the checker is the judge, it stays grounded, and it never leaks answers.

### Pieces

| Piece | Where | Role |
|---|---|---|
| Skill | `.claude/skills/tutor/SKILL.md` + `modes/{start,level,learn,practice,quiz,guide}.md` | how to teach: routing, the rules below, each mode's script. Claude Code loads it as `/tutor`; other agents reach it through `AGENTS.md` (`CLAUDE.md` imports `AGENTS.md`) |
| Lesson notes | `backend/src/prooflab/content/lessons/proofs/chNN-<topic>.md` | one original note per chapter, ProofLab's own words |
| CLI | `backend/src/prooflab/tutor.py`, run as `uv run --project backend --extra tutor prooflab-tutor` | content, checking and memory, JSON out |
| Memory | `backend/src/prooflab/tutor_memory/`, Postgres from `docker-compose.yml` | the learner's plan and history |

### The tutor's rules

1. **The checker is the only judge.** The agent calls work correct only when `check` or
   `answer` said so. Chapters 11 to 14 have no checker yet, so anything said about those
   proofs is labelled "feedback, not a verdict".
2. **Translate, never fix.** The agent turns the learner's own words into ProofLab steps
   (§3, §5) and shows them before checking. Ambiguity means asking, not choosing.
3. **The hint ladder matches the site:**
   - a question first;
   - then the authored hints in order (a wrong verdict carries the next one as
     `AUTHORED_HINT`);
   - then one hint of the agent's own;
   - the solution only when the learner gives up, followed by an offered new-number version.
4. **Try again on a wrong verdict.** The agent points at the first step with status `error`,
   explains its message and code, and asks for another attempt.
5. **Exercises are read only through the CLI.** Problem JSON holds solutions and worked
   attempts. Choice questions come without keys.
6. **No book text and no invented book exercises.** Citations use section, exercise number
   and page, plus the free PDF link. New numbers come only from labelled versions (§13.3).
7. **Local only.**
   - Never the API server.
   - Never the SQLite progress store (§17).
   - Never SQL from the agent; memory goes through the CLI.
   - Without memory the tutor keeps teaching and says it can't save.

### CLI contract

The CLI loads the live course only (`proofs`, matching `COURSE_ORDER`). It reuses the API's
own code paths, so the tutor and the site always agree: `find_problem`, `problem_detail`,
`practice_test_out`, `answer_out` in `api/routes.py`, and `check_isolated` with the API's
timeouts. Exit codes: 0 done, 1 bad request, 3 memory unavailable.

| Command | Output |
|---|---|
| `chapters` | 14 chapters: lesson path, `checkable`, minutes, sections, problem counts, card counts |
| `lesson N` | the note's frontmatter and text |
| `problems --chapter N [--difficulty D]` | problem summaries with `chapter` |
| `show <id>` | `ProblemDetail` (§7): never the answer, solution, mistakes or examples |
| `check <id> [--hints-shown H] [--record --session S --quiz Q]` | `{checked_by, problem_id, chapter, verdict}`; work as `Submission` JSON on stdin or `--file` |
| `hint <id> N`, `solution <id>` | authored hint N; the worked solution |
| `cards --chapter N --count K --seed S` or `--ids …` | concept cards |
| `quiz --chapter N --count K --seed S` | a practice quiz in `choice` style (§13), no keys |
| `quiz --placement --seed S` | 10 choice questions, 2 per area (sets; logic; counting; direct and contrapositive; contradiction and induction), difficulty 1 or 2, no keys |
| `answer <id> --seed S --format F --choice X [--record --quiz Q]` | `ChoiceAnswerOut` (§13.2) |
| `test --kind quiz\|midterm\|final --chapters 1-5 --seed S [--style] [--length] [--variants]` | a practice test (§13); chapters without problems are listed in `skipped_chapters` |
| `variant <id> --seed S` | a §13.3 version with a `label` saying it is not a book exercise |
| `memory status\|init\|show\|plan set\|plan archive\|chapter\|session start\|session end\|note add\|review add\|review clear\|card\|quiz start\|quiz finish\|export\|forget --confirm` | the memory (below) |

`--record` saves the checker's own result: an `attempts` row is written only from a verdict the
CLI just computed, and a quiz score is computed from recorded answers. The agent can't
write "correct". If memory is down, `check --record` still returns the verdict, with
`"recorded": false` and the reason.

Some attempts are only format slips: the verdict is `invalid`, or its first error is an
input-format code (`FORMAT_CODES` in `tutor.py`: `PARSE_ERROR`, `NOT_AN_EXPRESSION`,
`LET_FORMAT`, `SET_SYNTAX`, ...). They are stored with `counted = false` (migration 002). They
never take away "first try" and stay out of the stats. A translation slip by the agent
therefore can't count against the learner.

### Memory (Postgres)

- **Service:** `docker compose up -d tutor-db`.
  - `postgres:17-alpine`, pinned by digest;
  - `127.0.0.1:5433` only;
  - volume `tutor-db-data`;
  - user `prooflab`, database `prooflab_tutor`.
- **Password:** `TUTOR_DB_PASSWORD` (default `prooflab-local`, from the environment or the
  gitignored `.env`).
- **Settings:** `PROOFLAB_TUTOR_DATABASE_URL` overrides the whole URL;
  `PROOFLAB_TUTOR_DB_SCHEMA` (default `tutor`) picks the schema; `PROOFLAB_TUTOR_LEARNER`
  (default `me`) picks the profile.
- **Driver:** `psycopg[binary]` 3, an optional extra (`uv sync --extra tutor`), so the Vercel
  API and the Docker image don't carry it.
- **Migrations:**
  - `tutor_memory/schema/NNN_*.sql`, applied in order on every connection under an advisory
    lock, and tracked in `schema_version`;
  - they never drop data;
  - `memory init` just runs them and reports.
- **Tables** (all keyed by learner, deleted with it):

| Table | Holds |
|---|---|
| `learners` | profile names |
| `plans` | mission, goal, pace, exam date, entry chapter, placement (jsonb). One active plan; "start over" sets `archived_at` and keeps a snapshot of chapter statuses |
| `chapter_status` | chapter 1 to 14 → `skip`, `review`, `do`, `done` |
| `sessions` | mode, chapter, start, end, one-line summary for the next warm-up |
| `attempts` | problem id, chapter, checker status, score, hint codes, hints shown, first try, the submission (jsonb) |
| `quiz_results`, `quiz_answers` | kind, chapters, seed, total, score; one counted answer per question |
| `review_queue` | chapter, missed idea, problem ids, cleared or not |
| `notes` | `struggle`, `misconception`, `preference` or `goal`, at most 500 characters |
| `card_reviews` | concept card recalled or not. A card is due when last missed or last seen over 7 days ago |

- **Safety:**
  - parameterized SQL only, with Pydantic-validated inputs and `CHECK` constraints for
    lengths and enums;
  - a learner can only change their own rows;
  - printed URLs hide the password;
  - nothing from the book is stored.
- **`memory export`** writes `LEARNING.md` at the repo root (gitignored): a readable view with
  the mission, placement, path, progress log, solved list, quizzes, review queue and notes.
  Edits to the file are never read back.

### Lesson notes

Each note has a one-line `key: value` frontmatter (lists as JSON arrays) with these keys:
- `chapter`, `title`, `topic` (the outline id);
- `book: hammack-bop3`;
- `sections` (`"4.3 Direct Proof (p. 118)"`);
- `prerequisites`, `minutes`;
- `checkable: yes|partly|no`;
- `review: draft|reviewed`.

The body is `# Chapter N: Title`, then exactly these sections in order: **Why it matters,
Core ideas, Worked example, Typing it into ProofLab, Common mistakes, Pause questions,
Practice route**. Every core idea cites `(Section N.k, p. P)`, using the section start pages
of Edition 3.4.

In checkable chapters:
- every "Common mistakes" bullet names real hint codes;
- the practice route lists real problem ids.

Chapters 11 to 14 instead name book exercise sets by section ("Exercises for Section 11.2"),
never their text. Worked examples are original, not book examples or exercises. The notes
contain no answer keys.

Notes start as `draft`. A note becomes `reviewed` only after a person checks it against the
book: no copied wording, correct sections and pages. `tests/test_lessons.py` checks the
format, the citations against `sections`, the ids, the codes, and that there are no dashes.

### Verified so far

- `tests/test_tutor.py` (no database):
  - the CLI's verdicts and choice grading equal the API's (`/check`, `/quiz/answer`);
  - `show`, `problems`, quizzes, placement and tests carry no solutions, examples or keys;
  - the CLI never opens the SQLite store;
  - an unreachable memory gives exit code 3 with the start command, and checking still works.
- `tests/test_tutor_memory.py` runs against Postgres when `PROOFLAB_TUTOR_TEST_DATABASE_URL`
  is set, in a throwaway schema per test, and is skipped otherwise.
- `tests/conftest.py` points the tutor memory at a closed port for every other test.
- `tests/test_tutor_replay.py` keeps the website's replay (§21) equal to the CLI's real output.

## 21. Website: the tutor explainer

Decided with the user on 2026-11-08. The Next.js site (`frontend/`,
https://prooflab-ruby.vercel.app) is now one static page that shows what a coding agent does
when someone types `/tutor` in the repo. The practice site (problem shelves, the step
workspace, flashcards, tests, progress, XP and the sync to the progress database, §13 to §19)
was deleted from `frontend/`; it is in git history up to commit `0eb0d0f`. The backend and its
HTTP API are unchanged.

### The page

One page, `/`, prerendered at build time. It calls no API and stores nothing.

- **How the pieces fit:** a diagram of the learner, the coding agent, the tutor skill,
  `prooflab-tutor`, content, the checker and memory, each with its place in the repo.
- **One session, step by step:** a replay of `/tutor practice 4` in 22 steps.
  - Back and Next reveal one step at a time; Show all reveals the rest.
  - Each step says who acts: the learner, the tutor, or the agent reading a file or running a
    command.
  - Commands show their real JSON output. `check` shows the verdict the way the checker read
    each step, typeset with KaTeX, with flagged steps in the status red.
  - From `lg` up, a side panel marks the pieces the current step uses ("you are here").
  - A link to `#step-N` opens the session up to step N.
- **Seven rules it keeps:** the rules of §20, each linking to the replay step that shows it.
- **Set it up:** the four commands with copy buttons, and how Claude Code, Codex and other
  agents start the tutor.

### Real output only

`frontend/src/replay/practice-4.script.json` holds the turns. The learner's and tutor's words
are written for the page, following the skill, and the page says so.
`frontend/scripts/capture_replay.py` runs every command in it with the real CLI and writes
`practice-4.json`, which the page imports.

- It uses a throwaway memory schema, dropped before and after. An existing `LEARNING.md` is
  put back.
- `{session}` becomes the id that `memory session start` returned.
- `check` gets exactly the steps the tutor proposed (`stdin_from`), so a verdict on the page is
  always about the steps the learner agreed to.
- Absolute paths inside the repo are shortened to repo-relative ones.

Re-capture after changing the checker, Chapter 4's content or the CLI's output:
`uv run --project backend --extra tutor python frontend/scripts/capture_replay.py`.

### Tests

- `frontend/src/lib/replay.test.ts` (`npm test`):
  - the capture matches its script;
  - the tutor says correct only right after a correct verdict, and names the checker;
  - every check grades the last proposed steps, after a learner reply;
  - no solution is shown, and `show` output carries none;
  - a wrong verdict is followed by a question, not rewritten steps;
  - every rule links to a step tagged with it;
  - no machine paths, and no em or en dashes in page text.
- `backend/tests/test_tutor_replay.py` re-runs the replay's `show`, `lesson` and `check`
  commands and requires the same output, so the page can't drift from the CLI. It is skipped
  where the frontend isn't checked out (the backend Docker image).
- Checked in a browser at 375 px and 1280 px, in light and dark: no sideways scroll, and every
  control is at least 44 px.
