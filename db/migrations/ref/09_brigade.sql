-- Бригады
CREATE TABLE ref.brigade (
    brigade_id    SERIAL PRIMARY KEY,
    name          VARCHAR(255) NOT NULL,
    headcount     INTEGER      NOT NULL,
    base_location VARCHAR(255),
    CONSTRAINT chk_headcount CHECK (headcount > 0)
);
COMMENT ON TABLE ref.brigade IS 'Производственные бригады';
