-- Профиль загрузки склада (U_t)
CREATE TABLE mtr.warehouse_load_profile (
    warehouse_id    INTEGER       NOT NULL,
    profile_date    DATE          NOT NULL,
    total_load      NUMERIC(12,2) NOT NULL,
    peak_indicator  BOOLEAN       NOT NULL DEFAULT FALSE,
    queue_length    NUMERIC(8,3),
    wait_time       NUMERIC(8,3),
    PRIMARY KEY (warehouse_id, profile_date),
    CONSTRAINT fk_wlp_warehouse FOREIGN KEY (warehouse_id) REFERENCES ref.warehouse(warehouse_id),
    CONSTRAINT chk_wlp_load     CHECK (total_load >= 0)
);
CREATE INDEX idx_wlp_date ON mtr.warehouse_load_profile(profile_date);
COMMENT ON TABLE mtr.warehouse_load_profile IS 'Загрузка склада U_t (формула 2.22), L_q (2.28), W_q (2.29)';
