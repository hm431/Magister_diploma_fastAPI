-- Индексы критичности работ
CREATE TABLE risk.work_criticality_index (
    run_id             INTEGER      NOT NULL,
    work_id            INTEGER      NOT NULL,
    criticality_index  NUMERIC(5,4) NOT NULL,
    risk_critical      BOOLEAN      NOT NULL DEFAULT FALSE,
    PRIMARY KEY (run_id, work_id),
    CONSTRAINT fk_wci_run  FOREIGN KEY (run_id)  REFERENCES risk.monte_carlo_run(run_id) ON DELETE CASCADE,
    CONSTRAINT fk_wci_work FOREIGN KEY (work_id) REFERENCES sro.work(work_id),
    CONSTRAINT chk_wci_idx CHECK (criticality_index BETWEEN 0 AND 1)
);
-- Поиск рисковых работ
CREATE INDEX idx_wci_risk_critical ON risk.work_criticality_index(risk_critical) WHERE risk_critical = TRUE;
COMMENT ON TABLE risk.work_criticality_index IS 'Индекс критичности CI_i (формула 2.50)';
