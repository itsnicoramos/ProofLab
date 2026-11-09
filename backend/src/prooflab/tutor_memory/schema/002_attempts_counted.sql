-- An attempt the checker couldn't read (status "invalid", or its first error is an input-format
-- code like PARSE_ERROR or NOT_AN_EXPRESSION) is kept for the record but doesn't count: it
-- isn't a try at the math, so it never takes away "first try" or shows up in the stats.
ALTER TABLE attempts ADD COLUMN counted boolean NOT NULL DEFAULT true;
