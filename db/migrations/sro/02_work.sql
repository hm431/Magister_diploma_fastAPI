-- Работы
CREATE TABLE sro.work (
    work_id                  SERIAL PRIMARY KEY,
    project_id               INTEGER NOT NULL,
    site_id                  INTEGER NOT NULL,
    work_type_id             INTEGER NOT NULL,
    duration                 INTEGER NOT NULL,
    volume                   NUMERIC(12,3) NOT NULL,
    required_qualification_id INTEGER,
    required_equipment_type  VARCHAR(100),
    CONSTRAINT fk_work_project   FOREIGN KEY (project_id)                REFERENCES sro.project(project_id) ON DELETE CASCADE,
    CONSTRAINT fk_work_site      FOREIGN KEY (site_id)                   REFERENCES ref.site(site_id),
    CONSTRAINT fk_work_type      FOREIGN KEY (work_type_id)              REFERENCES ref.work_type(work_type_id),
    CONSTRAINT fk_work_qual      FOREIGN KEY (required_qualification_id) REFERENCES ref.qualification(qualification_id),
    CONSTRAINT chk_work_duration CHECK (duration > 0),
    CONSTRAINT chk_work_volume   CHECK (volume   > 0)
);
CREATE INDEX idx_work_project ON sro.work(project_id);
CREATE INDEX idx_work_site    ON sro.work(site_id);
COMMENT ON TABLE sro.work IS 'Работы проекта (множество I, d_i = duration, v_i = volume)';
