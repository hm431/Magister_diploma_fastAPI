-- Корректирующие сценарии
CREATE TABLE risk.correction_scenario (
    scenario_id      SERIAL PRIMARY KEY,
    deviation_id     INTEGER      NOT NULL,
    generation_date  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description      TEXT,
    delta_t          NUMERIC(8,3),
    delta_c          NUMERIC(15,2),
    delta_r          NUMERIC(5,4),
    j_score          NUMERIC(10,4),
    is_recommended   BOOLEAN      NOT NULL DEFAULT FALSE,
    CONSTRAINT fk_cs_deviation FOREIGN KEY (deviation_id) REFERENCES ops.deviation(deviation_id) ON DELETE CASCADE
);
CREATE INDEX idx_cs_deviation ON risk.correction_scenario(deviation_id);
-- Поиск рекомендованных сценариев
CREATE INDEX idx_cs_recommended ON risk.correction_scenario(is_recommended) WHERE is_recommended = TRUE;
COMMENT ON TABLE risk.correction_scenario IS 'Сценарии корректировки σ (формулы 2.63-2.64)';
