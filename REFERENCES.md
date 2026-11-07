# References

## Citation policy

- **ProofLab never copies text from a textbook.**
- **Proofs course (MATH 123): every problem is a *Book of Proof* exercise.** MATH 123 uses
  *Book of Proof* as its textbook, so nothing in this course is invented: each problem is one
  exercise, with the same mathematical claim restated in ProofLab's own words, and cited as
  `Chapter N exercises, #k (p. P)` (pages from Edition 3.4). Hints and worked solutions are
  ProofLab's own. The book is CC BY-NC-ND 4.0, so its wording isn't reproduced and no modified
  version of the book is shared.
- **Other courses:** problems are original, and each cites the open-textbook section that
  teaches its topic, so a student who's stuck knows where to read.
- Confirming the exercise number, page and statement against the book is part of moving a
  problem from `draft` to `reviewed`.

The machine-readable registry is `backend/src/prooflab/content/references.json`.

## Books

| id | Book | Author(s) | Licence | Used for |
|---|---|---|---|---|
| `sundstrom-mr3` | *Mathematical Reasoning: Writing and Proof*, Version 3 (2020), ScholarWorks@GVSU. <https://scholarworks.gvsu.edu/books/24/> | Ted Sundstrom | CC BY-NC-SA 3.0 | cited only by retired problems |
| `hammack-bop3` | *Book of Proof*, 3rd ed., Edition 3.4 (2018). <https://richardhammack.github.io/BookOfProof/> | Richard Hammack | CC BY-NC-ND 4.0 | **MATH 123 textbook**: all proofs-course problems map to its exercises |
| `openstax-precalc2e` | *Precalculus 2e* (2021), OpenStax. <https://openstax.org/details/books/precalculus-2e> | Jay Abramson et al. | CC BY 4.0 | functions, trig, exponentials and logs |
| `openstax-calc1` | *Calculus Volume 1* (2016), OpenStax. <https://openstax.org/details/books/calculus-volume-1> | Gilbert Strang, Edwin "Jed" Herman et al. | CC BY-NC-SA 4.0 | limits, derivatives |
| `openstax-calc2` | *Calculus Volume 2* (2016), OpenStax. <https://openstax.org/details/books/calculus-volume-2> | Gilbert Strang, Edwin "Jed" Herman et al. | CC BY-NC-SA 4.0 | integration, series, first-order ODEs |
| `openstax-calc3` | *Calculus Volume 3* (2016), OpenStax. <https://openstax.org/details/books/calculus-volume-3> | Gilbert Strang, Edwin "Jed" Herman et al. | CC BY-NC-SA 4.0 | multivariable, vector calculus, second-order ODEs |
| `trench-de` | *Elementary Differential Equations* (2013), Trinity University Digital Commons. <https://digitalcommons.trinity.edu/mono/8/> | William F. Trench | CC BY-NC-SA 3.0 | differential equations |

## Software

ProofLab's checking is built on these open-source libraries:

| Library | Licence | Role |
|---|---|---|
| [SymPy](https://www.sympy.org) | BSD-3-Clause | symbolic math: derivatives, limits, solving, simplification |
| [mpmath](https://mpmath.org) | BSD-3-Clause | 30-digit numeric evaluation for equivalence checks |
| [FastAPI](https://fastapi.tiangolo.com) | MIT | HTTP API |
| [Pydantic](https://docs.pydantic.dev) | MIT | content and request validation |
| [Uvicorn](https://www.uvicorn.org) | BSD-3-Clause | ASGI server |

The numeric-equivalence approach (compare expressions at random points in a declared domain)
is the same idea long used by open homework systems such as WeBWorK.
