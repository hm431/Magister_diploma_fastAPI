-- Параметры бета-распределения длительностей работ
CREATE TABLE risk.work_risk_params (
    work_id           INTEGER PRIMARY KEY,
    optimistic        NUMERIC(8,3) NOT NULL,
    most_likely       NUMERIC(8,3) NOT NULL,
    pessimistic       NUMERIC(8,3) NOT NULL,
    alpha             NUMERIC(8,4),
    beta              NUMERIC(8,4),
    expected_duration NUMERIC(8,3),
    std_deviation     NUMERIC(8,3),
    CONSTRAINT fk_wrp_work FOREIGN KEY (work_id) REFERENCES sro.work(work_id) ON DELETE CASCADE,
    CONSTRAINT chk_wrp_order CHECK (optimistic <= most_likely AND most_likely <= pessimistic)
);
COMMENT ON TABLE risk.work_risk_params IS 'Параметры бета-распределения d_i (a_i, m_i, b_i из формулы 2.39)';
