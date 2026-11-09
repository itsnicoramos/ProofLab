-- One memory per learner per course pack (SPEC §22). A row in `learners` is now a learner in
-- one course, and every other table hangs off it as before, so each course has its own plan,
-- chapters, sessions, attempts, quizzes, review queue, notes and card reviews. Everything
-- stored before this migration belongs to MATH 123, the only course there was.
ALTER TABLE learners
    ADD COLUMN course text NOT NULL DEFAULT 'math123'
        CHECK (course ~ '^[a-z][a-z0-9]{1,23}$');
ALTER TABLE learners DROP CONSTRAINT learners_name_key;
ALTER TABLE learners ADD CONSTRAINT learners_name_course_key UNIQUE (name, course);

-- Courses differ in length, so the CLI checks a chapter number against the course pack. The
-- database only keeps the number sane.
ALTER TABLE plans
    DROP CONSTRAINT plans_entry_chapter_check,
    ADD CONSTRAINT plans_entry_chapter_check CHECK (entry_chapter BETWEEN 1 AND 99);
ALTER TABLE chapter_status
    DROP CONSTRAINT chapter_status_chapter_check,
    ADD CONSTRAINT chapter_status_chapter_check CHECK (chapter BETWEEN 1 AND 99);
ALTER TABLE sessions
    DROP CONSTRAINT sessions_chapter_check,
    ADD CONSTRAINT sessions_chapter_check CHECK (chapter BETWEEN 1 AND 99);
ALTER TABLE attempts
    DROP CONSTRAINT attempts_chapter_check,
    ADD CONSTRAINT attempts_chapter_check CHECK (chapter BETWEEN 1 AND 99);
ALTER TABLE review_queue
    DROP CONSTRAINT review_queue_chapter_check,
    ADD CONSTRAINT review_queue_chapter_check CHECK (chapter BETWEEN 1 AND 99);
ALTER TABLE notes
    DROP CONSTRAINT notes_chapter_check,
    ADD CONSTRAINT notes_chapter_check CHECK (chapter BETWEEN 1 AND 99);

-- A course with no outline yet has no chapter to file a missed idea under.
ALTER TABLE review_queue ALTER COLUMN chapter DROP NOT NULL;

-- "coach" sessions: feedback on the learner's own course material, where ProofLab has no
-- checker (an empty course slot, or a chapter without checked exercises).
ALTER TABLE sessions
    DROP CONSTRAINT sessions_mode_check,
    ADD CONSTRAINT sessions_mode_check
        CHECK (mode IN ('start', 'level', 'learn', 'practice', 'quiz', 'guide', 'coach'));
