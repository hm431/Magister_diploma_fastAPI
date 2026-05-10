-- Квантили распределения длительности проекта
CREATE TABLE risk.risk_quantile (
    run_id      INTEGER      NOT NULL,
    gamma_level NUMERIC(4,3) NOT NULL,
    t_gamma     NUMERIC(10,3) NOT NULL,
    PRIMARY KEY (run_id, gamma_level),
    CONSTRAINT fk_rq_run    FOREIGN KEY (run_id) REFERENCES risk.monte_carlo_run(run_id) ON DELETE CASCADE,
    CONSTRAINT chk_rq_gamma CHECK (gamma_level BETWEEN 0 AND 1)
);
COMMENT ON TABLE risk.risk_quantile IS 'Квантили T_γ из формулы 2.49';
