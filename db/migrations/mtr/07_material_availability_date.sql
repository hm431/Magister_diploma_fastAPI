-- Даты гарантированной доступности материалов (T_доступ(j))
CREATE TABLE mtr.material_availability_date (
    project_id        INTEGER NOT NULL,
    material_id       INTEGER NOT NULL,
    availability_date DATE    NOT NULL,
    calculation_id    INTEGER NOT NULL,
    PRIMARY KEY (project_id, material_id, calculation_id),
    CONSTRAINT fk_mad_project  FOREIGN KEY (project_id)     REFERENCES sro.project(project_id) ON DELETE CASCADE,
    CONSTRAINT fk_mad_material FOREIGN KEY (material_id)    REFERENCES ref.material(material_id),
    CONSTRAINT fk_mad_calc     FOREIGN KEY (calculation_id) REFERENCES sro.schedule_calculation(calculation_id) ON DELETE CASCADE
);
COMMENT ON TABLE mtr.material_availability_date IS 'T_доступ(j) - даты гарантированной доступности (формула 2.18)';
