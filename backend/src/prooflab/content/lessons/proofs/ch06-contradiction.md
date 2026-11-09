---
chapter: 6
title: Proof by Contradiction
topic: contradiction
book: hammack-bop3
sections: ["6.1 Proving Statements with Contradiction (p. 138)", "6.2 Proving Conditional Statements by Contradiction (p. 141)", "6.3 Combining Techniques (p. 142)", "6.4 Some Words of Advice (p. 143)"]
prerequisites: [2, 4]
minutes: 90
checkable: partly
review: draft
---

# Chapter 6: Proof by Contradiction

## Why it matters
Many statements say that something never happens: an equation has no integer solutions, a number is never divisible by 4, a number is irrational. There is nothing to start a direct proof from, so you assume the opposite and show it leads somewhere impossible. Most of ProofLab's Chapter 6 problems end the same way: an integer would need two different remainders at once.

## Core ideas
1. **The method** (Section 6.1, p. 138). To prove a statement $P$, assume $\sim P$ and reason until you reach a contradiction: a statement $C$ together with $\sim C$, or a plainly false claim like $0 = 1$. Since $\sim P$ leads to something false, $\sim P$ is false, so $P$ is true. This works for any kind of statement, not just conditionals.
2. **Negate carefully** (Section 6.1, p. 138). Your first line is the negation, so it has to be right. Use the rules from Chapter 2: "there are no integers with $X$" negates to "there are integers with $X$"; "for every $n$, $4 \nmid f(n)$" negates to "for some $n$, $4 \mid f(n)$"; "$a$ or $b$ is even" negates to "$a$ and $b$ are both odd".
3. **Rational and irrational numbers** (Section 6.1, p. 138). A real number is rational if it equals $a/b$ for integers $a$ and $b$ with $b \neq 0$, and irrational otherwise. The classic contradiction proofs show that $\sqrt{2}$ is irrational and that there are infinitely many primes. ProofLab can't check those arguments yet, but learn them on paper.
4. **The remainder contradiction** (Section 6.1, p. 138). Every integer leaves exactly one remainder in $\{0, 1, \dots, d - 1\}$ when divided by $d$. So a number written as $d \cdot (\text{integer}) + 2$ can't also be a multiple of $d$. To show "$X = 0$ is impossible", show $X$ never leaves remainder 0, since $0 = d \cdot 0$ does. When you know nothing about a variable, split it into cases by its remainder and check each one.
5. **Conditionals by contradiction** (Section 6.2, p. 141). The only way $P \Rightarrow Q$ can be false is $P$ true and $Q$ false. So to prove $P \Rightarrow Q$, assume $P$ and $\sim Q$ together and derive a contradiction. Compare: a contrapositive proof assumes only $\sim Q$ and must reach the fixed target $\sim P$; a contradiction proof assumes both and may reach any contradiction.
6. **Combining techniques** (Section 6.3, p. 142). Real proofs mix methods. A contradiction proof often leans on a fact proved by contrapositive (such as "if $n^2$ is even, then $n$ is even"), and a direct proof can contain a short contradiction argument inside one step. Choose the method for each piece separately.
7. **Advice** (Section 6.4, p. 143). Say in the first line that you are assuming the opposite, and state exactly what that is. Reach for contradiction when the statement is a "no", "never" or "not" claim, or when the opposite gives you something concrete to compute with. If a direct or contrapositive proof is easy, prefer it: it is usually clearer.

## Worked example
Claim: there are no integers $n$ and $m$ with $n^2 + 3m = 11$.

- Suppose, for the sake of contradiction, that integers $n$ and $m$ satisfy $n^2 + 3m = 11$. Then $n^2 + 3m - 11 = 0$, and $0$ is a multiple of 3.
- The $3m$ term is already a multiple of 3, so everything depends on $n$. Nothing is known about $n$, so split by its remainder mod 3.
- Case $n = 3k$: $n^2 + 3m - 11 = 9k^2 + 3m - 11 = 3(3k^2 + m - 4) + 1$, remainder 1.
- Case $n = 3k + 1$: $9k^2 + 6k + 1 + 3m - 11 = 9k^2 + 6k + 3m - 10 = 3(3k^2 + 2k + m - 4) + 2$, remainder 2.
- Case $n = 3k + 2$: $9k^2 + 12k + 4 + 3m - 11 = 9k^2 + 12k + 3m - 7 = 3(3k^2 + 4k + m - 3) + 2$, remainder 2.
- In every case $n^2 + 3m - 11$ leaves remainder 1 or 2, so it isn't a multiple of 3 and can't be 0. That contradicts $n^2 + 3m = 11$, so no such integers exist. $\blacksquare$

In ProofLab this is an `impossibility_proof` with expression $n^2 + 3m - 11$, divisor 3 and forbidden remainder 0:

```
case  n = 3k
expr  9k^2 + 3m - 11
form  3(3k^2 + m - 4) + 1
case  n = 3k + 1
expr  9k^2 + 6k + 3m - 10
form  3(3k^2 + 2k + m - 4) + 2
case  n = 3k + 2
expr  9k^2 + 12k + 3m - 7
form  3(3k^2 + 4k + m - 3) + 2
```

## Typing it into ProofLab
Chapter 6 problems are `impossibility_proof`. The prompt states the assumption for contradiction and says which remainder is impossible. Your steps show that the expression always leaves a different one.

- `let`: only for a variable the problem tells you something about, including the assumption for contradiction. If the prompt says "suppose $x$ is even", type `let x = 2k`. With two such variables use two letters: `let a = 2s + 1`, then `let b = 2t + 1`.
- `case`: when nothing is known about a variable, split it: `case a = 2k` and `case a = 2k + 1`, or by 3 as above. All cases split the same variable by the same number and must cover every remainder.
- `expr`: an algebra line equal to the expression after your substitutions.
- `form`: the closing line of each case, or of the whole proof when there are no cases. It must equal the expression and be written factored: a multiple of the divisor times an integer expression, plus a constant, like `4(k^2 + 3k) + 1` or `5(2a - b) + 3`. You may put the expression in front: `n^2 + 3m - 11 = 3(3k^2 + m - 4) + 1`. Keep the constant between 0 and $d - 1$ so the remainder is plain to see.
- `note`: free text, not checked.

A one-line example with no cases: to show $14a + 35b = 2$ has no integer solutions, take the expression $14a + 35b$ with divisor 7. The single step

```
form  7(2a + 5b)
```

shows it always leaves remainder 0, while 2 leaves remainder 2.

## Common mistakes
- **Assuming the statement instead of its negation** (`BAD_REPRESENTATION`). For "if $5n + 1$ is even, then $n$ is odd", the assumption for contradiction is "$5n + 1$ is even and $n$ is even", so the let is `n = 2k`, not `n = 2k + 1`. Write the negation in words before you type.
- **A let step for an unknown variable** (`LET_WITHOUT_HYPOTHESIS`). If the problem says nothing about $n$, you can't declare it even. Use case steps that cover every remainder.
- **Missing a case** (`CASES_NOT_EXHAUSTIVE`). Splitting by 3 needs three cases; splitting by parity needs both.
- **A form that isn't factored** (`FORM_SHAPE`). `9k^2 + 3m - 11` equals the expression but hides the remainder. Pull out the divisor: `3(3k^2 + m - 4) + 1`.
- **Algebra slips** (`FORM_NOT_EQUAL`, `NOT_EQUIVALENT`). The usual culprits are the middle term of $(2k + 1)^2$ and dividing only some terms by the divisor, like writing $14a + 35b$ as $7(2a + 35b)$. Expand in an `expr` line first, then factor.
- **Ending without a form** (`FORM_INCOMPLETE`). Each case, or the whole proof, needs a closing form step. An algebra chain alone doesn't show the remainder.
- **One letter for two variables** (`SAME_FRESH_VARIABLE`, `FRESH_NOT_NEW`). If $a$ and $b$ are both odd, write $a = 2s + 1$ and $b = 2t + 1$; one shared letter assumes $a = b$. The new letter also can't be a problem variable, so with variables $n$ and $m$ don't write `n = 3m`.

## Pause questions
1. What is the negation of "for all integers $a$ and $b$, $a^2 - 5b \neq 3$"?
2. To prove $P \Rightarrow Q$ by contradiction, what do you assume, and how is that different from a contrapositive proof?
3. Why does writing $X = 5 \cdot (\text{integer}) + 3$ show that $5 \nmid X$?
4. Why does the worked example split $n$ into three cases instead of two?

## Practice route
- `proofs.contradiction.ch6-ex02`: the contradiction set-up with one let; the algebra is the easy part.
- `proofs.contradiction.ch6-ex01`: the same set-up with an odd square, so the form ends in $+ 1$.
- `proofs.contradiction.ch6-ex11`: no let at all, a single form line.
- `proofs.contradiction.ch6-ex10`: the same idea with a different divisor.
- `proofs.contradiction.ch6-ex17`: your first cases on a variable nobody told you about.
- `proofs.contradiction.ch6-ex06`: cases again, with a second variable that stays as it is.
- `proofs.contradiction.ch6-ex18`: two odd variables, so two different letters.
- `proofs.contradiction.ch6-ex08`: two lets plus cases on a third variable; the hardest one here.
