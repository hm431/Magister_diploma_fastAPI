-- Проекты
CREATE TABLE sro.project (
    project_id    SERIAL PRIMARY KEY,
    object_id     INTEGER     NOT NULL,
    status        VARCHAR(50) NOT NULL DEFAULT 'planned',
    plan_start    DATE        NOT NULL,
    plan_finish   DATE        NOT NULL,
    actual_start  DATE,
    actual_finish DATE,
    CONSTRAINT fk_project_object FOREIGN KEY (object_id) REFERENCES ref.object(object_id),
    CONSTRAINT chk_project_status CHECK (status IN ('planned', 'in_progress', 'completed', 'suspended', 'cancelled')),
    CONSTRAINT chk_project_dates  CHECK (plan_finish >= plan_start)
);
CREATE INDEX idx_project_object ON sro.project(object_id);
CREATE INDEX idx_project_status ON sro.project(status);
COMMENT ON TABLE sro.project IS 'Проекты строительства (T_план - plan_finish)';
