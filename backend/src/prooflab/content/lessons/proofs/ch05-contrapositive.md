---
chapter: 5
title: Contrapositive Proof
topic: contrapositive
book: hammack-bop3
sections: ["5.1 Contrapositive Proof (p. 128)", "5.2 Congruence of Integers (p. 131)", "5.3 Mathematical Writing (p. 133)"]
prerequisites: [2, 4]
minutes: 90
checkable: partly
review: draft
---

# Chapter 5: Contrapositive Proof

## Why it matters
Some conditionals are hard to prove head on because the hypothesis gives you nothing to substitute, like "$n^2$ is even". Turning the statement into its contrapositive often hands you a hypothesis you can work with, like "$n$ is odd", and the algebra from Chapter 4 finishes the job. This chapter also introduces congruence, a short way to talk about remainders that you will use for the rest of the course.

## Core ideas
1. **The contrapositive** (Section 5.1, p. 128). The contrapositive of $P \Rightarrow Q$ is $\sim Q \Rightarrow \sim P$. The two have the same truth table, so a proof of one is a proof of the other. Keep it apart from the converse $Q \Rightarrow P$ and the inverse $\sim P \Rightarrow \sim Q$: those can be false when the original is true.
2. **How a contrapositive proof runs** (Section 5.1, p. 128). Assume the negation of the conclusion and reason directly until you reach the negation of the hypothesis. It is a direct proof of $\sim Q \Rightarrow \sim P$. For integers, "not even" means odd and "not odd" means even, so negating parity statements is easy.
3. **When to choose it** (Section 5.1, p. 128). Look at which side gives you something to substitute. If the hypothesis is about an expression (like $x^3 - 1$ or $a^2$) and the conclusion is about a single variable, a direct proof would make you solve for the variable, which usually goes nowhere. The contrapositive starts from the variable: write $x = 2a$ or $x = 2a + 1$ and expand.
4. **Congruence** (Section 5.2, p. 131). For integers $a, b$ and a natural number $n$, $a \equiv b \pmod n$ means $n \mid (a - b)$. Equivalently, $a = nk + b$ for some integer $k$. For instance $23 \equiv 5 \pmod 9$, because $23 - 5 = 18 = 9 \cdot 2$.
5. **Proving congruence statements** (Section 5.2, p. 131). Turn each congruence you are given into an equation with a fresh integer: $a \equiv b \pmod n$ becomes $a = nk + b$. Substitute into the expression you care about and factor out the modulus. To show $X \equiv r \pmod d$, write $X = d \cdot (\text{integer}) + r$. To show $d \mid X$, write $X = d \cdot (\text{integer})$. Two different congruences need two different letters.
6. **Congruence and remainders** (Section 5.2, p. 131). $a \equiv b \pmod n$ holds exactly when $a$ and $b$ leave the same remainder after division by $n$. Every integer leaves exactly one of $0, 1, \dots, d - 1$ when divided by $d$, so you can split a proof into the cases $n = dk$, $n = dk + 1$, up to $n = dk + (d - 1)$. If you already know $n$ is odd and you split by 6, only $6k + 1$, $6k + 3$ and $6k + 5$ are possible.
7. **Writing it up** (Section 5.3, p. 133). Tell the reader the method in the first line ("We prove the contrapositive"). Put words between formulas, and don't start a sentence with a symbol. Introduce every new letter with its type ("for some integer $k$"). "If $P$, then $Q$" claims only the link; "since $P$, $Q$" also claims $P$ is true, so use it only when $P$ holds.

## Worked example
Claim: let $x$ be an integer. If $x^2 - 6x + 13$ is even, then $x$ is odd.

A direct proof would start from $x^2 - 6x + 13 = 2b$ and get stuck, since you can't solve that for $x$ in a useful way. So prove the contrapositive.

- Contrapositive: if $x$ is even, then $x^2 - 6x + 13$ is odd.
- Suppose $x$ is even, so $x = 2a$ for some integer $a$.
- Then $x^2 - 6x + 13 = (2a)^2 - 6(2a) + 13 = 4a^2 - 12a + 13$.
- Split off the odd part: $4a^2 - 12a + 13 = 2(2a^2 - 6a + 6) + 1$.
- Since $2a^2 - 6a + 6$ is an integer, $x^2 - 6x + 13$ is odd. That proves the contrapositive, so the claim is true. $\blacksquare$

In ProofLab this would be a `parity_proof` with hypothesis "$x$ is even", expression $x^2 - 6x + 13$ and goal "odd". You would type:

```
let      x = 2a
expr     (2a)^2 - 6(2a) + 13
expr     4a^2 - 12a + 13
witness  2a^2 - 6a + 6
```

The witness is the $w$ in $2w + 1$, not the whole right side. An extra `expr` line `2(2a^2 - 6a + 6) + 1` before the witness is also fine.

## Typing it into ProofLab
Chapter 5 problems are `parity_proof` (goal "even" or "odd") and `divisibility_proof` (goal "$d$ divides it" or "congruent to $r$ mod $d$"). ProofLab checks a contrapositive proof as a direct proof of the contrapositive, and the prompt tells you which statement that is.

- `let`: rewrite the variable you may assume something about, using a new single letter. `n = 2a` (even), `n = 2a + 1` (odd), `a = 9k + 4` ($a \equiv 4 \pmod 9$), `a = nk + b` ($a \equiv b \pmod n$). The left side is one problem variable, never an expression like $n^2$.
- `expr`: an algebra line. Each one must equal the prompt's expression after your substitutions. Use `^` for powers; `2a` and `(nk + b)^3` multiply as you'd expect.
- `witness`: the integer $w$ that finishes the proof. The shape is $2w$ for even, $2w + 1$ for odd, $d \cdot w$ for "$d$ divides it" and $d \cdot w + r$ for "congruent to $r$ mod $d$". Type `w` alone or `m = ...`. It must be a polynomial with integer coefficients in your letters, and the remainder is the standard one ($0 \le r < d$), so odd means $2w + 1$, never $2w - 1$.
- `case`: start a case, like `n = 6k + 1`. All cases split the same variable by the same number, each ends with its own witness, and together they cover every remainder the hypothesis allows.
- `note`: free text, never checked.

When the prompt says "that is, $n \mid (a^3 - b^3)$", the expression is $a^3 - b^3$ and the shape is $n \cdot w$. A small congruence example: if $a \equiv 4 \pmod 9$, then $a^2 \equiv 7 \pmod 9$.

```
let      a = 9k + 4
expr     81k^2 + 72k + 16
witness  9k^2 + 8k + 1
```

This works because $81k^2 + 72k + 16 = 9(9k^2 + 8k + 1) + 7$.

## Common mistakes
- **Assuming the wrong statement** (`EVEN_FORM`, `ODD_FORM`, `BAD_REPRESENTATION`). The let step introduces the hypothesis of the contrapositive, which is the negated conclusion of the original. If you assume the original hypothesis instead (say `x = 2a + 1` when the contrapositive starts from "$x$ is even"), the let is rejected. Write the contrapositive in words before you type.
- **Mixing up converse, inverse and contrapositive** (`IMPLIES_CONVERSE`, `IMPLIES_INVERSE`). The Chapter 2 logic problems raise these when $P \Rightarrow Q$ is rewritten as $Q \Rightarrow P$ or $\sim P \Rightarrow \sim Q$. In a Chapter 5 proof the same slip shows up as a rejected let step. Swap the two parts and negate both.
- **Starting from the expression** (`LET_FORMAT`). `x^2 - 6x + 13 = 2a` is not a let step. A let rewrites one problem variable, like `x = 2a`.
- **A witness that isn't halved, or uses $-1$** (`WITNESS_MISMATCH`). For odd, the witness is the $w$ in $2w + 1$. If you found $2w - 1$, rewrite it as $2(w - 1) + 1$.
- **Fractions in the witness** (`WITNESS_NOT_INTEGER`, `MISSING_LET`). $(x^2 - 6x + 12)/2$ may be an integer, but nothing shows why. Substitute with a let first, then factor so the witness is a plain polynomial.
- **Reusing letters** (`SAME_FRESH_VARIABLE`, `FRESH_NOT_NEW`). $a \equiv b$ and $c \equiv d \pmod n$ become $a = ns + b$ and $c = nt + d$; one shared letter would secretly force $s = t$. The new letter also can't be one of the problem's own variables.
- **Forgetting the remainder in a congruence** (`BAD_REPRESENTATION`). $a \equiv 4 \pmod 9$ is $a = 9k + 4$, not $a = 9k$. With a letter as the modulus, $a \equiv b \pmod n$ is $a = nk + b$.
- **Cases that miss or clash** (`CASES_NOT_EXHAUSTIVE`, `CASE_CONTRADICTS_HYPOTHESIS`, `CASE_MISMATCH`). If $n$ is odd and you split by 6, you need $6k + 1$, $6k + 3$ and $6k + 5$. A case like $6k + 2$ contradicts the hypothesis, and you can't switch to a different divisor halfway.
- **Algebra slips and stopping early** (`NOT_EQUIVALENT`, `PROOF_INCOMPLETE`). Expand powers fully, middle terms included. A correct chain with no witness is valid but unfinished.

## Pause questions
1. What is the contrapositive of "if $a^2$ is not divisible by 9, then $a$ is not divisible by 3", and how does it differ from the converse?
2. Why is starting from $x = 2a$ easier than starting from $x^2 - 6x + 13 = 2b$?
3. Write $a \equiv 2 \pmod 7$ as an equation with a new integer variable.
4. If $n$ is odd and you split by the remainder mod 6, which cases do you need, and why is $6k + 4$ not one of them?

## Practice route
- `proofs.contrapositive.ch5-ex02`: the gentlest contrapositive, one let and a one-line witness.
- `proofs.contrapositive.ch5-ex01`: the same idea with an odd goal, so the witness is the $w$ in $2w + 1$.
- `proofs.contrapositive.ch5-ex15`: a cubic, where the contrapositive is clearly easier than a direct proof.
- `proofs.contrapositive.ch5-ex12`: the first divisibility goal, a multiple of 4 instead of 2.
- `proofs.contrapositive.ch5-ex20`: your first congruence, with a number as the modulus.
- `proofs.contrapositive.ch5-ex23`: a letter as the modulus; factoring beats expanding here.
- `proofs.contrapositive.ch5-ex24`: two congruences at once, so two different letters.
- `proofs.contrapositive.ch5-ex17`: needs cases by remainder; the hardest one in the chapter.
