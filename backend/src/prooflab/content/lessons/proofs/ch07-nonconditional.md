---
chapter: 7
title: Proving Non-Conditional Statements
topic: nonconditional
book: hammack-bop3
sections: ["7.1 If-and-Only-If Proof (p. 147)", "7.2 Equivalent Statements (p. 149)", "7.3 Existence Proofs; Existence and Uniqueness Proofs (p. 150)", "7.4 Constructive Versus Non-Constructive Proofs (p. 154)"]
prerequisites: [4, 5]
minutes: 100
checkable: partly
review: draft
---

# Chapter 7: Proving Non-Conditional Statements

## Why it matters
Not every theorem has the shape "if $P$, then $Q$". Some say two statements are equivalent, some say an object exists, and some say exactly one exists. Each shape has its own recipe, and almost all of them come down to the direct, contrapositive and contradiction proofs you already know.

## Core ideas
1. **If-and-only-if is two proofs** (Section 7.1, p. 147). $P \Leftrightarrow Q$ means $P \Rightarrow Q$ and $Q \Rightarrow P$. Prove each direction separately, with whatever method suits it. Label the parts ("($\Rightarrow$)" and "($\Leftarrow$)", or start the second with "Conversely") so the reader knows which is which.
2. **A method for each direction** (Section 7.1, p. 147). Often one direction is a direct proof and the other is easier by contrapositive, because its hypothesis is about an expression. For "$n$ is odd if and only if $f(n)$ is even", a common split is direct for $\Rightarrow$ and contrapositive for $\Leftarrow$ (assume $n$ is even, show $f(n)$ is odd).
3. **Equivalent statements** (Section 7.2, p. 149). A theorem may list several statements and claim they are all equivalent. Rather than proving every pair both ways, prove a cycle such as $(a) \Rightarrow (b) \Rightarrow (c) \Rightarrow (a)$. Following the arrows around the loop gets you from any statement to any other.
4. **Existence statements** (Section 7.3, p. 150). To prove $\exists x, P(x)$, name one $x$ and check that $P(x)$ holds. To show some natural number $n$ has $13 \mid (n^2 + 1)$, offer $n = 5$: $5^2 + 1 = 26 = 13 \cdot 2$. One example proves "there exists". It never proves "for all".
5. **Existence and uniqueness** (Section 7.3, p. 150). "There is exactly one $x$ with $P(x)$" has two parts: existence (an example) and uniqueness (if $x$ and $y$ both satisfy $P$, then $x = y$). For instance, $n = 3$ solves $n^2 = 6n - 9$, and any solution satisfies $(n - 3)^2 = 0$, so it must be 3. The same section also proves that $\gcd(a, b)$ can be written as $ak + b\ell$ for some integers $k$ and $\ell$.
6. **Constructive versus non-constructive** (Section 7.4, p. 154). A constructive proof shows you the object. A non-constructive proof shows it must exist without saying which one it is. Example: among the first 21 digits of $\pi$ after the decimal point, some digit appears at least 3 times, because 10 digits used at most twice each fill only 20 places. That proves such a digit exists without naming it.

## Worked example
Claim: let $n$ be an integer. Then $n$ is odd if and only if $n^3 + 2n + 9$ is even.

($\Rightarrow$, direct.) Suppose $n$ is odd, so $n = 2k + 1$ for some integer $k$.
- $n^3 + 2n + 9 = (2k + 1)^3 + 2(2k + 1) + 9$
- $= 8k^3 + 12k^2 + 6k + 1 + 4k + 2 + 9 = 8k^3 + 12k^2 + 10k + 12$
- $= 2(4k^3 + 6k^2 + 5k + 6)$, which is even.

($\Leftarrow$, contrapositive.) We show: if $n$ is even, then $n^3 + 2n + 9$ is odd. Suppose $n = 2k$.
- $n^3 + 2n + 9 = 8k^3 + 4k + 9 = 2(4k^3 + 2k + 4) + 1$, which is odd.

Both directions hold, so the equivalence is proved. $\blacksquare$

ProofLab splits an iff into two problems, one per direction. The forward direction (hypothesis "$n$ is odd", goal "even"):

```
let      n = 2k + 1
expr     (2k + 1)^3 + 2(2k + 1) + 9
expr     8k^3 + 12k^2 + 10k + 12
witness  4k^3 + 6k^2 + 5k + 6
```

The converse by contrapositive (hypothesis "$n$ is even", goal "odd"):

```
let      n = 2k
expr     8k^3 + 4k + 9
witness  4k^3 + 2k + 4
```

## Typing it into ProofLab
Chapter 7 uses several problem kinds. Read the prompt and the answer format to see which one you have.

- **One direction of an iff** (`parity_proof`). The prompt names the direction and the method. For a contrapositive direction it states the contrapositive for you, and your `let` assumes that statement's hypothesis. Steps are `let`, `expr` and `witness`, as in Chapters 4 and 5.
- **A "for all" claim with cases** (`divisibility_proof`). Statements like "for every integer $a$, $2 \mid (a^2 + 5a)$" have no "if", and nothing is known about $a$. Split by remainder, each case with its own witness: `case a = 2k`, `witness 2k^2 + 5k`, then `case a = 2k + 1`, `witness 2k^2 + 7k + 3`.
- **Existence** (`existence`). Type your example in the answer box as `name = value`, like `n = 5`, with one entry per variable separated by commas. Steps are optional notes and aren't checked; ProofLab evaluates the statement at your values. In this book $\mathbb{N} = \{1, 2, 3, \dots\}$, so $0$ is not allowed where a natural number is asked for.
- **Impossibility by contradiction** (`impossibility_proof`). `proofs.nonconditional.ch7-ex24` and `proofs.nonconditional.ch7-ex27` use the Chapter 6 format: `let` or `case` steps, then a `form` step like `4(k^2 + 3k) + 1` closing every case.
- **Induction** (`induction`). `proofs.nonconditional.ch7-ex19` is checked as an induction proof (`base`, `assume` and `expr` steps), which you will meet in Chapter 10.

## Common mistakes
- **Proving one direction twice** (`EVEN_FORM`, `ODD_FORM`). The converse swaps hypothesis and conclusion. In the contrapositive half, a let that assumes the forward direction's hypothesis (like `n = 2k + 1` when the prompt says to assume $n$ is even) is rejected.
- **Halving errors in the witness** (`WITNESS_MISMATCH`, `WITNESS_NOT_INTEGER`). The witness is the $w$ in $2w$ or $2w + 1$. If $10a + 7$ appears, write it as $2(5a + 3) + 1$, not with $5a + 7/2$.
- **Using an example to prove "for all"** (`TRY_CASES`, `CASES_NOT_EXHAUSTIVE`). Checking $a = 2$ says nothing about every $a$. When nothing is known about $a$, split into cases by remainder and cover all of them. A witness like $(a^2 + 5a)/2$ only restates the claim.
- **An example that fails** (`EXISTS_FAILS`). Test your value before you submit: plug it in and check every condition, including any bounds in the statement.
- **Answer box format and domain** (`COUNTEREXAMPLE_FORMAT`, `EXISTS_FORMAT`, `COUNTEREXAMPLE_DOMAIN`, `COUNTEREXAMPLE_NOT_INTEGER`). Type `n = 5`, not just `5`. Values must be integers, and natural numbers start at 1.
- **A let step for an unknown variable** (`LET_WITHOUT_HYPOTHESIS`). A let needs a hypothesis about that variable. Without one, use cases.

## Pause questions
1. To prove "$n$ is even if and only if $5n + 2$ is even", which two conditionals do you prove?
2. Why does one example prove "there is an $n$ with $P(n)$" but not "for every $n$, $P(n)$"?
3. What are the two parts of an existence-and-uniqueness proof?
4. Why is the digits-of-$\pi$ argument non-constructive?

## Practice route
- `proofs.nonconditional.ch7-ex01a`: one direction of an iff, a short direct proof.
- `proofs.nonconditional.ch7-ex01b`: the other direction by contrapositive; together they prove the iff.
- `proofs.nonconditional.ch7-ex04b`: a direct direction of a quadratic iff.
- `proofs.nonconditional.ch7-ex04a`: its other direction by contrapositive, with more algebra.
- `proofs.nonconditional.ch7-ex17`: an existence proof by one well-chosen example.
- `proofs.nonconditional.ch7-ex20`: existence where you have to search a little, and 0 doesn't count.
- `proofs.nonconditional.ch7-ex10`: a "for all" statement proved by cases mod 3.
- `proofs.nonconditional.ch7-ex24`: an impossibility proof, linking back to Chapter 6.
