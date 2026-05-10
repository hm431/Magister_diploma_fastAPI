-- Типы работ
CREATE TABLE ref.work_type (
    work_type_id           SERIAL PRIMARY KEY,
    name                   VARCHAR(255) NOT NULL,
    unit                   VARCHAR(20)  NOT NULL,
    normative_productivity NUMERIC(10,3),
    technological_group    VARCHAR(100)
);
COMMENT ON TABLE ref.work_type IS 'Справочник типовых СМР';
