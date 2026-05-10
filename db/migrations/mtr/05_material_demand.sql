-- Плановая потребность в материалах (Q_{jt})
CREATE TABLE mtr.material_demand (
    project_id              INTEGER       NOT NULL,
    material_id             INTEGER       NOT NULL,
    demand_date             DATE          NOT NULL,
    quantity                NUMERIC(12,3) NOT NULL,
    schedule_calculation_id INTEGER       NOT NULL,
    PRIMARY KEY (project_id, material_id, demand_date, schedule_calculation_id),
    CONSTRAINT fk_md_project  FOREIGN KEY (project_id)              REFERENCES sro.project(project_id) ON DELETE CASCADE,
    CONSTRAINT fk_md_material FOREIGN KEY (material_id)             REFERENCES ref.material(material_id),
    CONSTRAINT fk_md_calc     FOREIGN KEY (schedule_calculation_id) REFERENCES sro.schedule_calculation(calculation_id) ON DELETE CASCADE,
    CONSTRAINT chk_md_qty     CHECK (quantity >= 0)
);
COMMENT ON TABLE mtr.material_demand IS 'Плановая потребность Q_{jt} (формула 2.9)';
