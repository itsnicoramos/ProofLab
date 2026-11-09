---
chapter: 10
title: Mathematical Induction
topic: induction
book: hammack-bop3
sections: ["10.1 Proof by Induction (p. 182)", "10.2 Proof by Strong Induction (p. 187)", "10.3 Proof by Smallest Counterexample (p. 191)", "10.4 The Fundamental Theorem of Arithmetic (p. 192)", "10.5 Fibonacci Numbers (p. 193)"]
prerequisites: [4]
minutes: 150
checkable: partly
review: draft
---

# Chapter 10: Mathematical Induction

## Why it matters
Many claims say something about every natural number: a sum formula, a divisibility fact, an inequality. You can't check infinitely many cases one by one. Induction proves all of them with two finite arguments, and it is the tool behind later results such as unique prime factorization.

## Core ideas
1. **A list of statements** (Section 10.1, p. 182). Induction proves claims of the form "for every integer $n \ge b$, $S_n$ is true". Think of $S_b, S_{b+1}, S_{b+2}, \ldots$ as an endless list. You prove two things. The base case: $S_b$ is true. The inductive step: for every $k \ge b$, if $S_k$ is true then $S_{k+1}$ is true. Together they reach every statement: $S_b$ gives $S_{b+1}$, that gives $S_{b+2}$, and so on.
2. **The base case** (Section 10.1, p. 182). Put the starting value into the statement and check it with numbers. In this book $\mathbb{N} = \{1, 2, 3, \ldots\}$, so "for every $n \in \mathbb{N}$" starts at $n = 1$. A claim "for every integer $n \ge 0$" starts at $n = 0$. Remember that $a^0 = 1$ and $0! = 1$.
3. **The inductive step is a conditional proof** (Section 10.1, p. 182). You assume $S_k$ for one fixed but arbitrary $k \ge b$. That assumption is the inductive hypothesis. Then you deduce $S_{k+1}$ from it. You are not assuming the theorem. You assume one case and show the next case follows. So write the hypothesis with $k$, never with $n$.
4. **Sums: split off the last term** (Section 10.1, p. 182). For a claim $\sum_{i=1}^{n} a_i = R(n)$, the sum up to $k + 1$ is the sum up to $k$ plus $a_{k+1}$. Replace the sum up to $k$ by $R(k)$. That is where the hypothesis gets used. Then do algebra until you reach $R(k+1)$. Write $R(k+1)$ down first so you know your target. Factoring out a shared factor such as $(k + 1)$ is usually faster than expanding everything.
5. **Divisibility: make $f(k)$ appear inside $f(k+1)$** (Section 10.1, p. 182). To prove $d \mid f(n)$, write the hypothesis as $f(k) = dm$ for an integer $m$. Then rewrite $f(k+1)$ so that $f(k)$ shows up. With powers, use $a^{k+1} = a \cdot a^k$ and add and subtract a constant: $3^{4(k+1)} - 1 = 81 \cdot 3^{4k} - 1 = 81(3^{4k} - 1) + 80$. With polynomials, expand $f(k+1)$ and group the terms of $f(k)$ together. Finish by writing $f(k+1) = d \cdot w$ with $w$ an integer.
6. **Other kinds of statements** (Section 10.1, p. 182). Induction also proves inequalities and facts about primes. One fact you will reuse: if a prime divides a product of $n$ integers, it divides at least one of them. For an inequality, the inductive step is a chain of $=$, $\le$ and $<$ steps from the hypothesis to $S_{k+1}$. (ProofLab doesn't check inequality proofs yet.)
7. **Strong induction** (Section 10.2, p. 187). Sometimes $S_{k+1}$ follows from an earlier statement, not from $S_k$. In strong induction you assume all of $S_b, \ldots, S_k$ and deduce $S_{k+1}$. If the step reaches back $j$ places, you need $j$ base cases. Example: every integer $n \ge 14$ is a sum of 3s and 8s. Check $14 = 3 + 3 + 8$, $15 = 3 + 3 + 3 + 3 + 3$ and $16 = 8 + 8$. For $k + 1 \ge 17$, the number $(k + 1) - 3 \ge 14$ is a sum of 3s and 8s by the hypothesis, so add one more 3.
8. **Smallest counterexample** (Section 10.3, p. 191). This is induction written as a proof by contradiction. Check the first case. Then suppose some case fails, and let $k$ be the smallest index with $S_k$ false. Since $k$ is past the base case, $S_{k-1}$ is true. Use $S_{k-1}$ to show $S_k$ is true after all, a contradiction. It works because every nonempty set of natural numbers has a smallest element.
9. **The fundamental theorem of arithmetic** (Section 10.4, p. 192). Every integer $n > 1$ is a product of primes in exactly one way, apart from the order of the factors. Existence uses strong induction: either $n$ is prime, or $n = ab$ with $1 < a, b < n$, and both smaller factors already have prime factorizations. Uniqueness uses a smallest counterexample together with the prime fact from idea 6.
10. **Fibonacci numbers and other recurrences** (Section 10.5, p. 193). The Fibonacci numbers are $F_1 = F_2 = 1$ and $F_n = F_{n-1} + F_{n-2}$ for $n \ge 3$. A fact about $F_{k+1}$ usually needs both $F_k$ and $F_{k-1}$, so you use strong induction with two base cases. The same plan works for any two-step recurrence. For instance, if $a_1 = 1$, $a_2 = 5$ and $a_n = a_{n-1} + 2a_{n-2}$, then $a_n = 2^n + (-1)^n$. Check $n = 1$ and $n = 2$, then $a_{k+1} = (2^k + (-1)^k) + 2(2^{k-1} + (-1)^{k-1}) = 2^{k+1} + (-1)^{k+1}$.

## Worked example
Claim: for every $n \in \mathbb{N}$, $\sum_{i=1}^{n} (6i^2 - 2i) = 2n^2(n + 1)$.

**Base case.** For $n = 1$ the left side is $6 \cdot 1^2 - 2 \cdot 1 = 4$ and the right side is $2 \cdot 1^2 \cdot (1 + 1) = 4$. They agree.

**Inductive hypothesis.** Fix $k \ge 1$ and assume $\sum_{i=1}^{k} (6i^2 - 2i) = 2k^2(k + 1)$.

**Target.** The case $n = k + 1$ says the sum up to $k + 1$ equals $2(k + 1)^2(k + 2)$.

**Inductive step.** Split off the last term, which is $6(k + 1)^2 - 2(k + 1)$, and use the hypothesis on the rest: $\sum_{i=1}^{k+1} (6i^2 - 2i) = 2k^2(k + 1) + 6(k + 1)^2 - 2(k + 1)$.

Every term has a factor $(k + 1)$, so pull it out: $(k + 1)(2k^2 + 6(k + 1) - 2) = (k + 1)(2k^2 + 6k + 4)$.

Factor the quadratic: $2k^2 + 6k + 4 = 2(k + 1)(k + 2)$. So the sum is $2(k + 1)^2(k + 2)$, which is the target.

So $S_k$ implies $S_{k+1}$ for every $k \ge 1$. With the base case, induction gives the formula for every $n \in \mathbb{N}$.

In ProofLab you would type these steps (step kind on the left, what goes in the box on the right):

```
base      6*1^2 - 2*1 = 2*1^2*(1 + 1)
assume    4 + 20 + ... + (6k^2 - 2k) = 2k^2(k + 1)
expr      2k^2(k + 1) + 6(k + 1)^2 - 2(k + 1)
expr      (k + 1)(2k^2 + 6k + 4)
expr      2(k + 1)^2(k + 2)
```

The first `expr` line is the hypothesis's right side plus the next term. ProofLab marks it as the line that uses the hypothesis. The last two lines simplify it to the $n = k + 1$ formula.

## Typing it into ProofLab
ProofLab checks sum formulas and divisibility statements proved by ordinary induction. A proof is a list of steps, and you pick a kind for each one. In the step picker, `base` shows as "Base case" and `expr` shows as "Step".

- `base`: the base case, numbers only. Put the starting value in and write a chain of equal numbers: `4 = 2*1^2*(1 + 1)`, or `n = 1: 4 = 4`. For divisibility: `3^0 - 1 = 0 = 10*0`, or `10 | 0`.
- `assume`: the statement for $n = k$. For a sum ProofLab reads only the right side, so the left may use dots: `4 + 20 + ... + (6k^2 - 2k) = 2k^2(k + 1)`. You may add `, for some k >= 1`. For divisibility, write an equation with a new integer `m`: `3^(4k) - 1 = 10m`.
- `expr`: one expression per step, each equal to the $n = k + 1$ case. No equals signs and no dots here. For a sum, one step must be the hypothesis's right side plus the next term, in any order, and at least one more step must follow it. For divisibility you may use `m`, which stands for $f(k)/d$.
- `witness`: divisibility only. The integer $w$ with $f(k + 1) = d \cdot w$, written in `k` and `m`: `81m + 8`, or `w = 81m + 8`. A fraction is fine only if the value is always an integer, like `m + k(k + 1)/2`.
- `note`: words for yourself. Never checked.

A full divisibility proof, for $10 \mid (3^{4n} - 1)$ with $n \ge 0$:

```
base      3^0 - 1 = 0 = 10*0
assume    3^(4k) - 1 = 10m
expr      81*3^(4k) - 1
expr      81(3^(4k) - 1) + 80
expr      810m + 80
witness   81m + 8
```

Syntax reminders. `^` is a power, and an exponent with more than one symbol needs brackets: `5^(2k)`, `2^(k + 1)`. Multiplication is `*` or implicit: `2k^2(k + 1)`. Factorials are `(k + 1)!`. The allowed letters are `n`, `k`, `m` and the sum's index (usually `i`). Each checked step shows how ProofLab read it, so compare that with what you meant.

Verdicts: correct when every step checks and the proof is complete; partial when every step checks but something is missing; incorrect when a step is wrong.

## Common mistakes
- **Letters in the base case** (`IND_BASE_NUMBERS`). You wrote $n$ or $k$ in the base step. Substitute the starting value and write numbers only.
- **A base case that doesn't add up** (`IND_BASE_UNEQUAL`, `IND_BASE_WRONG`). An arithmetic slip such as $4^0 = 0$ (it is 1), or checking $n = 1$ when the prompt starts at $n = 0$. Read the starting value in the prompt and redo the arithmetic.
- **Missing base case or hypothesis** (`IND_NEED_BASE`, `IND_NEED_HYPOTHESIS`). Correct algebra alone isn't an induction proof. Add the `base` and `assume` steps.
- **Hypothesis written with n** (`IND_ASSUME_USE_K`). Writing the formula with $n$ assumes the whole theorem. Write it for one fixed $k$.
- **Wrong hypothesis** (`IND_ASSUME_WRONG`, `IND_ASSUME_FORMAT`). The hypothesis is the formula with every $n$ replaced by $k$, written as an equation. Don't write the $k + 1$ case here.
- **Divisibility hypothesis left as $d \mid f(k)$** (`IND_ASSUME_FORMAT`, `IND_ASSUME_DIVIDES`). You can't substitute a divisibility claim. Write $f(k) = dm$ with the right divisor and a new letter $m$.
- **Using m before assuming anything** (`IND_NO_HYPOTHESIS_YET`). Put the `assume` step first, so $m$ has a meaning.
- **Wrong next term** (`IND_STEP_WRONG`). Adding $a_k$ again, or substituting $k + 1$ in only part of the term. For $6i^2 - 2i$ the next term is $6(k + 1)^2 - 2(k + 1)$, not $6k^2 - 2k$. The same code flags any algebra slip later in the chain.
- **Jumping to the answer** (`IND_USE_HYPOTHESIS`). Writing only the $k + 1$ formula proves nothing. Start the step with the hypothesis's right side plus the next term.
- **Stopping after the hypothesis line** (`IND_FINISH_SUM`). Keep simplifying until you reach the $n = k + 1$ formula.
- **Dots or equations in a step** (`PARSE_ERROR`, `NOT_AN_EXPRESSION`). An `expr` step is one expression. Replace the sum by the hypothesis's right side, and drop any `... =` part.
- **Witness off by a little** (`IND_WITNESS_WRONG`). Usually a dropped constant or a term not divided by $d$. Multiply your witness by $d$ and compare with $f(k + 1)$.
- **A witness ProofLab can't confirm is an integer** (`IND_WITNESS_NOT_INTEGER`). Write it as a polynomial in $k$ and $m$, such as `81m + 8`. Don't write $f(k + 1)/d$ itself as the witness, and don't leave a fraction that may not divide evenly.
- **No witness at the end** (`IND_FINISH_DIVIDES`). A line such as `10(81m + 8)` shows the idea, but the proof ends with a `witness` step.

## Pause questions
1. In the inductive step, what exactly are you allowed to assume, and what must you prove?
2. Why does a claim "for every integer $n \ge 0$" need a different base case from a claim "for every $n \in \mathbb{N}$"?
3. To prove $d \mid f(n)$, why write the hypothesis as $f(k) = dm$ instead of $d \mid f(k)$?
4. When does a proof need strong induction, and how do you decide how many base cases to check?

## Practice route
- `proofs.induction.ch10-ex01`: the simplest sum; learn the step kinds and the hypothesis-plus-next-term line.
- `proofs.induction.ch10-ex06`: sigma notation with a linear term; substitute $k + 1$ everywhere in the next term.
- `proofs.induction.ch10-ex05`: powers of 2; use $2^{k+1} = 2 \cdot 2^k$ to simplify.
- `proofs.induction.ch10-ex02`: squares; heavier algebra, so factor out $(k + 1)$ instead of expanding.
- `proofs.induction.ch10-ex15`: fractions; combine over a common denominator to reach the target.
- `proofs.induction.ch10-ex10`: the first divisibility proof; write $f(k) = 3m$ and finish with a witness.
- `proofs.induction.ch10-ex11`: polynomial divisibility; expand $f(k + 1)$ and regroup the terms of $f(k)$.
- `proofs.induction.ch10-ex13`: a harder witness; you need a fact about $k(k + 1)$ to see it is an integer.
