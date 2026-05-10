-- Итерации Монте-Карло
CREATE TABLE risk.monte_carlo_iteration (
    run_id          INTEGER NOT NULL,
    iteration_number INTEGER NOT NULL,
    t_r             NUMERIC(10,3) NOT NULL,
    c_r             NUMERIC(15,2),
    PRIMARY KEY (run_id, iteration_number),
    CONSTRAINT fk_mci_run FOREIGN KEY (run_id) REFERENCES risk.monte_carlo_run(run_id) ON DELETE CASCADE
);
COMMENT ON TABLE risk.monte_carlo_iteration IS 'Результаты отдельных итераций T^{(r)} (2.45), C^{(r)}';
