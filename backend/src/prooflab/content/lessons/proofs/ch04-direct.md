---
chapter: 4
title: Direct Proof
topic: direct
book: hammack-bop3
sections: ["4.1 Theorems (p. 113)", "4.2 Definitions (p. 115)", "4.3 Direct Proof (p. 118)", "4.4 Using Cases (p. 124)", "4.5 Treating Similar Cases (p. 125)"]
prerequisites: [1, 2]
minutes: 100
checkable: partly
review: draft
---

# Chapter 4: Direct Proof

## Why it matters
A direct proof is the basic way to prove "if $P$, then $Q$": assume $P$ and reason forward until you reach $Q$. Contrapositive proof, contradiction and induction all reuse its moves. The habit you build here, unpacking definitions into equations with new variables and then packing the result back into a definition, is most of what proving facts about integers takes.

## Core ideas
1. **Theorems and their shape** (Section 4.1, p. 113). A theorem is a statement that has been proved true. Smaller results are called propositions; a lemma is a step toward a bigger result, and a corollary follows quickly from one. Most have the form $P \Rightarrow Q$, often with a hidden "for every integer $n$" in front.
2. **Even, odd and parity** (Section 4.2, p. 115). An integer $n$ is even if $n = 2a$ for some integer $a$, and odd if $n = 2a + 1$ for some integer $a$. Every integer is exactly one of the two. Two integers have the same parity if both are even or both are odd, and opposite parity otherwise.
3. **Divisibility, primes, gcd and lcm** (Section 4.2, p. 115). For integers $a$ and $b$, $a \mid b$ means $b = ac$ for some integer $c$; read it "$a$ divides $b$". It is a statement, not a number: $4 \mid 28$ is true, while $28/4 = 7$ is a number. A natural number $p > 1$ is prime if its only positive divisors are 1 and $p$; a natural number above 1 that isn't prime is composite. $\gcd(a, b)$ is the largest integer dividing both, and $\operatorname{lcm}(a, b)$ is the smallest positive integer that both divide.
4. **Facts you may use freely** (Section 4.2, p. 115). Sums, differences and products of integers are integers. That is why an expression like $2k^2 + 3k$ counts as an integer once $k$ is one. The division algorithm says that for any integer $n$ and positive integer $d$, there are unique integers $q$ and $r$ with $n = qd + r$ and $0 \le r < d$. So every integer has the form $3q$, $3q + 1$ or $3q + 2$.
5. **The outline of a direct proof** (Section 4.3, p. 118). To prove $P \Rightarrow Q$, write "Suppose $P$." Then take justified steps until you can write "Therefore $Q$." You never assume $Q$. Start with "Proof." and finish with a mark such as ∎.
6. **Unpack, compute, repack** (Section 4.3, p. 118). Rewrite each hypothesis with its definition and a new variable: "$x$ is odd, so $x = 2k + 1$ for some integer $k$." Substitute into the expression the conclusion is about and do the algebra. Then show the result has the shape the conclusion's definition needs, such as $2(\text{integer})$, $2(\text{integer}) + 1$ or $a \cdot (\text{integer})$, and say which integer it is.
7. **One new letter per hypothesis** (Section 4.3, p. 118). If $x$ and $y$ are both odd, write $x = 2j + 1$ and $y = 2k + 1$. Using the same letter for both quietly assumes $x = y$, so the proof would only cover that one situation.
8. **Proof by cases** (Section 4.4, p. 124). When the hypothesis gives you nothing to unpack, as in "for every integer $n$, ...", split into cases that cover every possibility: $n$ even and $n$ odd, or the three remainders when dividing by 3. Prove the conclusion separately in each case.
9. **Treating similar cases** (Section 4.5, p. 125). When two cases differ only by swapping the names of variables, prove one and say the other works the same way with the roles swapped. The phrase "without loss of generality" signals this. Use it only when the cases really are symmetric.

## Worked example
Prove: if $a$ is odd and $b$ is even, then $a^2 + 3ab - b$ is odd.

1. Suppose $a$ is odd and $b$ is even. By the definitions, $a = 2j + 1$ and $b = 2k$ for some integers $j$ and $k$. There are two hypotheses, so there are two different new letters.
2. Substitute: $a^2 + 3ab - b = (2j + 1)^2 + 3(2j + 1)(2k) - 2k$.
3. Expand. $(2j + 1)^2 = 4j^2 + 4j + 1$ and $3(2j + 1)(2k) = 12jk + 6k$. So the expression equals $4j^2 + 4j + 12jk + 4k + 1$.
4. Repack: $4j^2 + 4j + 12jk + 4k + 1 = 2(2j^2 + 2j + 6jk + 2k) + 1$.
5. Name the integer. $2j^2 + 2j + 6jk + 2k$ is an integer, because sums and products of integers are integers. So $a^2 + 3ab - b$ has the form $2(\text{integer}) + 1$, which means it is odd. ∎

In ProofLab, as a `parity_proof` problem whose target is $a^2 + 3ab - b$ and whose goal is odd:
- let: `a = 2j + 1`
- let: `b = 2k`
- expr: `(2j + 1)^2 + 3(2j + 1)(2k) - 2k`
- expr: `4j^2 + 4j + 12jk + 4k + 1`
- expr: `2(2j^2 + 2j + 6jk + 2k) + 1`
- witness: `2j^2 + 2j + 6jk + 2k`

The witness is only the integer inside the brackets. ProofLab checks that $2 \cdot (\text{witness}) + 1$ equals the target after your substitutions.

## Typing it into ProofLab
Chapter 4 problems are `parity_proof` (conclusions about even and odd) and `divisibility_proof` (conclusions about $\mid$). ProofLab checks the algebra skeleton of your proof: each representation, each line of algebra, the witness and the cases. It doesn't read your sentences, so you still write the proof out in words. Exercises about primes, gcds, inequalities or real numbers aren't checked here.

Step kinds:
- `let`: rewrite a hypothesis with a new integer letter. Even: `x = 2k`. Odd: `x = 2k + 1`. For $a \mid b$, write `b = am`. The left side is a problem variable that a hypothesis is about. The right side uses one new single letter that you haven't used for anything else.
- `expr`: one line of algebra. Every line must equal the expression you're proving something about, after your `let` substitutions. It may use the problem's letters or your new ones.
- `witness`: the integer $w$ that finishes the proof. For even, target $= 2w$. For odd, target $= 2w + 1$; always this $+1$ form, never $2w - 1$. For $d \mid$ target, target $= d \cdot w$. Type $w$ itself, like `3k^2 + k`, or a labelled form like `m = 3k^2 + k`. It must be a polynomial in your integer letters with integer coefficients.
- `case`: starts a case, like `n = 2k`, and later another, like `n = 2k + 1`. Each case needs its own `expr` lines and its own `witness`. All cases must split the same variable by the same number and together cover every remainder. You may reuse $k$ in each case. Cases can't be nested.
- `note`: free text, never checked.

There is no answer box. The proof is complete when every step checks out and it ends with a valid witness (in every case, if you used cases).

A divisibility example: if $a \mid b$ and $a \mid c$, then $a^2 \mid (bc + 3b^2)$.
- let: `b = aj`
- let: `c = ak`
- expr: `(aj)(ak) + 3(aj)^2`
- expr: `a^2(jk + 3j^2)`
- witness: `jk + 3j^2`

A cases example: for every integer $n$, $n^2 - 3n + 9$ is odd.
- case: `n = 2k`
- expr: `4k^2 - 6k + 9`
- witness: `2k^2 - 3k + 4`
- case: `n = 2k + 1`
- expr: `4k^2 - 2k + 7`
- witness: `2k^2 - k + 3`

## Common mistakes
- **One letter for two hypotheses** (`SAME_FRESH_VARIABLE`). Writing $x = 2k + 1$ and $y = 2k + 1$ says $x = y$. Give each hypothesis its own letter.
- **Reusing a problem variable** (`FRESH_NOT_NEW`). $x = 2x + 1$ or $b = ab$ doesn't introduce anything new. Pick a letter that isn't already in the problem.
- **Wrong form for even or odd** (`EVEN_FORM`, `ODD_FORM`, `BAD_REPRESENTATION`). Odd means $2k + 1$, not $k + 1$ or $2k$. For $a \mid b$ the multiple goes on $b$: $b = am$, not $a = bm$.
- **A badly formed let** (`LET_FORMAT`, `LET_WITHOUT_HYPOTHESIS`). A let is an equation like `x = 2k + 1` with a problem variable on the left, not a sentence like "x is odd". Only rewrite variables a hypothesis talks about; a variable with no assumption stays as it is, or gets split into cases.
- **Not using the hypothesis** (`MISSING_LET`). If the target still contains $x$ and you never used "$x$ is odd", you haven't used what you were given. Start with the let.
- **Algebra slips** (`NOT_EQUIVALENT`). Each `expr` line must equal the target. Expand squares carefully: $(2k + 1)^2 = 4k^2 + 4k + 1$, not $4k^2 + 1$.
- **Witness off by a piece** (`WITNESS_MISMATCH`). The witness is only the integer inside $2(\ldots) + 1$ or $d(\ldots)$. Leave out the $+1$, and for $a^2 \mid \ldots$ divide out all of $a^2$, not just $a$.
- **Witness that isn't clearly an integer** (`WITNESS_NOT_INTEGER`, `TRY_CASES`). A fraction like $\frac{n^2 + n}{2}$ isn't visibly an integer. Split into cases so the algebra gives an integer polynomial.
- **Cases that don't cover everything** (`CASES_NOT_EXHAUSTIVE`, `CASE_MISMATCH`). Even and odd together cover every integer, while remainders mod 3 need three cases. Don't mix splits, such as $n = 2k$ with $n = 3k + 1$.
- **Stopping before the end** (`PROOF_INCOMPLETE`). Correct algebra isn't a finished proof until you name the witness that matches the definition.

## Pause questions
1. Why can't you write $x = 2k + 1$ and $y = 2k + 1$ when proving something about two odd integers?
2. Using only the definition, is 0 even? Is $-7$ odd? Which integer shows it in each case?
3. What is the difference between $a \mid b$ and $a / b$? Is $6 \mid 3$ true?
4. A claim says "for every integer $n$" and assumes nothing else about $n$. What do you do first, and how do you know your cases cover everything?

## Practice route
- `proofs.direct.ch4-ex01`: one let and a short witness; learn the step kinds here.
- `proofs.direct.ch4-ex03`: a longer expansion that ends in the odd form with a $+1$ left over.
- `proofs.direct.ch4-ex04`: two odd hypotheses, so two different new letters.
- `proofs.direct.ch4-ex05`: only $x$ has a hypothesis; $y$ stays as it is.
- `proofs.direct.ch4-ex06`: the first divisibility proof; factor out $a$.
- `proofs.direct.ch4-ex19`: chain two divisibility facts by substituting one into the other.
- `proofs.direct.ch4-ex14`: no hypothesis about $n$, so split into even and odd cases.
- `proofs.direct.ch4-ex15`: cases again, this time with an even goal.
