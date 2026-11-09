---
chapter: 8
title: Proofs Involving Sets
topic: set-proofs
book: hammack-bop3
sections: ["8.1 How to Prove a ∈ A (p. 157)", "8.2 How to Prove A ⊆ B (p. 159)", "8.3 How to Prove A = B (p. 162)", "8.4 Examples: Perfect Numbers (p. 165)"]
prerequisites: [1, 4]
minutes: 90
checkable: partly
review: draft
---

# Chapter 8: Proofs Involving Sets

## Why it matters
Sets appear in every later chapter, and claims about them ("this set sits inside that one", "these two sets are equal") need proofs too. The method is always the same: translate the set statement into a statement about elements, then use the logic of Chapter 2. ProofLab checks the most common case, set identities, one line at a time.

## Core ideas
1. **Showing $a \in A$** (Section 8.1, p. 157). Unpack the definition of $A$. If $A = \{x : P(x)\}$, show $P(a)$ is true; if $A = \{x \in S : P(x)\}$, also check $a \in S$. If $A = \{f(k) : k \in \mathbb{Z}\}$, find an integer $k$ with $f(k) = a$. For example, $-14 \in \{3k + 1 : k \in \mathbb{Z}\}$ because $-14 = 3(-5) + 1$.
2. **Showing $A \subseteq B$** (Section 8.2, p. 159). $A \subseteq B$ means "if $x \in A$, then $x \in B$", so the proof is a conditional proof. Let $x$ be any element of $A$ and show $x \in B$. Example: $\{12k + 5 : k \in \mathbb{Z}\} \subseteq \{4m + 1 : m \in \mathbb{Z}\}$, because $x = 12k + 5$ gives $x = 4(3k + 1) + 1$ with $3k + 1$ an integer. You can also argue by contrapositive: assume $x \notin B$ and show $x \notin A$.
3. **Subset is not equality** (Section 8.2, p. 159). In that example, $1$ is in the second set ($m = 0$) but not the first, since $12k + 5 = 1$ forces $k = -1/3$. To show $A \not\subseteq B$, one element of $A$ outside $B$ is enough.
4. **Showing $A = B$ by two inclusions** (Section 8.3, p. 162). $A = B$ exactly when $A \subseteq B$ and $B \subseteq A$. So a full equality proof has two parts, each starting from an arbitrary element of one side.
5. **Showing $A = B$ by a chain of equivalences** (Section 8.3, p. 162). If you can rewrite "$x \in A$" step by step into "$x \in B$" so that each step says exactly the same thing (an "if and only if"), both inclusions are proved at once. The steps use Chapter 2 laws: distributing ($P \wedge (Q \vee R) = (P \wedge Q) \vee (P \wedge R)$, and the same with $\wedge$ and $\vee$ swapped), De Morgan ($\sim(P \wedge Q) = \sim P \vee \sim Q$ and $\sim(P \vee Q) = \sim P \wedge \sim Q$), and small facts like $P = P \wedge P$ and "$Q$ or (something impossible)" $= Q$.
6. **Unpacking the operations** (Section 8.3, p. 162). $x \in A \cup B$ means $x \in A$ or $x \in B$. $x \in A \cap B$ means $x \in A$ and $x \in B$. $x \in A - B$ means $x \in A$ and $x \notin B$. $x \in \overline{A}$ means $x \in U$ and $x \notin A$. $(x, y) \in A \times B$ means $x \in A$ and $y \in B$, so for products you follow a pair, not a single element.
7. **Perfect numbers** (Section 8.4, p. 165). A natural number is perfect if it equals the sum of its positive divisors other than itself, like $6 = 1 + 2 + 3$ and $28 = 1 + 2 + 4 + 7 + 14$. If $p = 2^n - 1$ is prime, then $N = 2^{n-1} p$ is perfect. Its divisors are the powers $1, 2, \dots, 2^{n-1}$, which add up to $p$, and those powers times $p$, which add up to $p^2$. All divisors together give $p(p + 1) = 2N$, and removing $N$ itself leaves $N$. Conversely, every even perfect number has this form. Nobody knows whether an odd perfect number exists.

## Worked example
Claim: for any sets $A$, $B$ and $C$, $(A - C) \cap (B \cup C) = (A \cap B) - C$.

Follow an element $x$, keeping every line equivalent to the one before it.

1. $x \in (A - C) \cap (B \cup C)$
2. $x \in A - C \text{ and } x \in B \cup C$ (definition of $\cap$)
3. $(x \in A \text{ and } x \notin C) \text{ and } (x \in B \text{ or } x \in C)$ (definitions of $-$ and $\cup$)
4. $x \in A \text{ and } (x \notin C \text{ and } (x \in B \text{ or } x \in C))$ (regroup the "and"s)
5. $x \in A \text{ and } ((x \notin C \text{ and } x \in B) \text{ or } (x \notin C \text{ and } x \in C))$ (distribute)
6. $x \in A \text{ and } (x \notin C \text{ and } x \in B)$ (the second option can never happen)
7. $(x \in A \text{ and } x \in B) \text{ and } x \notin C$ (regroup)
8. $x \in A \cap B \text{ and } x \notin C$ (definition of $\cap$)
9. $x \in (A \cap B) - C$ (definition of $-$)

Every step can be read in both directions, so the two sets have exactly the same elements. $\blacksquare$

In ProofLab every line is an `expr` step:

```
expr  x ∈ (A − C) ∩ (B ∪ C)
expr  x ∈ A − C and x ∈ B ∪ C
expr  (x ∈ A and x ∉ C) and (x ∈ B or x ∈ C)
expr  x ∈ A and (x ∉ C and (x ∈ B or x ∈ C))
expr  x ∈ A and ((x ∉ C and x ∈ B) or (x ∉ C and x ∈ C))
expr  x ∈ A and (x ∉ C and x ∈ B)
expr  (x ∈ A and x ∈ B) and x ∉ C
expr  x ∈ A ∩ B and x ∉ C
expr  x ∈ (A ∩ B) − C
```

ProofLab would also accept a shorter chain, since it only needs each line to match the one before. A written proof should still show each law you use.

## Typing it into ProofLab
Chapter 8 problems are `set_identity`. Every line is an `expr` step (with optional `note` steps), and each line is either a set or a statement about an element.

- Sets: `A ∪ B` or `A union B`, `A ∩ B` or `A intersect B`, `A − B` or `A - B`, `A × B` or `A times B`, `∅` or `emptyset`, and `A'` for the complement $\overline{A}$ when the problem has a universal set `U`.
- Statements: `x ∈ A` or `x in A`, `x ∉ A` or `x not in A`, joined with `and`, `or` and `not`. For products follow a pair: `(x, y) ∈ A × B`.
- Brackets: ProofLab won't guess how mixed operators group. `x ∈ A and x ∈ B or x ∈ C` and `A − C ∩ B` are rejected until you add brackets. A run of one operator, like `x ∈ A and x ∈ B and x ∉ C`, is fine.
- The rules: the first line must have the same elements as the left side, each line must have the same elements as the line before, and the last line must be the right side (as a set or as `x ∈ ...`). Each step is tested on every way an element can sit inside the sets, so a line that changes the meaning is always caught.
- Show work: going straight from the left side to the right side isn't a proof. Unpack a membership into and/or/not, or put a set-law line in between, like `((A − C) ∩ B) ∪ ((A − C) ∩ C)`.

## Common mistakes
- **Jumping from side to side** (`SETID_NO_WORK`). Writing the left side and then the right side shows nothing. Unpack the membership and apply one law per line.
- **De Morgan without flipping** (`SETID_STEP_DIFFERS`). $\sim(P \wedge Q)$ is $\sim P \vee \sim Q$: the "and" becomes "or", and the reverse happens for $\sim(P \vee Q)$. Keeping the same connective changes the set.
- **Distributing onto only one part** (`SETID_STEP_DIFFERS`). In $x \in C \text{ and } (x \in A \text{ or } x \notin B)$, the condition $x \in C$ has to go with both options. ProofLab names an element placement where your line and the previous one disagree; use it to find the slip.
- **Dropping a real condition** (`SETID_STEP_DIFFERS`). You may drop "or (something impossible)", but not a condition that can fail. A line that loses $x \in B$ describes a bigger set.
- **Missing brackets or unknown names** (`SETID_SYNTAX`). Mixed `and`/`or`, or mixed set operations, need brackets. Only the problem's set letters (and `U` when there is a universal set) are allowed.
- **Starting or stopping in the wrong place** (`SETID_FIRST_DIFFERS`, `SETID_INCOMPLETE`). Begin with the left side (or `x ∈` the left side), and keep going until the last line is the right side.

## Pause questions
1. What do you have to show to prove $A \subseteq B$, and what is the first sentence of that proof?
2. Why does a chain of "if and only if" steps prove both $A \subseteq B$ and $B \subseteq A$?
3. Unpack $x \in (B - A) \cup C$ into a statement that uses only $x \in$, $x \notin$, "and" and "or".
4. Why is 6 perfect but 12 not?

## Practice route
- `proofs.set-proofs.ch8-ex09`: "and" distributed over "or", the most natural first chain.
- `proofs.set-proofs.ch8-ex08`: the mirror law, "or" distributed over "and".
- `proofs.set-proofs.ch8-ex10`: De Morgan with complements, where "and" turns into "or".
- `proofs.set-proofs.ch8-ex11`: the other De Morgan law.
- `proofs.set-proofs.ch8-ex14`: a set difference whose condition must be shared by both parts.
- `proofs.set-proofs.ch8-ex12`: De Morgan and distributing in the same proof.
- `proofs.set-proofs.ch8-ex16`: your first product, following a pair $(x, y)$.
- `proofs.set-proofs.ch8-ex18`: a product with a difference; the hardest one here.
