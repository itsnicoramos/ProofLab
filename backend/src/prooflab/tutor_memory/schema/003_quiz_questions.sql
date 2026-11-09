-- The questions a quiz was built with: [{"problem_id", "format", "seed"}], where format is
-- "answer" or "spot" for a choice question (seed is that question's own seed) and "written"
-- for a checked one. `prooflab-tutor memory quiz start` writes them from the quiz it rebuilds,
-- and an answer or attempt recorded against the quiz must match one of them. NULL for quizzes
-- started before this migration, which stay unbound.
ALTER TABLE quiz_results ADD COLUMN questions jsonb;
