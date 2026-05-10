-- Квалификации
CREATE TABLE ref.qualification (
    qualification_id SERIAL PRIMARY KEY,
    name             VARCHAR(255) NOT NULL,
    level            INTEGER,
    CONSTRAINT chk_qual_level CHECK (level IS NULL OR level BETWEEN 1 AND 10)
);
COMMENT ON TABLE ref.qualification IS 'Квалификационные требования и разряды';
