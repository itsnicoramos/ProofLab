---
chapter: 12
title: Functions
topic: functions
book: hammack-bop3
sections: ["12.1 Functions (p. 223)", "12.2 Injective and Surjective Functions (p. 228)", "12.3 The Pigeonhole Principle Revisited (p. 233)", "12.4 Composition (p. 235)", "12.5 Inverse Functions (p. 238)", "12.6 Image and Preimage (p. 242)"]
prerequisites: [1, 11]
minutes: 150
checkable: no
review: draft
---

# Chapter 12: Functions

## Why it matters
You have used functions for years as formulas. This chapter makes them precise as sets of pairs, so you can prove things about them. Injective, surjective and bijective are the words the rest of the course uses, and Chapter 14 relies on bijections to compare the sizes of infinite sets.

## Core ideas
1. **A function is a special relation** (Section 12.1, p. 223). A function $f: A \to B$ is a relation from $A$ to $B$ in which every $a \in A$ is the first coordinate of exactly one pair. You write $f(a) = b$ for $(a, b) \in f$. $A$ is the domain and $B$ is the codomain. The range is the set of outputs that actually occur, $\{f(a) : a \in A\}$. It can be smaller than $B$.
2. **Being a function is something you check** (Section 12.1, p. 223). A rule defines a function $A \to B$ only if every input in $A$ gets an output, that output is unique, and it lies in $B$. For example, $x \mapsto 1/(x - 4)$ is not a function $\mathbb{R} \to \mathbb{R}$, because $4$ has no output, but it is a function $\mathbb{R} - \{4\} \to \mathbb{R}$. Two functions are equal when they have the same domain, the same codomain and the same output at every input.
3. **Injective** (Section 12.2, p. 228). $f$ is injective (one-to-one) if different inputs always give different outputs. The form you usually prove is the contrapositive: if $f(a) = f(a')$ then $a = a'$. Start with "Suppose $f(a) = f(a')$", do algebra, and end with $a = a'$. To show $f$ is not injective, give two specific different inputs with the same output.
4. **Surjective** (Section 12.2, p. 228). $f$ is surjective (onto) if every $b \in B$ is an output: some $a \in A$ has $f(a) = b$. Start with "Let $b \in B$". Find $a$ in scratch work by solving $f(a) = b$. Check that this $a$ really is in $A$, then compute $f(a) = b$. To show $f$ is not surjective, give one specific $b$ and show no $a$ works. For example, $g: \mathbb{Z} \to \mathbb{Z}$ with $g(n) = 3n + 1$ is injective but not surjective, since $3n + 1 = 2$ forces $n = 1/3 \notin \mathbb{Z}$.
5. **Bijective** (Section 12.2, p. 228). A bijection is both injective and surjective: every element of $B$ is the output of exactly one element of $A$. The domain and codomain matter. The same formula can be a bijection between some sets and not between others.
6. **The pigeonhole principle for functions** (Section 12.3, p. 233). For finite sets: if $|A| > |B|$, no function $A \to B$ is injective; if $|A| < |B|$, no function $A \to B$ is surjective. If $|A| = |B|$ and both are finite, a function $A \to B$ is injective exactly when it is surjective. To use it, decide what plays $A$ (the pigeons), what plays $B$ (the boxes), and what $f$ does (which box each pigeon goes in).
7. **Composition** (Section 12.4, p. 235). For $f: A \to B$ and $g: B \to C$, the composition $g \circ f: A \to C$ is $(g \circ f)(x) = g(f(x))$. You apply $f$ first. Order matters: usually $g \circ f \ne f \circ g$, and one of them may not even be defined. Composition is associative. If $f$ and $g$ are both injective, so is $g \circ f$. The same holds for surjective, and so for bijective.
8. **Inverse functions** (Section 12.5, p. 238). The inverse relation of $f$ is $f^{-1} = \{(y, x) : (x, y) \in f\}$. It is a function $B \to A$ exactly when $f$ is a bijection. Then $f^{-1}(f(x)) = x$ for every $x \in A$, and $f(f^{-1}(y)) = y$ for every $y \in B$. To find a formula, solve $y = f(x)$ for $x$. Another way to prove $f$ is a bijection: give a $g: B \to A$ and check that both compositions are identity functions.
9. **Image and preimage** (Section 12.6, p. 242). For $X \subseteq A$, the image is $f(X) = \{f(x) : x \in X\}$. For $Y \subseteq B$, the preimage is $f^{-1}(Y) = \{x \in A : f(x) \in Y\}$. The preimage makes sense for every function, even one with no inverse. With $h(x) = x^2$ on $\mathbb{R}$: $h(\{-2, 1\}) = \{1, 4\}$, $h^{-1}(\{4, 9\}) = \{-3, -2, 2, 3\}$, and $h^{-1}(\{-1\}) = \emptyset$.
10. **Proofs about images and preimages** (Section 12.6, p. 242). These are set proofs from Chapter 8: show one set is a subset of another by following an element. Preimages behave well: $f^{-1}(Y \cap Z) = f^{-1}(Y) \cap f^{-1}(Z)$, and the same with $\cup$. Images of intersections only give $f(X \cap W) \subseteq f(X) \cap f(W)$. Equality can fail when $f$ isn't injective: with $h(x) = x^2$, $X = \{-1\}$ and $W = \{1\}$, you get $h(X \cap W) = \emptyset$ but $h(X) \cap h(W) = \{1\}$.

## Worked example
Define $f: \mathbb{Z} \to \mathbb{Z}$ by $f(n) = n + 3$ if $n$ is even and $f(n) = n - 5$ if $n$ is odd. Prove $f$ is a bijection and find $f^{-1}$.

**A first observation.** If $n$ is even, $f(n) = n + 3$ is odd. If $n$ is odd, $f(n) = n - 5$ is even. So $f$ swaps parity, and the parity of $f(n)$ tells you the parity of $n$.

**Injective.** Suppose $f(a) = f(b)$. This value is odd or even.
- If it is odd, then $a$ and $b$ are both even, by the observation. So $a + 3 = b + 3$, and $a = b$.
- If it is even, then $a$ and $b$ are both odd. So $a - 5 = b - 5$, and $a = b$.

In both cases $a = b$. The observation is what rules out the mixed case, where $a$ is even, $b$ is odd and $a + 3 = b - 5$.

**Surjective.** Let $y \in \mathbb{Z}$.
- If $y$ is odd, put $a = y - 3$, which is even. Then $f(a) = (y - 3) + 3 = y$.
- If $y$ is even, put $a = y + 5$, which is odd. Then $f(a) = (y + 5) - 5 = y$.

Either way $y$ is an output, so $f$ is surjective. Being injective too, $f$ is a bijection.

**Inverse.** The surjectivity argument already found the input for each output: $f^{-1}(y) = y - 3$ if $y$ is odd, and $f^{-1}(y) = y + 5$ if $y$ is even. Check one value: $f(8) = 11$ and $f^{-1}(11) = 11 - 3 = 8$.

## Typing it into ProofLab
ProofLab can't check this chapter yet. Write your proof out in full and the tutor gives feedback, not a verdict. Structure it like this:
- **Name the function completely.** State $f: A \to B$ with its domain, codomain and rule. If there is any doubt, show it really is a function: each input gets one output, and that output is in $B$.
- **Injective part.** "Suppose $a, a' \in A$ and $f(a) = f(a')$." Then algebra, ending with "so $a = a'$". If $f$ is defined in pieces, split into cases, including the mixed case.
- **Surjective part.** "Let $b \in B$." State your choice of $a$ (do the solving in scratch work, not in the proof), show $a \in A$, and compute $f(a) = b$.
- **Not injective or not surjective.** Give specific elements and show the computation.
- **Inverse.** Prove $f$ is a bijection first. Then give $f^{-1}$ with its domain and codomain, and check that $f(f^{-1}(y)) = y$ for every $y \in B$.
- **Image and preimage proofs.** Write them as set proofs: "Let $y \in f(X \cap W)$. Then $y = f(x)$ for some $x \in X \cap W$, so..." and end with the membership you need.
- **Pigeonhole.** Say what the pigeons and the boxes are, give the function between them, and compare the two sizes.

## Common mistakes
- **Proving the converse for injectivity**. "If $a = a'$ then $f(a) = f(a')$" holds for every function and proves nothing. Start from $f(a) = f(a')$.
- **Not checking the input is in the domain**. In a surjectivity proof, solving $f(a) = b$ may give $a = b/2$ or $a = \sqrt{b}$, which might not be in $A$. Check it. If it fails for some $b$, the function may not be surjective.
- **Ignoring the codomain**. Whether $f$ is surjective depends on $B$. The rule $x \mapsto x^2$ is surjective onto $[0, \infty)$ but not onto $\mathbb{R}$. Always state the domain and codomain.
- **Mixing up range and codomain**. The codomain is the set named in $f: A \to B$. The range is what $f$ actually hits. They are equal exactly when $f$ is surjective.
- **Reading $g \circ f$ left to right**. $(g \circ f)(x) = g(f(x))$ applies $f$ first, then $g$.
- **Writing $f^{-1}$ for a function that isn't bijective**. An inverse function exists only for a bijection. The preimage $f^{-1}(Y)$ of a set is always defined, but it is a set, not a value of an inverse function.
- **Assuming $f(X \cap W) = f(X) \cap f(W)$**. Only $\subseteq$ holds in general. Test claims like this on $x \mapsto x^2$ before you try to prove them.
- **Missing the mixed case**. For a function defined in pieces, an injectivity proof must handle inputs from different pieces, as in the worked example.

## Pause questions
1. What is the difference between the codomain and the range of a function?
2. To prove $f$ is surjective, what do you assume first, and what must you check about the input you find?
3. Why does the inverse relation $f^{-1}$ only give a function when $f$ is a bijection?
4. If $|A| = 7$ and $|B| = 5$, what does the pigeonhole principle say about functions $A \to B$?

## Practice route
- Chapter 12 exercises, Section 12.1 set, early ones: decide whether a set of pairs is a function, and read off domain, codomain and range (statements not reproduced; read them in your copy of the book)
- Chapter 12 exercises, Section 12.2 set, early ones: build small finite examples that are or aren't injective and surjective (statements not reproduced; read them in your copy of the book)
- Chapter 12 exercises, Section 12.2 set, later ones: prove or disprove injective and surjective for rules on $\mathbb{Z}$, $\mathbb{R}$ or $\mathbb{Z} \times \mathbb{Z}$ (statements not reproduced; read them in your copy of the book)
- Chapter 12 exercises, Section 12.3 set: pigeonhole arguments with a clear choice of pigeons and boxes (statements not reproduced; read them in your copy of the book)
- Chapter 12 exercises, Section 12.4 set: compute compositions and prove facts about them (statements not reproduced; read them in your copy of the book)
- Chapter 12 exercises, Section 12.5 set: prove a function is a bijection and find its inverse (statements not reproduced; read them in your copy of the book)
- Chapter 12 exercises, Section 12.6 set: compute images and preimages, then prove set facts about them (statements not reproduced; read them in your copy of the book)
