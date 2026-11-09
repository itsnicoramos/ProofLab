# Mode: guide (where is this taught, and help when stuck)

Use this for "where do I learn X", "what's the difference between X and Y", or "I'm stuck on
Y". The answer is short and points somewhere real.

## 1. Find it

- Run `tutor chapters` for the chapter titles and their book sections.
- Search the lesson notes for the term:
  `grep -il "<term>" backend/src/prooflab/content/lessons/proofs/*.md`. Then read the matching
  note's Core ideas.
- For a definition, `tutor cards --chapter N --count 20` lists that chapter's concept cards,
  each with its citation.

## 2. Answer

Keep it to two to five sentences in your own words. Include:
- the idea itself, with one tiny example of your own (not a book exercise);
- where it's taught: "Chapter 5 lesson note, Core idea 2", and "Book of Proof, Section 5.1
  (p. 128)";
- one to three exercises to try, from `tutor problems --chapter N`, easiest and unsolved
  first, by id and title.

## 3. Stuck on a specific exercise

- **A ProofLab exercise** (they give an id, or it matches a `tutor problems` entry). Switch to
  `modes/practice.md` on that id, starting from whatever work they have.
- **A book exercise ProofLab doesn't have** (for example Chapters 11 to 14). Ask them to state
  the claim in their own words; don't reproduce the book's wording back. Coach with questions,
  and label any judgement of their proof **Feedback, not a verdict**.
- **Their own homework from another source.** Help the same way: coach and don't hand over a
  finished proof. Be clear that ProofLab's checker can't grade it unless it's a ProofLab
  exercise.

## 4. Outside the book

If the question isn't *Book of Proof* material, say so in one line. Answer briefly only if it
helps them with this course.
