---
chapter: 13
title: Proofs in Calculus
topic: calculus-proofs
book: hammack-bop3
sections: ["13.1 The Triangle Inequality (p. 245)", "13.2 Definition of a Limit (p. 246)", "13.3 Limits That Do Not Exist (p. 249)", "13.4 Limit Laws (p. 251)", "13.5 Continuity and Derivatives (p. 256)", "13.6 Limits at Infinity (p. 258)", "13.7 Sequences (p. 261)", "13.8 Series (p. 265)"]
prerequisites: [4, 6]
minutes: 180
checkable: no
review: draft
---

# Chapter 13: Proofs in Calculus

## Why it matters
Calculus courses usually describe a limit loosely: "$f(x)$ gets close to $L$". This chapter turns that into a precise definition and shows you how to prove limits, continuity and convergence from it. The pattern of answering every $\varepsilon$ with a $\delta$ or an $N$ runs through all of real analysis.

## Core ideas
1. **Absolute value and the triangle inequality** (Section 13.1, p. 245). $|x - a|$ is the distance between $x$ and $a$, and $|x - a| < r$ means $a - r < x < a + r$. The triangle inequality says $|x + y| \le |x| + |y|$ for all real $x$ and $y$. Two forms you will use often: $|a - c| \le |a - b| + |b - c|$ (a detour through $b$ is never shorter), and $\big| |x| - |y| \big| \le |x - y|$.
2. **The definition of a limit** (Section 13.2, p. 246). $\lim_{x \to c} f(x) = L$ means: for every $\varepsilon > 0$ there is a $\delta > 0$ such that $0 < |x - c| < \delta$ implies $|f(x) - L| < \varepsilon$. Read it as a challenge and a reply. Someone names any tolerance $\varepsilon$. You reply with a $\delta$ that keeps $f(x)$ within $\varepsilon$ of $L$ for every $x$ that close to $c$. The condition $0 < |x - c|$ means the value at $c$ itself never matters.
3. **Scratch work, then proof** (Section 13.2, p. 246). Find $\delta$ in scratch work. Start from $|f(x) - L|$, rewrite it until a factor $|x - c|$ appears, and see how small $|x - c|$ must be. Then write the proof forwards: "Let $\varepsilon > 0$. Put $\delta = \ldots$. Suppose $0 < |x - c| < \delta$. Then $\ldots < \varepsilon$." For a linear $f(x) = mx + b$ with $m \ne 0$, $|f(x) - f(c)| = |m| \, |x - c|$, so $\delta = \varepsilon / |m|$ works.
4. **Bounding the extra factor** (Section 13.2, p. 246). For a non-linear $f$, $|f(x) - L|$ is usually $|x - c|$ times a factor that depends on $x$. First require $|x - c| < 1$ (or another fixed amount) to get a bound $B$ on that factor. Then also require $|x - c| < \varepsilon / B$. Taking $\delta = \min(1, \varepsilon / B)$ gives both at once. Your $\delta$ may depend on $\varepsilon$ and $c$, but never on $x$.
5. **Limits that do not exist** (Section 13.3, p. 249). To prove $\lim_{x \to c} f(x)$ does not exist, show that no $L$ works. Negating the definition: for each $L$ there is an $\varepsilon > 0$ such that for every $\delta > 0$, some $x$ with $0 < |x - c| < \delta$ has $|f(x) - L| \ge \varepsilon$. A jump is the typical case. For the floor function at $c = 3$, values just left of 3 are 2 and values just right of 3 are 3. Whatever $L$ is, $|2 - L| + |3 - L| \ge 1$, so one side is at least $1/2$ away from $L$. Take $\varepsilon = 1/2$, and for any $\delta$ pick a point on that side within $\delta$ of 3.
6. **Limit laws** (Section 13.4, p. 251). If $\lim_{x \to c} f(x) = L$ and $\lim_{x \to c} g(x) = M$, then $f + g$ has limit $L + M$, $fg$ has limit $LM$, and $f/g$ has limit $L/M$ when $M \ne 0$. The sum law shows the standard trick. Get $f$ within $\varepsilon/2$ of $L$ and $g$ within $\varepsilon/2$ of $M$, take the smaller of the two deltas, and add using the triangle inequality. The product and quotient laws also need $g$ to stay bounded near $c$, or bounded away from 0.
7. **Continuity and derivatives** (Section 13.5, p. 256). $f$ is continuous at $c$ if $\lim_{x \to c} f(x) = f(c)$. In the $\varepsilon$-$\delta$ form you can drop the $0 <$, since $x = c$ gives $|f(c) - f(c)| = 0$. The derivative is $f'(c) = \lim_{h \to 0} \frac{f(c + h) - f(c)}{h}$, when that limit exists. A function differentiable at $c$ is continuous at $c$: write $f(x) - f(c) = \frac{f(x) - f(c)}{x - c} \cdot (x - c)$ and use the product law.
8. **Limits at infinity and infinite limits** (Section 13.6, p. 258). $\lim_{x \to \infty} f(x) = L$ means: for every $\varepsilon > 0$ there is an $N$ such that $x > N$ implies $|f(x) - L| < \varepsilon$. You now choose $N$ instead of $\delta$. Example: for $f(x) = \frac{4x + 1}{x + 2}$, $|f(x) - 4| = \frac{7}{x + 2} < \frac{7}{x}$ when $x > 0$, so $N = 7/\varepsilon$ works. For $\lim_{x \to c} f(x) = \infty$, the challenge is a large number $M$ instead of $\varepsilon$: find $\delta$ so that $0 < |x - c| < \delta$ forces $f(x) > M$.
9. **Sequences** (Section 13.7, p. 261). A sequence $a_1, a_2, a_3, \ldots$ converges to $L$ if for every $\varepsilon > 0$ there is an $N$ such that $n > N$ implies $|a_n - L| < \varepsilon$. Example: $a_n = \frac{3n - 2}{n + 5}$ has $|a_n - 3| = \frac{17}{n + 5} < \frac{17}{n}$, so any $N \ge 17/\varepsilon$ works. A sequence diverges when no $L$ works; $a_n = (-1)^n$ is the standard example. A sequence has at most one limit.
10. **Series** (Section 13.8, p. 265). A series $\sum_{k=1}^{\infty} a_k$ converges to $S$ when its partial sums $s_n = a_1 + a_2 + \cdots + a_n$ form a sequence converging to $S$. So a question about a series is a question about the sequence $s_n$. If a series converges then $a_k \to 0$. The converse fails: the harmonic series $\sum 1/k$ diverges even though $1/k \to 0$. For $r \ne 1$ the geometric sums are $1 + r + \cdots + r^n = \frac{1 - r^{n+1}}{1 - r}$, so $\sum_{k=0}^{\infty} r^k$ converges, to $\frac{1}{1 - r}$, exactly when $|r| < 1$.

## Worked example
Prove that $\lim_{x \to -1} (2x^2 - x) = 3$.

**Scratch work.** Here $c = -1$, so $|x - c| = |x + 1|$. Factor: $|(2x^2 - x) - 3| = |2x^2 - x - 3| = |2x - 3| \, |x + 1|$. The factor $|2x - 3|$ needs a bound. If $|x + 1| < 1$, then $-2 < x < 0$, so $-7 < 2x - 3 < -3$, and therefore $|2x - 3| < 7$. Then $|f(x) - 3| < 7 |x + 1|$, which is less than $\varepsilon$ once $|x + 1| < \varepsilon/7$. So take $\delta = \min(1, \varepsilon/7)$.

**Proof.** Let $\varepsilon > 0$ and put $\delta = \min(1, \varepsilon/7)$. Suppose $0 < |x + 1| < \delta$.
- Since $\delta \le 1$, we have $|x + 1| < 1$, so $-2 < x < 0$ and $|2x - 3| < 7$.
- Since $\delta \le \varepsilon/7$, we have $|x + 1| < \varepsilon/7$.

Therefore $|(2x^2 - x) - 3| = |2x - 3| \, |x + 1| < 7 \cdot \frac{\varepsilon}{7} = \varepsilon$. This shows $\lim_{x \to -1} (2x^2 - x) = 3$.

**Why the minimum matters.** Suppose you used only $\delta = \varepsilon/7$. For a large tolerance such as $\varepsilon = 70$ that gives $\delta = 10$, which allows $x = 8$. There $|2x - 3| = 13$, so the bound of 7 is false, and indeed $|f(8) - 3| = 117 > 70$. The 1 in the minimum keeps $x$ close enough to $-1$ for the bound to hold.

**Sanity check.** With $\varepsilon = 0.07$ the proof gives $\delta = 0.01$. At $x = -0.99$, $2x^2 - x = 1.9602 + 0.99 = 2.9502$, which is within $0.0498$ of 3, inside the tolerance.

## Typing it into ProofLab
ProofLab can't check this chapter yet. Write your proof out in full and the tutor gives feedback, not a verdict. Structure it like this:
- **Scratch work, labelled as scratch.** Show how you found $\delta$ (or $N$). It is not part of the proof, but it helps the tutor see your thinking.
- **First line: the arbitrary tolerance.** "Let $\varepsilon > 0$." For an infinite limit, "Let $M > 0$."
- **Second line: your choice.** "Put $\delta = \ldots$" (or "Put $N = \ldots$"), using only $\varepsilon$ and fixed numbers.
- **Third line: the assumption.** "Suppose $0 < |x - c| < \delta$" (or "Suppose $x > N$", or "Suppose $n > N$").
- **The chain.** A chain of $=$, $\le$ and $<$ steps from $|f(x) - L|$ down to $\varepsilon$. Say which fact justifies each inequality: the triangle inequality, or the bound you got from $\delta \le 1$.
- **The conclusion.** Restate the limit you proved.
- **For non-existence.** Fix an arbitrary $L$, name your $\varepsilon$, then let $\delta > 0$ be arbitrary and produce a specific $x$ with $0 < |x - c| < \delta$ and $|f(x) - L| \ge \varepsilon$.
- **For limit laws.** Write each hypothesis as its own $\varepsilon$-$\delta$ statement with its own $\delta_1$, $\delta_2$, and say how you combine them.
- **For series.** Find the partial sums $s_n$ in closed form if you can, then prove the limit of that sequence.

## Common mistakes
- **A $\delta$ that depends on $x$**. Something like $\delta = \varepsilon / |2x - 3|$ is not allowed, because $\delta$ must be chosen before $x$. Bound the extra factor by a number first.
- **Writing the scratch work as the proof**. Scratch work runs backwards from the goal. The proof must start from $0 < |x - c| < \delta$ and arrive at $|f(x) - L| < \varepsilon$.
- **Using a specific $\varepsilon$**. Showing it works for $\varepsilon = 0.1$ proves nothing. $\varepsilon$ is arbitrary, so your $\delta$ is a formula in $\varepsilon$.
- **Forgetting the minimum**. If your bound on the extra factor used $|x - c| < 1$, then $\delta$ must also be at most 1. That is why $\delta = \min(1, \varepsilon/B)$.
- **The wrong bound from an interval**. From $-7 < 2x - 3 < -3$, the bound on $|2x - 3|$ is 7, the larger size of the two ends, not 3.
- **Swapping quantifiers in a negation**. "The limit does not exist" means: for every $L$ there is an $\varepsilon$ such that for every $\delta$ some $x$ fails. Choosing $\delta$ first, or fixing one $L$ only, proves a different statement.
- **Quoting a rule instead of the definition**. When an exercise asks for an $\varepsilon$-$\delta$ proof, plugging in or using L'Hôpital's rule only tells you $L$. The proof still has to come from the definition.
- **Confusing a series with its terms**. $a_k \to 0$ does not make $\sum a_k$ converge. Convergence of a series is about the partial sums.

## Pause questions
1. In the definition of $\lim_{x \to c} f(x) = L$, which is chosen first, $\varepsilon$ or $\delta$, and why does the order matter?
2. Why does the definition require $0 < |x - c|$ and not only $|x - c| < \delta$?
3. When $|f(x) - L|$ is $|x - c|$ times another factor, why do you take $\delta$ to be a minimum of two numbers?
4. How is convergence of a series defined in terms of a sequence?

## Practice route
- Chapter 13 exercises, Section 13.2 set, early ones: $\varepsilon$-$\delta$ proofs for linear functions (statements not reproduced; read them in your copy of the book)
- Chapter 13 exercises, Section 13.2 set, later ones: quadratics and other non-linear functions, with $\delta$ as a minimum (statements not reproduced; read them in your copy of the book)
- Chapter 13 exercises, Section 13.3 set: proofs that a limit does not exist (statements not reproduced; read them in your copy of the book)
- Chapter 13 exercises, Section 13.4 set: proofs of limit laws and of limits built from them (statements not reproduced; read them in your copy of the book)
- Chapter 13 exercises, Section 13.5 set: continuity and derivatives straight from the definitions (statements not reproduced; read them in your copy of the book)
- Chapter 13 exercises, Section 13.6 set: limits at infinity and infinite limits, choosing $N$ or $M$ (statements not reproduced; read them in your copy of the book)
- Chapter 13 exercises, Section 13.7 set: convergence and divergence of sequences (statements not reproduced; read them in your copy of the book)
- Chapter 13 exercises, Section 13.8 set: series through their partial sums (statements not reproduced; read them in your copy of the book)
