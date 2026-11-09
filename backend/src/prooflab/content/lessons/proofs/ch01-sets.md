---
chapter: 1
title: Sets
topic: sets
book: hammack-bop3
sections: ["1.1 Introduction to Sets (p. 3)", "1.2 The Cartesian Product (p. 8)", "1.3 Subsets (p. 12)", "1.4 Power Sets (p. 15)", "1.5 Union, Intersection, Difference (p. 18)", "1.6 Complement (p. 20)", "1.7 Venn Diagrams (p. 22)", "1.8 Indexed Sets (p. 25)", "1.9 Sets That Are Number Systems (p. 30)", "1.10 Russell's Paradox (p. 32)"]
prerequisites: []
minutes: 90
checkable: yes
review: draft
---

# Chapter 1: Sets

## Why it matters
Every later chapter talks in the language of sets: the integers a proof is about, the outcomes you count, the values a variable may take. This chapter gives you that vocabulary. Most mistakes here aren't deep. They come from misreading which things are elements and which are sets of elements, so the main skill is reading braces carefully.

## Core ideas
1. **Sets, elements and equality** (Section 1.1, p. 3). A set is a collection of things called its elements. Write $x \in A$ when $x$ is an element of $A$, and $x \notin A$ when it isn't. Order and repetition don't matter: $\{4, 9\}$, $\{9, 4\}$ and $\{9, 4, 4\}$ are the same set. Two sets are equal exactly when they have the same elements.
2. **Cardinality, with sets inside sets** (Section 1.1, p. 3). For a finite set $A$, $|A|$ is its number of elements. Count only the items separated by commas at the outermost level of braces. The set $\{7, \{7, 8\}, \emptyset\}$ has 3 elements: the number 7, the set $\{7, 8\}$ and the empty set. An element that is itself a set counts once, whatever is inside it.
3. **The empty set** (Section 1.1, p. 3). $\emptyset = \{\}$ has no elements, so $|\emptyset| = 0$. It is not the same as $\{\emptyset\}$. Picture $\{\emptyset\}$ as a box holding one empty box: it has one element.
4. **Set-builder notation** (Section 1.1, p. 3). $\{x \in S : P(x)\}$ is the set of elements of $S$ that make $P(x)$ true. Read the colon as "such that". The set $S$ matters: $\{x \in \mathbb{Z} : x^2 = 5\}$ is empty, but the same condition over $\mathbb{R}$ gives two elements. A form like $\{3x : x \in \mathbb{Z}, |x| \le 2\}$ means: run $x$ through the allowed values and collect $3x$ each time.
5. **Ordered pairs and the Cartesian product** (Section 1.2, p. 8). In an ordered pair, order matters: $(2, 5) \ne (5, 2)$. The product $A \times B$ is the set of all pairs $(a, b)$ with $a \in A$ and $b \in B$, so $|A \times B| = |A| \cdot |B|$. $A^n$ is the set of ordered lists of length $n$ with entries from $A$. Grouping matters too: $(A \times B) \times C$ has elements shaped $((a, b), c)$, while $A \times B \times C$ has $(a, b, c)$. If either factor is empty, the product is empty.
6. **Subsets** (Section 1.3, p. 12). $A \subseteq B$ means every element of $A$ is also an element of $B$. So $\emptyset \subseteq B$ and $B \subseteq B$ for every set $B$. Keep $\in$ and $\subseteq$ apart: $2 \in \{1, 2\}$ and $\{2\} \subseteq \{1, 2\}$, but $\{2\} \notin \{1, 2\}$. A set with $n$ elements has $2^n$ subsets, because each element is either in or out.
7. **Power sets** (Section 1.4, p. 15). $\mathscr{P}(A)$ is the set whose elements are all the subsets of $A$. It always contains $\emptyset$ and $A$ itself, and $|\mathscr{P}(A)| = 2^{|A|}$. Even $\mathscr{P}(\emptyset) = \{\emptyset\}$ has one element.
8. **Union, intersection, difference** (Section 1.5, p. 18). $A \cup B$ holds everything in $A$ or $B$ (or both). $A \cap B$ holds what is in both. $A - B$ holds what is in $A$ but not in $B$. Usually $A - B \ne B - A$.
9. **Complement** (Section 1.6, p. 20). First fix a universal set $U$ that contains everything under discussion. The complement $\overline{A} = U - A$ is everything in $U$ that is outside $A$. Without a fixed $U$, a complement has no meaning.
10. **Venn diagrams** (Section 1.7, p. 22). Draw sets as overlapping regions inside a rectangle for $U$, then shade. A diagram helps you guess and sanity-check facts like $\overline{A \cup B} = \overline{A} \cap \overline{B}$. A picture suggests a fact; Chapter 8 shows how to prove one.
11. **Indexed sets** (Section 1.8, p. 25). A family of sets $A_1, A_2, \ldots, A_n$, or $A_i$ for each $i$ in an index set $I$, can be combined all at once. $\bigcup_{i \in I} A_i$ holds what lies in at least one $A_i$. $\bigcap_{i \in I} A_i$ holds what lies in every $A_i$.
12. **Number systems** (Section 1.9, p. 30). You'll use $\mathbb{N} \subseteq \mathbb{Z} \subseteq \mathbb{Q} \subseteq \mathbb{R}$ all course. In this book $\mathbb{N} = \{1, 2, 3, \ldots\}$: 0 is not a natural number. The division algorithm also appears here: dividing an integer by a positive integer $d$ leaves a unique remainder between 0 and $d - 1$.
13. **Russell's paradox** (Section 1.10, p. 32). Try to form the set of all sets that are not elements of themselves, then ask whether it is an element of itself. Both answers contradict themselves. The lesson: not every description defines a set, so in practice you work inside a sensible universal set.

## Worked example
Let $A = \{n \in \mathbb{N} : 3n < 8\}$ and $B = \{w, \{w, 9\}\}$, where $w$ is a letter. List $A \times B$ and $\mathscr{P}(B)$, then find $|\mathscr{P}(A \times B)|$.

1. Unpack $A$. You need natural numbers with $3n < 8$, that is $n < 8/3$. Since $\mathbb{N}$ starts at 1, $A = \{1, 2\}$. Putting 0 in here is the classic slip.
2. Count $B$. Its elements are the letter $w$ and the set $\{w, 9\}$. So $|B| = 2$, even though three symbols appear.
3. Build $A \times B$. Pair each element of $A$ (first entry) with each element of $B$ (second entry): $\{(1, w), (1, \{w, 9\}), (2, w), (2, \{w, 9\})\}$. That is $2 \cdot 2 = 4$ pairs, as the formula predicts.
4. Build $\mathscr{P}(B)$ by listing subsets by size. Size 0: $\emptyset$. Size 1: $\{w\}$ and $\{\{w, 9\}\}$. Size 2: $B$ itself. So $\mathscr{P}(B) = \{\emptyset, \{w\}, \{\{w, 9\}\}, \{w, \{w, 9\}\}\}$, with $2^2 = 4$ elements. Note the double braces in $\{\{w, 9\}\}$: it is the subset whose only element is the set $\{w, 9\}$.
5. Count without listing. $|A \times B| = 4$, so $|\mathscr{P}(A \times B)| = 2^4 = 16$.

As ProofLab steps for the first question (steps are optional; the answer is what gets graded):
- step: `A = {1, 2}`
- step: `B = {w, {w, 9}}`
- step: `|A × B| = 4`
- answer: `{(1, w), (1, {w, 9}), (2, w), (2, {w, 9})}`

For the power set the answer would be `{∅, {w}, {{w, 9}}, {w, {w, 9}}}`, and for the last part it would be `16`.

## Typing it into ProofLab
Chapter 1 problems use the `finite_set` kind. They come from the exercises of Sections 1.1 to 1.4. The answer is one of two things:
- **A set**, listed between braces, like `{-2, 0, 5}`. Type `∅` or `{}` for the empty set. Elements can be numbers (`sqrt(3)`, `-1/2`, `pi`), letters the problem names (`a`, `c`), pairs and tuples (`(1, a)`, `(0, 1, 1)`), or sets (`{1, 2}`). A run of whole numbers can be written `1, 2, ..., 9`. Order and spacing don't matter.
- **A whole number**, when the problem asks for a cardinality, like `3`.

Sets of sets nest their braces: `{∅, {1}, {1, 2}}`. Pairs may have sets as entries: `({1}, ∅)`.

Steps are optional `expr` lines. Each is an equation, and ProofLab evaluates both sides and checks they match:
- `A = {3, 4}` checks that you unpacked a named set correctly.
- `A × B = {(3, 5), (4, 5)}` checks a product. `A x B` works too.
- `|P(A)| = 8` compares a cardinality with a number.

Operators: `∪` or `cup`, `∩` or `cap`, `−` or `-`, `×` or `x`, `A'` for a complement (only when the problem has a universal set), and `P(A)` for a power set. Add parentheses whenever you mix $\cup$, $\cap$ and $-$, as in `(A ∪ B) − C`. A `note` step holds free text and is never checked.

Don't answer in set-builder form. `{x ∈ Z : x^2 < 4}` is rejected: work out the elements and list them.

## Common mistakes
- **Zero in ℕ** (`SET_NATURALS_ZERO`). In this book $\mathbb{N}$ starts at 1. If your list or count would be right with 0 included, take it out.
- **Counting inside an element** (`SET_COUNT_INNER`). $|\{\{1, 2, 3\}\}| = 1$. Count only the items at the outermost level of braces.
- **Missing or extra braces** (`SET_BRACES`). $\{5\}$ and $\{\{5\}\}$ are different sets. When an element is a set, it keeps its own braces inside the outer ones.
- **Pairs the wrong way round** (`SET_PAIRS_REVERSED`). In $A \times B$ the first entry comes from $A$. $B \times A$ is a different set unless $A = B$ or one of them is empty.
- **Tuples grouped wrongly** (`SET_TUPLE_GROUPING`, `SET_TUPLE_LENGTH`). $(A \times B) \times C$ gives $((a, b), c)$, $A \times (B \times C)$ gives $(a, (b, c))$, and $A \times B \times C$ gives $(a, b, c)$. Match your brackets to the product as written.
- **Forgetting ∅ in a power set** (`SET_EMPTY_MISSING`, `SET_MISSING`). The empty set is a subset of every set. Before you submit, check that your list has $2^n$ subsets.
- **Elements where subsets belong** (`SET_EXTRA`). The elements of $\mathscr{P}(A)$ are sets. If $A = \{3, 2, a\}$, then $3 \notin \mathscr{P}(A)$, but $\{3\} \in \mathscr{P}(A)$.
- **Answering in set-builder form** (`SET_BUILDER`, `SET_NOT_A_LIST`). The checker compares listed elements. Find the elements first, then list them in braces.
- **Steps ProofLab can't compare** (`SET_STEP_UNLABELED`, `SET_STEP_NOT_EQUAL`, `SET_MIXED_OPERATORS`). Write each step as an equation whose sides ProofLab can evaluate, and use parentheses when operators mix.

## Pause questions
1. How many elements does $\{\emptyset, \{\emptyset\}, \{1, \emptyset\}\}$ have?
2. Is $\{2\} \in \{1, 2\}$? Is $\{2\} \subseteq \{1, 2\}$? Explain the difference in one sentence.
3. If $|A| = 3$ and $|B| = 4$, how many elements do $A \times B$ and $\mathscr{P}(A)$ have? What happens to $A \times B$ if $B = \emptyset$?
4. List $\{x \in \mathbb{N} : 2x - 1 \le 6\}$. How would your list change if 0 were a natural number?

## Practice route
- `proofs.sets.ch1-01-ex04`: list a set-builder set over $\mathbb{N}$; a direct test of the "ℕ starts at 1" rule.
- `proofs.sets.ch1-01-ex14`: the "collect $5x$" form of set-builder notation.
- `proofs.sets.ch1-01-ex29`: a cardinality where some elements are themselves sets.
- `proofs.sets.ch1-02-ex04`: unpack two set-builder factors, then form their product; try the optional steps here.
- `proofs.sets.ch1-02-ex07`: a triple product where $\emptyset$ is an element, not an empty factor.
- `proofs.sets.ch1-03-ex02`: all subsets of a set that has $\emptyset$ as one of its elements.
- `proofs.sets.ch1-04-ex05`: a power set of a power set; work from the inside out.
- `proofs.sets.ch1-04-ex11`: the hardest one; subsets of a power set with at most one element.
