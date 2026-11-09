---
chapter: 2
title: Logic
topic: logic
book: hammack-bop3
sections: ["2.1 Statements (p. 35)", "2.2 And, Or, Not (p. 39)", "2.3 Conditional Statements (p. 42)", "2.4 Biconditional Statements (p. 46)", "2.5 Truth Tables for Statements (p. 48)", "2.6 Logical Equivalence (p. 50)", "2.7 Quantifiers (p. 53)", "2.8 More on Conditional Statements (p. 56)", "2.9 Translating English to Symbolic Logic (p. 57)", "2.10 Negating Statements (p. 59)", "2.11 Logical Inference (p. 63)", "2.12 An Important Note (p. 64)"]
prerequisites: [1]
minutes: 120
checkable: partly
review: draft
---

# Chapter 2: Logic

## Why it matters
Every theorem is a statement built from smaller ones with and, or, not and if-then. If you misread what a conditional claims, you end up proving the wrong thing. This chapter pins down those meanings exactly, and truth tables give you a mechanical way to check them. The proof chapters lean hard on two facts from here: when $P \Rightarrow Q$ is true, and how to negate a statement.

## Core ideas
1. **Statements** (Section 2.1, p. 35). A statement is a sentence that is definitely true or definitely false, even if you don't know which. "91 is prime" is a statement (a false one). "$x + 2 = 7$" is an open sentence: its truth depends on $x$, so it only becomes a statement once $x$ is fixed or quantified. Capital letters $P, Q, R$ stand for statements.
2. **And, or, not** (Section 2.2, p. 39). $P \wedge Q$ is true only when both parts are true. $P \vee Q$ is true when at least one part is true, including when both are. $\sim P$ has the opposite truth value to $P$.
3. **Conditionals** (Section 2.3, p. 42). $P \Rightarrow Q$ is false in exactly one situation: $P$ true and $Q$ false. When $P$ is false, the whole statement is true whatever $Q$ is. Think of a sign on a vending machine: "if you insert a coin, a drink comes out". Only someone who paid and got nothing can show the sign is wrong. The same statement can be written "if $P$, then $Q$", "$Q$ if $P$", "$P$ only if $Q$", "$P$ is sufficient for $Q$" or "$Q$ is necessary for $P$".
4. **Biconditionals and converses** (Section 2.4, p. 46). The converse of $P \Rightarrow Q$ is $Q \Rightarrow P$, and it can have a different truth value. $P \Leftrightarrow Q$ says both directions hold, so it is true exactly when $P$ and $Q$ have the same truth value. Read it "$P$ if and only if $Q$".
5. **Truth tables** (Section 2.5, p. 48). A statement with $n$ letters has $2^n$ rows. Use the book's row order: the first letter is T for the top half and F for the bottom half, each later letter splits the blocks in half again, and the last letter alternates T, F. Work from the inside out with helper columns, and finish with the main connective (the one applied last).
6. **Logical equivalence** (Section 2.6, p. 50). Two statements are logically equivalent when their columns agree in every row. To show they are not, one row where they differ is enough. Laws to know well: DeMorgan's laws $\sim(P \wedge Q) = (\sim P) \vee (\sim Q)$ and $\sim(P \vee Q) = (\sim P) \wedge (\sim Q)$; $P \Rightarrow Q = (\sim P) \vee Q$; the contrapositive $P \Rightarrow Q = (\sim Q) \Rightarrow (\sim P)$; the distributive laws; and $\sim \sim P = P$.
7. **Quantifiers** (Section 2.7, p. 53). $\forall x \in S, P(x)$ says $P(x)$ holds for every $x$ in $S$. $\exists x \in S, P(x)$ says it holds for at least one. Order matters: $\forall x \in \mathbb{Z}, \exists y \in \mathbb{Z}, x + y = 0$ is true, but $\exists y \in \mathbb{Z}, \forall x \in \mathbb{Z}, x + y = 0$ is false.
8. **Conditionals with variables** (Section 2.8, p. 56). A sentence like "if $n^2$ ends in the digit 7, then $n$ is even" quietly means "for every integer $n$". It is true when no $n$ makes the hypothesis true and the conclusion false. No square ends in 7, so nothing can break it, and the statement is true. This is why a false hypothesis gives T in the truth table.
9. **English to symbols** (Section 2.9, p. 57). Name the basic statements first. Then look for hidden quantifiers ("every", "some", "a", "there is") and hidden conditionals ("whenever", "only if", "is necessary for"). "But" usually means $\wedge$.
10. **Negating statements** (Section 2.10, p. 59). Push the $\sim$ inward. $\sim(\forall x, P(x))$ becomes $\exists x, \sim P(x)$, and $\sim(\exists x, P(x))$ becomes $\forall x, \sim P(x)$. The negation of $P \Rightarrow Q$ is $P \wedge \sim Q$, not another conditional. So "if $n$ is prime, then $n$ is odd" is false because there is a prime that is even.
11. **Logical inference** (Section 2.11, p. 63). From $P \Rightarrow Q$ and $P$ you may conclude $Q$ (modus ponens). From $P \Rightarrow Q$ and $\sim Q$ you may conclude $\sim P$ (modus tollens). From $P \Rightarrow Q$ and $Q \Rightarrow R$ you get $P \Rightarrow R$. Each rule can be checked row by row with a truth table.
12. **Symbols are a tool, proofs are prose** (Section 2.12, p. 64). Symbolic logic helps you see how statements fit together. Written proofs still use full sentences, so don't drop $\Rightarrow$ or $\wedge$ into the middle of your prose.

## Worked example
Decide whether $(P \vee Q) \Rightarrow R$ and $(P \Rightarrow R) \vee (Q \Rightarrow R)$ are logically equivalent.

1. Three letters means $2^3 = 8$ rows. For $(P, Q, R)$ they go TTT, TTF, TFT, TFF, FTT, FTF, FFT, FFF.
2. Left side. The helper column $P \vee Q$ is T T T T T T F F. An implication is false only when its hypothesis is T and its conclusion is F, and $R$ alternates T, F. So the left column is T F T F T F T T. The last two rows are T because the hypothesis $P \vee Q$ is false there.
3. Right side. $P \Rightarrow R$ is T F T F T T T T (all T in the bottom half, where $P$ is false). $Q \Rightarrow R$ is T F T T T F T T. Joining them with $\vee$ gives T F T T T T T T.
4. Compare. The columns differ in row 4 ($P = T$, $Q = F$, $R = F$) and in row 6. In row 4 the left side is $T \Rightarrow F$, which is F. On the right, $Q \Rightarrow R$ is $F \Rightarrow F$, which is T, so the "or" is T. One differing row settles it: **not equivalent**.
5. Change the $\vee$ on the right to $\wedge$ and the two statements become equivalent. A chain of rewrites shows it, one law per line: start with $(P \vee Q) \Rightarrow R$; rewrite the implication as $\sim(P \vee Q) \vee R$; apply DeMorgan to get $(\sim P \wedge \sim Q) \vee R$; distribute to get $(\sim P \vee R) \wedge (\sim Q \vee R)$; turn each part back into an implication, $(P \Rightarrow R) \wedge (Q \Rightarrow R)$.

As ProofLab steps for the first question (a `logical_equivalence` problem that asks you to decide):
- row step: `P = T, Q = F, R = F`
- answer: `not equivalent`

Or with both columns instead of a row:
- column step: `(P ∨ Q) ⇒ R : T F T F T F T T`
- column step: `(P ⇒ R) ∨ (Q ⇒ R) : T F T T T T T T`
- answer: `not equivalent`

For the equivalent pair in step 5, the chain goes in as `expr` steps, one statement each:
- `(P ∨ Q) ⇒ R`
- `~(P ∨ Q) ∨ R`
- `(~P ∧ ~Q) ∨ R`
- `(~P ∨ R) ∧ (~Q ∨ R)`
- `(P ⇒ R) ∧ (Q ⇒ R)`

## Typing it into ProofLab
ProofLab checks Sections 2.5 and 2.6: truth tables and logical equivalence. It doesn't check quantifiers, translations from English, negations written in words, or inference. Practise those on paper with your tutor.

Connectives: `~` for not, `∧` or `&` for and, `∨` or `|` for or, `⇒` or `=>` for implies, `⇔` or `<=>` for if and only if. Statement letters are single capitals. A `~` applies only to what comes right after it, so `~P ∨ Q` means $(\sim P) \vee Q$. If you mix $\wedge$ with $\vee$, or chain two $\Rightarrow$, add parentheses; ProofLab won't guess.

**`truth_table` problems.**
- The answer is the final column: T/F values top to bottom in the book's row order, like `T F F T`.
- Helper columns are optional `column` steps written `statement : values`, like `Q ⇒ R : T F T T T F T T`. Each one is checked.
- "Find the truth values" problems take an answer like `P = T, Q = T, R = F, S = F`.

**`logical_equivalence` problems.** Back up your claim in one of three ways:
- Two `column` steps, one for each statement, with matching values.
- A chain of `expr` steps from the left statement to the right one, each equivalent to the one before. Going straight from the first statement to the last doesn't count as work.
- For "not equivalent", a `row` step like `P = F, Q = F` where the two statements differ.

When the problem asks you to decide, type `equivalent` or `not equivalent` as the answer. Otherwise there is no answer box. A `note` step holds text and is never checked.

## Common mistakes
- **F ⇒ F read as false** (`IMPLIES_AS_AND`, `TT_ROWS_WRONG`). A conditional with a false hypothesis is true. Only $T \Rightarrow F$ gives F.
- **Turning the arrow around** (`IMPLIES_CONVERSE`, `IMPLIES_INVERSE`). $Q \Rightarrow P$ and $\sim P \Rightarrow \sim Q$ say something different from $P \Rightarrow Q$. Only the contrapositive $\sim Q \Rightarrow \sim P$ is equivalent to it.
- **Rewriting ⇒ without the ~** (`IMPLIES_AS_OR`). $P \Rightarrow Q$ becomes $(\sim P) \vee Q$: the hypothesis gets negated.
- **Mixing up ⇒ and ⇔** (`IFF_AS_IMPLIES`, `IMPLIES_AS_IFF`). In the row $P = F$, $Q = T$, the statement $P \Rightarrow Q$ is true but $P \Leftrightarrow Q$ is false.
- **DeMorgan done halfway** (`DEMORGAN_CONNECTIVE`, `NEGATION_SCOPE`). To push $\sim$ into $\sim(P \wedge Q)$, negate both parts and flip $\wedge$ to $\vee$. Negating only one part, or keeping the same connective, changes the meaning.
- **A lost or misplaced ~** (`NEGATION_DROPPED`, `TT_ALL_FLIPPED`). If every value in your column is the opposite of what it should be, check the outermost $\sim$ or the main connective.
- **∧ and ∨ swapped** (`AND_OR_SWAPPED`). "And" needs both parts true; "or" needs at least one.
- **Rows in your own order** (`TT_ROW_ORDER`, `TT_WRONG_LENGTH`). Use $2^n$ rows in the book's order, with the first letter T in the top half.
- **Missing parentheses** (`LOGIC_AMBIGUOUS`). $P \vee Q \wedge R$ could mean two different statements. Add brackets.
- **Weak evidence for a claim** (`LOGIC_ROW_SAME`, `LOGIC_INCOMPLETE`, `LOGIC_NO_WORK`, `LOGIC_STEP_NOT_EQUIVALENT`). A row proves "not equivalent" only if the two sides differ there. One column alone isn't a comparison. A rewrite chain needs real middle steps, each equivalent to the one before.

## Pause questions
1. Is "if 7 is even, then $7^2$ is even" true or false? Which row of the $\Rightarrow$ table is it?
2. A table for $P, Q, R, S$ has how many rows, and what are the values of $P, Q, R, S$ in row 3?
3. Why does one row prove two statements are not equivalent, while proving they are equivalent needs every row?
4. Write the negation of "for every integer $n$, if $n$ is odd then $n^2 + 1$ is even", with the $\sim$ pushed all the way in.

## Practice route
- `proofs.logic.ch2-05-ex03`: a two-letter table where a $\sim$ sits outside an implication.
- `proofs.logic.ch2-05-ex07`: a conditional whose hypothesis is never true; see what that does to the column.
- `proofs.logic.ch2-05-ex01`: eight rows and a helper column for $Q \Rightarrow R$.
- `proofs.logic.ch2-05-ex10`: reason backwards from "this implication is false" without a full table.
- `proofs.logic.ch2-06-ex03`: show $P \Rightarrow Q$ and $(\sim P) \vee Q$ agree, with two column steps.
- `proofs.logic.ch2-06-ex04`: one of DeMorgan's laws by truth table.
- `proofs.logic.ch2-06-ex12`: decide an equivalence and back it up with a rewrite chain.
- `proofs.logic.ch2-06-ex11`: a pair that is not equivalent; find the one row that proves it.
