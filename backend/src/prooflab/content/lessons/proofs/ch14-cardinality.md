---
chapter: 14
title: Cardinality of Sets
topic: cardinality
book: hammack-bop3
sections: ["14.1 Sets with Equal Cardinalities (p. 269)", "14.2 Countable and Uncountable Sets (p. 275)", "14.3 Comparing Cardinalities (p. 280)", "14.4 The Cantor-Bernstein-Schröder Theorem (p. 284)"]
prerequisites: [12]
minutes: 150
checkable: no
review: draft
---

# Chapter 14: Cardinality of Sets

## Why it matters
For a finite set, size is a count. For an infinite set you can't count to the end, but you can still pair its elements with the elements of another set. This chapter uses bijections and injections to compare infinite sets, and it proves that some infinite sets are strictly bigger than others.

## Core ideas
1. **Equal cardinality means a bijection** (Section 14.1, p. 269). $|A| = |B|$ means there is a bijection $f: A \to B$. For finite sets this agrees with counting. For infinite sets it is the definition, and it gives results that feel strange at first: a set can have the same cardinality as a proper subset of itself. For example, $f(n) = 2n$ is a bijection from $\mathbb{N}$ to the set of even natural numbers.
2. **How to prove $|A| = |B|$** (Section 14.1, p. 269). Give an explicit $f: A \to B$. Check that $f(a) \in B$ for every $a \in A$. Then prove $f$ is injective and surjective, as in Chapter 12. Or give $f$ and a $g: B \to A$ and check that $g(f(a)) = a$ and $f(g(b)) = b$. Equal cardinality is reflexive, symmetric and transitive, so you can chain bijections through a middle set.
3. **Intervals of real numbers** (Section 14.1, p. 269). Any two open intervals $(a, b)$ and $(c, d)$ have equal cardinality: the linear map $f(x) = c + \frac{d - c}{b - a}(x - a)$ is a bijection. A bounded interval can even match all of $\mathbb{R}$. For example, $x \mapsto \frac{x}{1 - |x|}$ is a bijection from $(-1, 1)$ to $\mathbb{R}$. Adding or removing an endpoint takes more work, or the theorem in idea 10.
4. **Countably infinite sets** (Section 14.2, p. 275). A set is countably infinite if it has the same cardinality as $\mathbb{N} = \{1, 2, 3, \ldots\}$. This cardinality is written $\aleph_0$. A set is countable if it is finite or countably infinite, and uncountable otherwise. A bijection $f: \mathbb{N} \to A$ is the same thing as a list $f(1), f(2), f(3), \ldots$ in which every element of $A$ appears exactly once. So to show $A$ is countably infinite, you can describe such a list. $\mathbb{Z}$ is countably infinite: $0, 1, -1, 2, -2, 3, -3, \ldots$
5. **Building countable sets** (Section 14.2, p. 275). A subset of a countable set is countable. If $A$ and $B$ are countable, so are $A \cup B$ and $A \times B$. For a product, list the pairs diagonal by diagonal, grouping them by the sum of their positions in the two lists. This is why $\mathbb{Q}$ is countable even though it is dense on the number line: each rational is $a/b$ for a pair of integers, and there are only countably many pairs.
6. **$\mathbb{R}$ is uncountable** (Section 14.2, p. 275). This is Cantor's diagonal argument. Suppose $f: \mathbb{N} \to (0, 1)$ were a bijection, and write each $f(n)$ as a decimal. Build a number $x$ whose $n$th digit differs from the $n$th digit of $f(n)$, for every $n$. Use only digits other than 0 and 9, so no number with two decimal expansions causes trouble. Then $x \in (0, 1)$, but $x$ differs from every $f(n)$, so $f$ is not surjective. That contradiction shows $(0, 1)$ is uncountable, and since $(0, 1)$ and $\mathbb{R}$ have equal cardinality, so is $\mathbb{R}$.
7. **Comparing sizes** (Section 14.3, p. 280). $|A| \le |B|$ means there is an injection $A \to B$. $|A| < |B|$ means there is an injection but no bijection. So $|\mathbb{N}| < |\mathbb{R}|$: the inclusion $n \mapsto n$ is an injection, and the diagonal argument shows no bijection exists. To prove $|A| < |B|$ you need both parts.
8. **Countably infinite is the smallest infinite size** (Section 14.3, p. 280). Every infinite set $A$ contains a countably infinite subset. Pick distinct elements $a_1, a_2, a_3, \ldots$ one at a time, which never gets stuck because $A$ is infinite. Then $n \mapsto a_n$ is an injection $\mathbb{N} \to A$, so $|\mathbb{N}| \le |A|$. In words: no infinite set is smaller than $\mathbb{N}$.
9. **Cantor's theorem** (Section 14.3, p. 280). For every set $A$, $|A| < |\mathcal{P}(A)|$. The injection is $a \mapsto \{a\}$. To see that no $f: A \to \mathcal{P}(A)$ is surjective, look at $D = \{a \in A : a \notin f(a)\}$. If $D = f(d)$ for some $d \in A$, then $d \in D$ exactly when $d \notin D$, which is impossible. So there is no largest infinite size: $|\mathbb{N}| < |\mathcal{P}(\mathbb{N})| < |\mathcal{P}(\mathcal{P}(\mathbb{N}))| < \cdots$. Whether some set is strictly between $\mathbb{N}$ and $\mathbb{R}$ in size is the continuum hypothesis, which the usual axioms of set theory can neither prove nor disprove.
10. **The Cantor-Bernstein-Schröder theorem** (Section 14.4, p. 284). If there is an injection $A \to B$ and an injection $B \to A$, then $|A| = |B|$. This saves you from building a bijection by hand. Example: $[0, 1]$ and $(0, 1)$. The inclusion $(0, 1) \to [0, 1]$ is an injection. The map $x \mapsto \frac{x + 1}{3}$ sends $[0, 1]$ injectively into $[1/3, 2/3]$, which sits inside $(0, 1)$. So the two intervals have equal cardinality.

## Worked example
Let $S = \{n \in \mathbb{Z} : 3 \nmid n\}$, the integers that are not multiples of 3. Show that $S$ is countably infinite.

**Plan.** $\mathbb{Z}$ is countably infinite, so it is enough to find a bijection $f: \mathbb{Z} \to S$ and chain it with a bijection $\mathbb{N} \to \mathbb{Z}$. By the division algorithm, every element of $S$ is $3t + 1$ or $3t + 2$ for exactly one integer $t$. Send the even integers to the first kind and the odd integers to the second: $f(2t) = 3t + 1$ and $f(2t + 1) = 3t + 2$ for every $t \in \mathbb{Z}$. For instance $f(0) = 1$, $f(1) = 2$, $f(2) = 4$, $f(3) = 5$, $f(-1) = -1$ and $f(-2) = -2$.

**Well defined.** Every integer is $2t$ or $2t + 1$ for exactly one $t$, so each integer gets exactly one output. The outputs $3t + 1$ and $3t + 2$ are not multiples of 3, so they lie in $S$.

**Injective.** Suppose $f(a) = f(b)$. This value leaves remainder 1 or 2 when divided by 3.
- Remainder 1: both $a$ and $b$ are even, say $a = 2s$ and $b = 2t$. Then $3s + 1 = 3t + 1$, so $s = t$ and $a = b$.
- Remainder 2: both are odd, say $a = 2s + 1$ and $b = 2t + 1$. Then $3s + 2 = 3t + 2$, so $s = t$ and $a = b$.

**Surjective.** Let $y \in S$. By the division algorithm, $y = 3t + r$ with $r \in \{0, 1, 2\}$, and $r \ne 0$ because $3 \nmid y$. If $r = 1$, then $f(2t) = y$. If $r = 2$, then $f(2t + 1) = y$.

**Spot check.** Take $y = -7$. It is $3(-3) + 2$, so $r = 2$ and $t = -3$, and the input is $2(-3) + 1 = -5$. Indeed $f(-5) = 3(-3) + 2 = -7$.

**Conclusion.** $f$ is a bijection, so $|S| = |\mathbb{Z}| = |\mathbb{N}|$, and $S$ is countably infinite.

A second route is to list $S$ directly: $1, -1, 2, -2, 4, -4, 5, -5, 7, -7, \ldots$ This works because $n \in S$ exactly when $-n \in S$, and every element appears once, at a finite position.

## Typing it into ProofLab
ProofLab can't check this chapter yet. Write your proof out in full and the tutor gives feedback, not a verdict. Structure it like this:
- **Equal cardinality.** State $f$ with its domain and codomain. Show $f(a)$ lands in the codomain. Prove injective, then surjective, or give an inverse $g$ and check both compositions. End with "$|A| = |B|$".
- **Countably infinite.** Give a bijection with $\mathbb{N}$ (remember it starts at 1), or with a set you already know is countably infinite, such as $\mathbb{Z}$. Or describe a list and explain why every element appears and none repeats.
- **Uncountable.** Assume a bijection with $\mathbb{N}$ (or a complete list) exists. Construct an element of the set that the list misses. Explain why it is in the set and why it differs from every listed element. Conclude by contradiction.
- **Strictly smaller.** Give an injection $A \to B$, then prove that no bijection exists.
- **Cantor-Bernstein-Schröder.** Give both injections. For each, check that it lands in the right set and that it is injective. Then cite the theorem.

## Common mistakes
- **Stopping at an injection**. An injection $A \to B$ only gives $|A| \le |B|$. For equality you also need surjectivity, or an injection the other way.
- **Forgetting that $\mathbb{N}$ starts at 1**. A formula that works on $\{0, 1, 2, \ldots\}$ may be off by one on $\mathbb{N}$. Check the first few values of your map.
- **Showing that one function fails**. If your $f: A \to B$ is not a bijection, that says nothing about $|A|$ and $|B|$. To prove no bijection exists, argue about every possible function, as the diagonal argument does.
- **A list that never reaches some elements**. "All the positive integers, then all the negative ones" is not a list: no negative number gets a finite position. Interleave instead.
- **A loose diagonal argument**. The new number must differ from $f(n)$ in the $n$th digit for every $n$, and it must belong to the set. Avoid the digits 0 and 9 so that a number like $0.4999\ldots = 0.5000\ldots$ can't break it.
- **Using the diagonal argument on $\mathbb{Q}$**. The number it builds is usually irrational, so it isn't missing from any list of rationals. $\mathbb{Q}$ is countable.
- **Not checking the codomain**. Your map must land in the target set. In the worked example, that means checking the outputs are not multiples of 3.
- **Treating dense as uncountable**. Between any two rationals there is another, yet $\mathbb{Q}$ is countable. Density and size are different properties.
- **Assuming all infinite sets have the same size**. $\mathbb{N}$, $\mathbb{Z}$ and $\mathbb{Q}$ do, but $\mathbb{R}$ and $\mathcal{P}(\mathbb{N})$ are bigger. Decide which case you are in before you look for a bijection.

## Pause questions
1. What must you show to prove two infinite sets have the same cardinality?
2. Why is the list $0, 1, -1, 2, -2, \ldots$ enough to show $\mathbb{Z}$ is countably infinite?
3. In Cantor's diagonal argument, what does the constructed number show about the assumed bijection?
4. If you have an injection $A \to B$ and an injection $B \to A$, what can you conclude, and which theorem gives it?

## Practice route
- Chapter 14 exercises, Section 14.1 set, early ones: build explicit bijections between two sets and check both properties (statements not reproduced; read them in your copy of the book)
- Chapter 14 exercises, Section 14.1 set, later ones: bijections between intervals, or between $\mathbb{N}$ and a set of integers or pairs (statements not reproduced; read them in your copy of the book)
- Chapter 14 exercises, Section 14.2 set: prove sets are countable or uncountable, by a list or by a diagonal argument (statements not reproduced; read them in your copy of the book)
- Chapter 14 exercises, Section 14.3 set: compare cardinalities with injections and use Cantor's theorem (statements not reproduced; read them in your copy of the book)
- Chapter 14 exercises, Section 14.4 set: prove equal cardinality with two injections (statements not reproduced; read them in your copy of the book)
