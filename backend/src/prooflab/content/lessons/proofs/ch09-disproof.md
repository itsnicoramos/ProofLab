---
chapter: 9
title: Disproof
topic: disproof
book: hammack-bop3
sections: ["9.1 Counterexamples (p. 174)", "9.2 Disproving Existence Statements (p. 176)", "9.3 Disproof by Contradiction (p. 178)"]
prerequisites: [2, 4]
minutes: 60
checkable: partly
review: draft
---

# Chapter 9: Disproof

## Why it matters
Exam questions often say "prove or disprove". Before you write anything, you have to decide whether the statement is true, and when it is false you need to show that convincingly. For most false statements one well-chosen example does it, and ProofLab checks yours exactly.

## Core ideas
1. **Disproof means proving the negation** (Section 9.1, p. 174). To show $P$ is false, prove $\sim P$. What that takes depends on the shape of $P$, so negate it first with the rules from Chapter 2.
2. **Counterexamples to "for all"** (Section 9.1, p. 174). The negation of $\forall x \in S, P(x)$ is $\exists x \in S, \sim P(x)$. So one $x$ in $S$ that makes $P(x)$ false disproves the statement. Make sure that $x$ really belongs to $S$: in this book $\mathbb{N} = \{1, 2, 3, \dots\}$, so $0$ is not a natural number.
3. **Counterexamples to conditionals** (Section 9.1, p. 174). $P(x) \Rightarrow Q(x)$ fails only when $P(x)$ is true and $Q(x)$ is false. A counterexample has to do both: satisfy the hypothesis and break the conclusion. Values that make the hypothesis false prove nothing, because the conditional is true there.
4. **Finding one** (Section 9.1, p. 174). Try small values first, including $1$, equal values, and negatives when the domain allows them. If small values keep working, look for a reason the statement could break, such as a value that makes every term share a factor. Then write the disproof: state your values and show what the hypothesis and the conclusion become.
5. **Prove or disprove** (Section 9.1, p. 174). When you aren't told which, test examples to form a guess, then commit. A statement can hold for many values and still be false, so a list of successes is never a proof. If you can't find a counterexample, that still isn't a proof: look for a reason the statement holds, and write that up.
6. **Disproving "there exists"** (Section 9.2, p. 176). The negation of $\exists x, P(x)$ is $\forall x, \sim P(x)$. That is a universal claim, so no single example can establish it: you need a proof. Example: "there is an integer $n$ with $n^2 + n$ odd" is false, because $n^2 + n = n(n + 1)$ and one of two consecutive integers is even. Cases $n = 2k$ and $n = 2k + 1$ work too.
7. **Disproof by contradiction** (Section 9.3, p. 178). To show $P$ is false, assume $P$ is true and derive a contradiction. Example: "some nonzero real number $x$ has $x^2 + 1/x^2 < 2$". If it did, then $(x - 1/x)^2 = x^2 - 2 + 1/x^2 < 0$, but the square of a real number is never negative. So the statement is false.

## Worked example
Statement: for every natural number $n$, if $n$ is odd, then $n^2 + 2$ is prime. Prove or disprove.

- Try small odd values: $n = 1$ gives $3$ and $n = 3$ gives $11$, both prime. Two successes prove nothing.
- $n = 5$ gives $27 = 3 \cdot 9$, which is not prime.
- So $n = 5$ is a counterexample: $5$ is a natural number, the hypothesis "$5$ is odd" is true, and the conclusion "$27$ is prime" is false. The statement is false. $\blacksquare$

Why did it break? When $n$ is not a multiple of 3, $n^2$ leaves remainder 1 after division by 3, so $n^2 + 2$ is a multiple of 3. That number is prime only if it equals 3, which happens only for $n = 1$. So $n = 7$ and $n = 11$ are counterexamples too.

In ProofLab the steps are optional notes for your own working, and the values go in the answer box:

```
expr  5^2 + 2
note  27 = 3 times 9, so the conclusion fails while 5 is odd
```

Answer box: `n = 5`.

## Typing it into ProofLab
Chapter 9 problems are `counterexample`. ProofLab checks only the answer box.

- Type one `name = integer` for every variable, separated by commas: `n = 5`, or `a = 3, b = -7`.
- Each value must be an integer in the stated domain. "Natural number" means $1, 2, 3, \dots$; "integer" also allows $0$ and negatives.
- ProofLab evaluates the statement at your values. For a conditional it needs the hypothesis true and the conclusion false; for a plain "for all" claim it needs the claim false.
- Steps (`expr`, `note`) aren't checked, but writing the evaluation down is good practice, and a written disproof needs it.
- Disproving an existence statement takes a proof for every value. ProofLab's Chapter 9 problems are all counterexamples; for that kind of argument use the Chapter 6 `impossibility_proof` format.

How three attempts would go for "for all integers $a$ and $b$, if $a \mid (b + 6)$ and $a \mid b$, then $a \mid 3$":

- `a = 2, b = 1`: $2 \nmid 1$, so the hypothesis fails and nothing is disproved (ProofLab says `HYPOTHESIS_NOT_MET`).
- `a = 3, b = 3`: the hypothesis holds, but $3 \mid 3$, so the conclusion holds too (`CONCLUSION_HOLDS`).
- `a = 6, b = 6`: $6 \mid 12$ and $6 \mid 6$, while $6 \nmid 3$. This one is a counterexample (`COUNTEREXAMPLE_VALID`).

## Common mistakes
- **The conclusion still holds** (`CONCLUSION_HOLDS`). Your values satisfy the statement, so they don't break it. Recompute, or look for a value that forces a common factor.
- **The hypothesis fails** (`HYPOTHESIS_NOT_MET`). For a conditional, values that make the "if" part false can't disprove it. Check the hypothesis first, then the conclusion.
- **Outside the domain** (`COUNTEREXAMPLE_DOMAIN`, `COUNTEREXAMPLE_NOT_INTEGER`). $0$ and negative numbers are not natural numbers in this book, and fractions are never allowed.
- **Answer box format** (`COUNTEREXAMPLE_FORMAT`, `COUNTEREXAMPLE_MISSING_VALUE`). Write `a = 6, b = 6`, naming every variable, even when two values are equal.
- **One example against "there exists"** (`EXISTS_FAILS`). In Chapter 7, ProofLab answers a value that doesn't satisfy an existence statement with this code, and that is all it means: that one value doesn't work. To show no value works, you need a proof covering every value.

## Pause questions
1. Write the negation of "for every natural number $n$, $3^n + 2$ is prime". What kind of object proves that negation?
2. Why can't values that make the hypothesis false serve as a counterexample to a conditional?
3. Why is one example not enough to disprove "there is an integer $n$ with $P(n)$"?
4. Is $n = 0$ allowed as a counterexample to a statement about natural numbers? Why or why not?

## Practice route
- `proofs.disproof.ch9-ex11`: start with the smallest natural numbers.
- `proofs.disproof.ch9-ex03`: a conditional, so the hypothesis must hold while the conclusion fails.
- `proofs.disproof.ch9-ex04`: a "for all $n$, prime" claim; look for a value that forces a factor.
- `proofs.disproof.ch9-ex02`: the same idea, but small values keep giving primes for longer.
- `proofs.disproof.ch9-ex28`: the variables are integers here, so more values are allowed.
- `proofs.disproof.ch9-ex25`: a divisibility hypothesis to satisfy and two conclusions to break.
- `proofs.disproof.ch9-ex12`: three variables and a parity hypothesis to satisfy first.
