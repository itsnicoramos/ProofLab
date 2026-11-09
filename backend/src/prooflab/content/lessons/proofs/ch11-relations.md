---
chapter: 11
title: Relations
topic: relations
book: hammack-bop3
sections: ["11.1 Relations (p. 201)", "11.2 Properties of Relations (p. 205)", "11.3 Equivalence Relations (p. 210)", "11.4 Equivalence Classes and Partitions (p. 215)", "11.5 The Integers Modulo n (p. 218)", "11.6 Relations Between Sets (p. 221)"]
prerequisites: [1, 4]
minutes: 140
checkable: no
review: draft
---

# Chapter 11: Relations

## Why it matters
A relation is the general idea behind $<$, $=$, $\mid$ and "leaves the same remainder as". Treating a relation as a set lets you prove things about it with the tools from Chapters 1 and 4. Equivalence relations are how mathematics groups objects that are alike in one respect, and they lead straight to modular arithmetic and to the functions of Chapter 12.

## Core ideas
1. **A relation is a set of pairs** (Section 11.1, p. 201). A relation $R$ on a set $A$ is any subset of $A \times A$. You write $x \, R \, y$ to mean $(x, y) \in R$. Any subset counts, including $\emptyset$ and all of $A \times A$. Since a relation is a set, two relations are equal exactly when they contain the same pairs.
2. **Pictures and counting** (Section 11.1, p. 201). For a small finite $A$, draw each element as a dot and each pair $(x, y)$ as an arrow from $x$ to $y$. A pair $(x, x)$ is a loop. If $|A| = n$, then $A \times A$ has $n^2$ pairs, so there are $2^{n^2}$ relations on $A$.
3. **Reflexive, symmetric, transitive** (Section 11.2, p. 205). $R$ is reflexive if $x \, R \, x$ for every $x \in A$. It is symmetric if $x \, R \, y$ always implies $y \, R \, x$. It is transitive if $x \, R \, y$ and $y \, R \, z$ always imply $x \, R \, z$. Reflexive depends on $A$: every element of $A$ needs its loop. Symmetric and transitive are conditionals, so they can hold vacuously. The empty relation is symmetric and transitive.
4. **How to prove or disprove a property** (Section 11.2, p. 205). Each property is a "for all" statement, so a proof starts from arbitrary elements. Reflexive: "Let $x \in A$." Symmetric: "Suppose $x \, R \, y$." Transitive: "Suppose $x \, R \, y$ and $y \, R \, z$." Then unpack the definition of $R$ and work toward the conclusion. A disproof needs one specific counterexample. On $\mathbb{Z}$, the relation "$|x - y| \le 2$" is reflexive and symmetric but not transitive: $0 \, R \, 2$ and $2 \, R \, 4$, yet $|0 - 4| = 4 > 2$.
5. **Finite relations: check every case** (Section 11.2, p. 205). Take $A = \{1, 2, 3\}$ and $R = \{(1,1), (2,2), (3,3), (1,2), (2,1), (2,3)\}$. Reflexive: yes, all three loops are there. Symmetric: no, $(2,3) \in R$ but $(3,2) \notin R$. Transitive: no, $(1,2)$ and $(2,3)$ are in $R$ but $(1,3)$ is not. For transitivity, test every pair of arrows that meet head to tail, including pairs that use a loop.
6. **Equivalence relations and classes** (Section 11.3, p. 210). An equivalence relation is reflexive, symmetric and transitive. The equivalence class of $a$ is $[a] = \{x \in A : x \, R \, a\}$, the set of everything related to $a$. The main example is congruence modulo $n$ on $\mathbb{Z}$: $a \equiv b \pmod{n}$ means $n \mid (a - b)$. Its classes are the sets of integers with the same remainder when divided by $n$. A pattern worth knowing: for any function $g$ on $A$, the rule "$x \, R \, y$ when $g(x) = g(y)$" is an equivalence relation, and its classes are the sets where $g$ takes one value.
7. **Facts about classes** (Section 11.3, p. 210). For an equivalence relation, $a \in [a]$ by reflexivity, and $[a] = [b]$ exactly when $a \, R \, b$. Two classes are either equal or disjoint; they never partly overlap. To prove $[a] = [b]$, show each is a subset of the other, using symmetry and transitivity.
8. **Partitions** (Section 11.4, p. 215). A partition of $A$ is a set of nonempty subsets of $A$ that are pairwise disjoint and whose union is $A$. The classes of an equivalence relation always form a partition of $A$. In the other direction, a partition gives an equivalence relation: relate $x$ and $y$ when they lie in the same part. So equivalence relations on $A$ and partitions of $A$ match up one to one, and counting one counts the other.
9. **The integers modulo n** (Section 11.5, p. 218). $\mathbb{Z}_n$ is the set of the $n$ classes of congruence modulo $n$: $\{[0], [1], \ldots, [n - 1]\}$. Define $[a] + [b] = [a + b]$ and $[a] \cdot [b] = [ab]$. In $\mathbb{Z}_6$, $[4] + [5] = [9] = [3]$ and $[4] \cdot [5] = [20] = [2]$. The thing to prove is that these operations are well defined: if $[a] = [a']$ and $[b] = [b']$, then $[a + b] = [a' + b']$ and $[ab] = [a'b']$. For the product, write $a' = a + ns$ and $b' = b + nt$, expand $a'b'$, and collect the multiples of $n$.
10. **Relations between two sets** (Section 11.6, p. 221). A relation from $A$ to $B$ is a subset of $A \times B$. The arrows now go from one set to another, so reflexive, symmetric and transitive no longer make sense in general. This is the setting for functions: a function is a relation from $A$ to $B$ with one extra property.

## Worked example
Define $\sim$ on $\mathbb{Z}$ by $x \sim y$ when $7 \mid (x^2 - y^2)$. Show $\sim$ is an equivalence relation and describe its classes.

**Reflexive.** Let $x \in \mathbb{Z}$. Then $x^2 - x^2 = 0 = 7 \cdot 0$, so $x \sim x$.

**Symmetric.** Suppose $x \sim y$, so $x^2 - y^2 = 7a$ for some integer $a$. Then $y^2 - x^2 = 7(-a)$, and $-a$ is an integer, so $y \sim x$.

**Transitive.** Suppose $x \sim y$ and $y \sim z$, so $x^2 - y^2 = 7a$ and $y^2 - z^2 = 7b$ for integers $a$ and $b$. Adding the two equations gives $x^2 - z^2 = 7(a + b)$, so $x \sim z$.

So $\sim$ is an equivalence relation. It also fits the pattern from idea 6: $x \sim y$ exactly when $x^2$ and $y^2$ leave the same remainder mod 7.

**Classes.** Factor: $x^2 - y^2 = (x - y)(x + y)$. Since 7 is prime, 7 divides this product exactly when $7 \mid (x - y)$ or $7 \mid (x + y)$. That means $y \equiv x$ or $y \equiv -x \pmod{7}$. So the classes are:
- $[0]$, the multiples of 7;
- $[1]$, the integers congruent to 1 or 6 mod 7;
- $[2]$, the integers congruent to 2 or 5 mod 7;
- $[3]$, the integers congruent to 3 or 4 mod 7.

These four sets are nonempty, pairwise disjoint, and every integer is in one of them, so they form a partition of $\mathbb{Z}$. Notice that $\sim$ is not congruence mod 7: $1 \sim 6$, but $1 \not\equiv 6 \pmod{7}$.

## Typing it into ProofLab
ProofLab can't check this chapter yet. It has no relations checker, so write your proof out in full and the tutor gives feedback, not a verdict. Lay the proof out like this:
- **State the relation.** Say what $x \, R \, y$ means in symbols, and for elements of which set.
- **One labelled part per property.** Head each part "Reflexive", "Symmetric" or "Transitive", in that order.
- **Open with the right assumption.** Reflexive: "Let $x \in A$." Symmetric: "Suppose $x \, R \, y$." Transitive: "Suppose $x \, R \, y$ and $y \, R \, z$."
- **Unpack, work, repack.** Rewrite the assumption with the definition. For divisibility, name the integer: $x^2 - y^2 = 7a$. Do the algebra. End with the conclusion in exactly the form the definition asks for, with the new integer named.
- **Disproofs use specific elements.** Give actual elements, show they satisfy the hypothesis of the property, and show they fail its conclusion.
- **Classes as sets.** Describe each class in set-builder notation or as a list. Then say why the classes cover $A$ and why they don't overlap.
- **For $\mathbb{Z}_n$, prove well-definedness.** Start from two names for the same class, $[a] = [a']$, and show the result of the operation doesn't change.

For a small finite relation, you can list the pairs and point to the pair that breaks a property.

## Common mistakes
- **Missing loops for reflexivity**. A relation on $\{1, 2, 3\}$ with $(1,1)$ and $(2,2)$ but not $(3,3)$ is not reflexive. Check every element of $A$, not just the ones that appear in pairs.
- **Thinking symmetric means only loops**. Symmetric asks that each arrow has a reverse arrow. A pair $(x, y)$ with $x \ne y$ is fine as long as $(y, x)$ is there too.
- **Missing a transitivity case**. Check chains that go back and forth: $(1,2)$ and $(2,1)$ together force $(1,1)$.
- **Proving with one example**. Showing $3 \, R \, 3$ doesn't prove reflexivity. Start with an arbitrary element and argue in general.
- **Getting reflexive from symmetric and transitive**. The argument "$x \, R \, y$ and $y \, R \, x$ give $x \, R \, x$" needs some $y$ related to $x$, and there may be none. The empty relation on a nonempty set is a counterexample.
- **One letter for two integers**. In the transitive part, $x^2 - y^2 = 7a$ and $y^2 - z^2 = 7b$ need different letters. Using $a$ twice assumes the two multiples are equal.
- **Classes that overlap or miss elements**. If two of your classes share an element, they are the same class. If some element is in no class, a class is missing. Test your description on a few specific numbers.
- **Skipping well-definedness in $\mathbb{Z}_n$**. Computing $[a] + [b] = [a + b]$ for one choice of representatives isn't enough. Show the answer is the same for every choice.

## Pause questions
1. Why is the empty relation on $\{1, 2\}$ symmetric and transitive but not reflexive?
2. What is the first line of a proof that a relation is transitive, and what must the last line say?
3. If $R$ is an equivalence relation and $a \, R \, b$, what can you say about $[a]$ and $[b]$?
4. What does it mean for addition in $\mathbb{Z}_n$ to be well defined, and why does it need a proof?

## Practice route
- Chapter 11 exercises, Section 11.1 set, early ones: write relations as sets of pairs and draw them as arrow diagrams (statements not reproduced; read them in your copy of the book)
- Chapter 11 exercises, Section 11.2 set, early ones: decide which of the three properties a small finite relation has, with a reason for each "no" (statements not reproduced; read them in your copy of the book)
- Chapter 11 exercises, Section 11.2 set, later ones: prove or disprove the properties for relations on $\mathbb{Z}$ or $\mathbb{R}$ given by a rule (statements not reproduced; read them in your copy of the book)
- Chapter 11 exercises, Section 11.3 set: prove a relation is an equivalence relation, then describe its classes (statements not reproduced; read them in your copy of the book)
- Chapter 11 exercises, Section 11.4 set: work with partitions of small sets and the equivalence relations they give (statements not reproduced; read them in your copy of the book)
- Chapter 11 exercises, Section 11.5 set: arithmetic in $\mathbb{Z}_n$ and well-definedness arguments (statements not reproduced; read them in your copy of the book)
