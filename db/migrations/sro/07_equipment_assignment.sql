-- Закрепление техники за участками
CREATE TABLE sro.equipment_assignment (
    equipment_id INTEGER NOT NULL,
    site_id      INTEGER NOT NULL,
    period_start DATE    NOT NULL,
    period_end   DATE    NOT NULL,
    PRIMARY KEY (equipment_id, site_id, period_start),
    CONSTRAINT fk_ea_equipment FOREIGN KEY (equipment_id) REFERENCES ref.equipment(equipment_id),
    CONSTRAINT fk_ea_site      FOREIGN KEY (site_id)      REFERENCES ref.site(site_id),
    CONSTRAINT chk_ea_period   CHECK (period_end >= period_start)
);
COMMENT ON TABLE sro.equipment_assignment IS 'Закрепление техники за строительными участками';
