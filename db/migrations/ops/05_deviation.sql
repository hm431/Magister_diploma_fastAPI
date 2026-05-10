-- Отклонения по работам
CREATE TABLE ops.deviation (
    deviation_id    SERIAL PRIMARY KEY,
    work_id         INTEGER      NOT NULL,
    detection_date  DATE         NOT NULL,
    plan_percent    NUMERIC(5,4) NOT NULL,
    fact_percent    NUMERIC(5,4) NOT NULL,
    delta_percent   NUMERIC(5,4) NOT NULL,
    chi_mtr         BOOLEAN      NOT NULL DEFAULT FALSE,
    category        VARCHAR(50)  NOT NULL,
    CONSTRAINT fk_dev_work CHECK (
        plan_percent  BETWEEN 0 AND 1 AND
        fact_percent  BETWEEN 0 AND 1 AND
        delta_percent BETWEEN -1 AND 1),
    CONSTRAINT fk_dev_work_fk FOREIGN KEY (work_id) REFERENCES sro.work(work_id) ON DELETE CASCADE,
    CONSTRAINT chk_dev_cat    CHECK (category IN ('MTR', 'weather', 'technological', 'personnel', 'other'))
);
CREATE INDEX idx_dev_work     ON ops.deviation(work_id);
CREATE INDEX idx_dev_date     ON ops.deviation(detection_date);
CREATE INDEX idx_dev_category ON ops.deviation(category);
-- Поиск отклонений по проекту через work
CREATE INDEX idx_deviation_chi_mtr ON ops.deviation(chi_mtr) WHERE chi_mtr = TRUE;
COMMENT ON TABLE ops.deviation IS 'Отклонения Δp_i (формула 2.51), χ_i^МТР (формула 2.53)';
