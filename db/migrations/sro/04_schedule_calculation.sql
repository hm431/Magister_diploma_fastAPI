-- Расчёты календарного графика
CREATE TABLE sro.schedule_calculation (
    calculation_id   SERIAL PRIMARY KEY,
    project_id       INTEGER     NOT NULL,
    calculation_date TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    version          INTEGER     NOT NULL DEFAULT 1,
    t_min            INTEGER,
    scenario         VARCHAR(50) NOT NULL DEFAULT 'plan',
    CONSTRAINT fk_sc_project   FOREIGN KEY (project_id) REFERENCES sro.project(project_id) ON DELETE CASCADE,
    CONSTRAINT chk_sc_scenario CHECK (scenario IN ('plan', 'actual', 'counterfactual', 'correction'))
);
CREATE INDEX idx_sched_calc_project ON sro.schedule_calculation(project_id);
COMMENT ON TABLE sro.schedule_calculation IS 'Версии расчёта календарного графика';
COMMENT ON COLUMN sro.schedule_calculation.t_min IS 'T_min - минимальная продолжительность проекта (формула 2.7)';
