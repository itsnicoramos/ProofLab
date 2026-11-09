-- The repo tutor's memory (SPEC §20). Applied by `prooflab-tutor memory init` (and on first
-- use) into the schema named by PROOFLAB_TUTOR_DB_SCHEMA (default "tutor"). Never drops data.

CREATE TABLE learners (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        text NOT NULL UNIQUE CHECK (name ~ '^[a-z0-9][a-z0-9_-]{0,39}$'),
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- One active plan per learner. "Start over" archives it (archived_at) instead of deleting.
CREATE TABLE plans (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    learner_id     bigint NOT NULL REFERENCES learners (id) ON DELETE CASCADE,
    mission        text NOT NULL CHECK (length(mission) BETWEEN 1 AND 2000),
    goal           text CHECK (length(goal) <= 500),
    pace           text CHECK (length(pace) <= 200),
    exam_date      date,
    entry_chapter  smallint CHECK (entry_chapter BETWEEN 1 AND 14),
    placement      jsonb,
    chapters_at_archive jsonb,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    archived_at    timestamptz
);
CREATE UNIQUE INDEX plans_one_active ON plans (learner_id) WHERE archived_at IS NULL;

CREATE TABLE chapter_status (
    learner_id  bigint NOT NULL REFERENCES learners (id) ON DELETE CASCADE,
    chapter     smallint NOT NULL CHECK (chapter BETWEEN 1 AND 14),
    status      text NOT NULL CHECK (status IN ('skip', 'review', 'do', 'done')),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (learner_id, chapter)
);

CREATE TABLE sessions (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    learner_id  bigint NOT NULL REFERENCES learners (id) ON DELETE CASCADE,
    mode        text NOT NULL CHECK (mode IN ('start', 'level', 'learn', 'practice', 'quiz', 'guide')),
    chapter     smallint CHECK (chapter BETWEEN 1 AND 14),
    started_at  timestamptz NOT NULL DEFAULT now(),
    ended_at    timestamptz,
    summary     text CHECK (length(summary) <= 1000)
);
CREATE INDEX sessions_learner_started ON sessions (learner_id, started_at DESC);

-- A quiz, chapter check or mock test. Its score is computed from the recorded answers,
-- never sent by the agent.
CREATE TABLE quiz_results (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    learner_id   bigint NOT NULL REFERENCES learners (id) ON DELETE CASCADE,
    session_id   bigint REFERENCES sessions (id) ON DELETE SET NULL,
    kind         text NOT NULL CHECK (kind IN ('placement', 'chapter', 'quiz', 'midterm', 'final')),
    chapters     smallint[] NOT NULL DEFAULT '{}',
    seed         bigint NOT NULL,
    total        smallint NOT NULL CHECK (total BETWEEN 1 AND 60),
    score        smallint,
    started_at   timestamptz NOT NULL DEFAULT now(),
    finished_at  timestamptz
);

-- Only `prooflab-tutor check --record` writes here: each row is the checker's own verdict.
CREATE TABLE attempts (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    learner_id   bigint NOT NULL REFERENCES learners (id) ON DELETE CASCADE,
    session_id   bigint REFERENCES sessions (id) ON DELETE SET NULL,
    quiz_id      bigint REFERENCES quiz_results (id) ON DELETE SET NULL,
    problem_id   text NOT NULL CHECK (length(problem_id) <= 120),
    chapter      smallint CHECK (chapter BETWEEN 1 AND 14),
    status       text NOT NULL CHECK (status IN ('correct', 'partial', 'incorrect', 'invalid')),
    score        real NOT NULL,
    hint_codes   text[] NOT NULL DEFAULT '{}',
    hints_shown  smallint NOT NULL DEFAULT 0,
    first_try    boolean NOT NULL,
    steps        jsonb NOT NULL,
    checked_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX attempts_learner_problem ON attempts (learner_id, problem_id, checked_at);

-- Only `prooflab-tutor answer --record` writes here. The first answer to a question counts.
CREATE TABLE quiz_answers (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    quiz_id      bigint NOT NULL REFERENCES quiz_results (id) ON DELETE CASCADE,
    problem_id   text NOT NULL CHECK (length(problem_id) <= 120),
    seed         bigint NOT NULL,
    format       text CHECK (format IN ('answer', 'spot')),
    choice       text NOT NULL CHECK (choice ~ '^[a-e]$'),
    correct      boolean NOT NULL,
    answered_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (quiz_id, problem_id, seed)
);

CREATE TABLE review_queue (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    learner_id   bigint NOT NULL REFERENCES learners (id) ON DELETE CASCADE,
    chapter      smallint NOT NULL CHECK (chapter BETWEEN 1 AND 14),
    idea         text NOT NULL CHECK (length(idea) BETWEEN 1 AND 500),
    problem_ids  text[] NOT NULL DEFAULT '{}',
    added_at     timestamptz NOT NULL DEFAULT now(),
    cleared_at   timestamptz
);

-- What the tutor remembers about how this learner learns.
CREATE TABLE notes (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    learner_id  bigint NOT NULL REFERENCES learners (id) ON DELETE CASCADE,
    kind        text NOT NULL CHECK (kind IN ('struggle', 'misconception', 'preference', 'goal')),
    text        text NOT NULL CHECK (length(text) BETWEEN 1 AND 500),
    chapter     smallint CHECK (chapter BETWEEN 1 AND 14),
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE card_reviews (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    learner_id   bigint NOT NULL REFERENCES learners (id) ON DELETE CASCADE,
    card_id      text NOT NULL CHECK (length(card_id) <= 120),
    recalled     boolean NOT NULL,
    reviewed_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX card_reviews_learner_card ON card_reviews (learner_id, card_id, reviewed_at DESC);
