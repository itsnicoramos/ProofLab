---
chapter: 3
title: Counting
topic: counting
book: hammack-bop3
sections: ["3.1 Lists (p. 65)", "3.2 The Multiplication Principle (p. 67)", "3.3 The Addition and Subtraction Principles (p. 74)", "3.4 Factorials and Permutations (p. 78)", "3.5 Counting Subsets (p. 85)", "3.6 Pascal's Triangle and the Binomial Theorem (p. 90)", "3.7 The Inclusion-Exclusion Principle (p. 93)", "3.8 Counting Multisets (p. 96)", "3.9 The Division and Pigeonhole Principles (p. 104)", "3.10 Combinatorial Proof (p. 108)"]
prerequisites: [1]
minutes: 140
checkable: yes
review: draft
---

# Chapter 3: Counting

## Why it matters
Counting comes back in probability, in computer science and in later proofs. The hard part is rarely the arithmetic. It is picking the right model: does order matter, can things repeat, and are you counting anything twice? This chapter gives you a small set of tools and the habit of asking those three questions before you multiply anything.

## Core ideas
1. **Lists** (Section 3.1, p. 65). A list is an ordered sequence of entries, like $(B, 4, B)$. Order matters and entries may repeat, so $(B, 4, B) \ne (4, B, B)$. Its length is its number of entries. Many counting questions are "how many lists of this kind are there?" in disguise.
2. **Multiplication principle** (Section 3.2, p. 67). Build each outcome in stages. If stage 1 has $n_1$ choices, stage 2 has $n_2$ choices whatever happened at stage 1, and so on, then there are $n_1 n_2 \cdots n_k$ outcomes. Lists of length $k$ from $n$ symbols number $n^k$ with repetition and $n(n-1)\cdots(n-k+1)$ without. What you choose at a stage may depend on earlier choices; how many choices you have must not.
3. **Addition and subtraction principles** (Section 3.3, p. 74). If the outcomes split into cases that don't overlap, add the case counts. If the outcomes you want are awkward to count, count everything and subtract the ones you don't want. "At least one" questions are usually easier this way.
4. **Factorials and permutations** (Section 3.4, p. 78). $n! = n(n-1)\cdots 2 \cdot 1$, and $0! = 1$. There are $n!$ ways to arrange $n$ different objects in a row. An ordered list of $k$ different objects chosen from $n$ is a $k$-permutation, and there are $P(n, k) = \frac{n!}{(n-k)!}$ of them.
5. **Counting subsets** (Section 3.5, p. 85). An $n$-element set has $\binom{n}{k} = \frac{n!}{k!\,(n-k)!}$ subsets with $k$ elements, read "$n$ choose $k$". Use it when order doesn't matter and nothing repeats. It also counts lists of 0s and 1s of length $n$ with exactly $k$ ones: you choose where the ones go.
6. **Pascal's triangle and the binomial theorem** (Section 3.6, p. 90). Each entry of the triangle is the sum of the two above it: $\binom{n+1}{k} = \binom{n}{k-1} + \binom{n}{k}$. Expanding $(x + y)^n$, the coefficient of $x^{n-k} y^k$ is $\binom{n}{k}$, because you choose which $k$ of the $n$ factors give a $y$.
7. **Inclusion-exclusion** (Section 3.7, p. 93). For two sets, $|A \cup B| = |A| + |B| - |A \cap B|$. For three, add the single sets, subtract the three pairwise overlaps, then add back the triple overlap: $|A \cup B \cup C| = |A| + |B| + |C| - |A \cap B| - |A \cap C| - |B \cap C| + |A \cap B \cap C|$.
8. **Multisets** (Section 3.8, p. 96). A multiset allows repetition but ignores order, like choosing 5 scoops from 3 flavours. Draw each choice as stars (the items) and bars (dividers between the $n$ types). With $k$ stars and $n - 1$ bars there are $\binom{k + n - 1}{k}$ multisets. The same picture counts solutions of $x_1 + \cdots + x_n = k$ in non-negative integers. If a variable has a lower bound, hand that amount out first.
9. **Division and pigeonhole** (Section 3.9, p. 104). Division: if an easier count counts each outcome you want exactly $d$ times, divide it by $d$. Arranging a word with repeated letters works this way: arrange the letters as if all were different, then divide by the ways to shuffle each repeated letter among its own copies. Pigeonhole: if more than $n$ objects go into $n$ boxes, some box gets at least two. More generally, more than $kn$ objects in $n$ boxes forces some box to hold more than $k$.
10. **Combinatorial proof** (Section 3.10, p. 108). To prove an identity, describe one set and count it in two ways. One count gives the left side and the other gives the right side, so the two sides are equal. For example, $\binom{n}{k} = \binom{n}{n-k}$: choosing the $k$ items to keep is the same as choosing the $n - k$ items to leave out.

## Worked example
A bakery has 11 different pastries, and 3 of them are croissants. You fill a box with 4 different pastries; the order in the box doesn't matter. How many boxes contain at least one croissant?

1. Pick the model. A box is a set of 4 pastries: order doesn't matter and nothing repeats. So a box is a 4-element subset of an 11-element set.
2. Count every box: $\binom{11}{4} = 330$.
3. Count the boxes you don't want, the ones with no croissant. All 4 pastries come from the 8 others: $\binom{8}{4} = 70$.
4. Subtract: $330 - 70 = 260$.
5. Check by cases on the number of croissants. The cases don't overlap, so add them. Exactly one: $\binom{3}{1}\binom{8}{3} = 168$. Exactly two: $\binom{3}{2}\binom{8}{2} = 84$. Exactly three: $\binom{3}{3}\binom{8}{1} = 8$. Total $168 + 84 + 8 = 260$, which agrees.
6. A tempting wrong route: "choose a croissant (3 ways), then any 3 of the other 10 pastries", which gives $3\binom{10}{3} = 360$. That's too big. A box with two croissants is counted twice, once for each croissant you could have chosen first, and a box with three is counted three times.

As ProofLab steps (each step is evaluated and shown, never judged; only the answer is graded):
- step: `binom(11, 4)` shows 330
- step: `binom(8, 4)` shows 70
- step: `3*binom(8, 3) + binom(3, 2)*binom(8, 2) + binom(8, 1)` shows 260
- answer: `binom(11, 4) - binom(8, 4)`

Typing `3*binom(10, 3)` as the answer would come back incorrect, with a hint that you counted some outcomes more than once.

## Typing it into ProofLab
Chapter 3 problems use the `count` kind. They come from the exercises of Sections 3.2 to 3.5, 3.7 and 3.8.

The answer is the number of outcomes. Type the number itself (`32760`) or an expression that works it out:
- powers and products: `26^4`, `5*4*3`, `3(2^6)`
- factorials: `9!`, `10!/(3! 7!)`
- choose: `binom(10, 3)`, or the book's `C(10, 3)`
- permutations: `P(10, 3)`, which means $10!/7!$
- sums and differences: `6^3 - 5^3`

An expression is often better than the final number. It records your reasoning and avoids arithmetic slips.

Steps are optional `expr` lines, each a number or an expression with only numbers in it. ProofLab works out each one and shows its value, but doesn't judge it, because a count can be reached by many correct routes. Use a `note` step for words, like "case 2: exactly two croissants". Only the final answer is graded, and it must come out to an exact whole number.

## Common mistakes
- **Order counted when it doesn't matter** (`COUNT_TOO_BIG`, `KNOWN_MISTAKE`). Hands, teams, committees and subsets are sets. If you built ordered lists, divide by the number of orderings or switch to $\binom{n}{k}$.
- **Order ignored when it matters** (`COUNT_TOO_SMALL`, `KNOWN_MISTAKE`). Offices, rankings, codes and words are lists. Different jobs or positions mean order matters.
- **Repetition mixed up** (`KNOWN_MISTAKE`). Ask whether the same symbol or person can appear twice. $15^4$ and $15 \cdot 14 \cdot 13 \cdot 12$ answer different questions.
- **"Special one first" overcounting** (`COUNT_TOO_BIG`). Choosing a required item first and then filling the rest counts some outcomes several times. Use the subtraction principle, or split into cases that don't overlap.
- **A missing case** (`COUNT_TOO_SMALL`). When you split into cases, check that they cover everything, such as numbers with 1, 2, 3 and 4 digits.
- **Subtracting the wrong set** (`KNOWN_MISTAKE`, `COUNT_TOO_BIG`). For "at least one of each kind", the unwanted outcomes are "none of the first kind" and "none of the second kind". Subtract both, then add back anything you removed twice.
- **Stopping inclusion-exclusion early** (`KNOWN_MISTAKE`, `COUNT_TOO_BIG`, `COUNT_TOO_SMALL`). Adding the single sets alone overcounts. Subtracting the pairwise overlaps but not adding back the triple overlap undercounts.
- **Stars and bars off by one** (`KNOWN_MISTAKE`). With $k$ stars and $n$ types you need $n - 1$ bars, so you choose among $k + n - 1$ symbols. Hand out lower bounds before you start.
- **A count that isn't a whole number** (`COUNT_NOT_INTEGER`, `COUNT_NEGATIVE`). If a division leaves a fraction or a subtraction goes negative, the model is wrong. Recheck what you divided by and which set you subtracted.

## Pause questions
1. A 5-character code uses the digits 0 to 9. How does your count change between "digits may repeat" and "no digit repeats"?
2. When do you use $\binom{n}{k}$ and when do you use $P(n, k)$? Give one situation for each.
3. Why is "count everything, then subtract what you don't want" usually easier for "at least one" questions?
4. To count solutions of $a + b + c = 6$ in non-negative integers with stars and bars, how many stars and how many bars do you draw?

## Practice route
- `proofs.counting.ch3-04-ex15`: filling different offices, so order matters and nobody repeats.
- `proofs.counting.ch3-02-ex07b`: the multiplication principle when the number of choices stays fixed but the choices change.
- `proofs.counting.ch3-02-ex03d`: "at least once" with repetition; count everything and subtract.
- `proofs.counting.ch3-03-ex07b`: the subtraction principle with two kinds of unwanted outcomes.
- `proofs.counting.ch3-05-ex19`: choose a suit, then choose a set of cards; order doesn't matter.
- `proofs.counting.ch3-08-ex15`: arrange a word with repeated letters and divide out the shuffles.
- `proofs.counting.ch3-07-ex05`: inclusion-exclusion with three overlapping conditions.
- `proofs.counting.ch3-08-ex11`: stars and bars, after handing out the lower bounds.
