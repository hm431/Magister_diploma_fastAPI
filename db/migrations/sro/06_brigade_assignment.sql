-- Назначения бригад на участки
CREATE TABLE sro.brigade_assignment (
    assignment_id           SERIAL PRIMARY KEY,
    brigade_id              INTEGER NOT NULL,
    site_id                 INTEGER NOT NULL,
    period_start            DATE    NOT NULL,
    period_end              DATE    NOT NULL,
    assignment_cost         NUMERIC(12,4),
    schedule_calculation_id INTEGER NOT NULL,
    CONSTRAINT fk_ba_brigade  FOREIGN KEY (brigade_id)              REFERENCES ref.brigade(brigade_id),
    CONSTRAINT fk_ba_site     FOREIGN KEY (site_id)                 REFERENCES ref.site(site_id),
    CONSTRAINT fk_ba_calc     FOREIGN KEY (schedule_calculation_id) REFERENCES sro.schedule_calculation(calculation_id) ON DELETE CASCADE,
    CONSTRAINT chk_ba_period  CHECK (period_end >= period_start)
);
CREATE INDEX idx_ba_brigade ON sro.brigade_assignment(brigade_id);
CREATE INDEX idx_ba_site    ON sro.brigade_assignment(site_id);
CREATE INDEX idx_ba_calc    ON sro.brigade_assignment(schedule_calculation_id);
COMMENT ON TABLE sro.brigade_assignment IS 'Назначения бригад (y_{ks} из формулы 2.31), c_{ks} = assignment_cost';
