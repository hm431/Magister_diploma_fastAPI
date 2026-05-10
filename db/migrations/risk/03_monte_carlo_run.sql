-- Запуски имитации Монте-Карло
CREATE TABLE risk.monte_carlo_run (
    run_id            SERIAL PRIMARY KEY,
    project_id        INTEGER      NOT NULL,
    run_date          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    iterations_count  INTEGER      NOT NULL,
    seed              BIGINT,
    mean_duration     NUMERIC(10,3),
    std_duration      NUMERIC(10,3),
    prob_on_time      NUMERIC(5,4),
    CONSTRAINT fk_mcr_project   FOREIGN KEY (project_id) REFERENCES sro.project(project_id) ON DELETE CASCADE,
    CONSTRAINT chk_mcr_iter     CHECK (iterations_count > 0),
    CONSTRAINT chk_mcr_prob     CHECK (prob_on_time IS NULL OR prob_on_time BETWEEN 0 AND 1)
);
CREATE INDEX idx_mcr_project ON risk.monte_carlo_run(project_id);
COMMENT ON TABLE risk.monte_carlo_run IS 'Запуски Монте-Карло: E[T] (2.47), σ[T] (2.48), P(T≤T_план) (2.46)';
