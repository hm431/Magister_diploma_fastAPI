-- Управляющие воздействия в составе сценариев
CREATE TABLE risk.scenario_action (
    scenario_id INTEGER     NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    target_id   INTEGER,
    parameters  JSONB,
    PRIMARY KEY (scenario_id, action_type, COALESCE(target_id, 0)),
    CONSTRAINT fk_sa_scenario FOREIGN KEY (scenario_id) REFERENCES risk.correction_scenario(scenario_id) ON DELETE CASCADE,
    CONSTRAINT chk_sa_type CHECK (action_type IN ('expedite_delivery', 'reassign_brigade', 'parallelize_works', 'add_resources', 'other'))
);
COMMENT ON TABLE risk.scenario_action IS 'Управляющие воздействия в составе корректирующего сценария';
