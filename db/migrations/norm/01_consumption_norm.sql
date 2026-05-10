-- Нормы расхода материалов (r_{ij} из формулы 2.9)
CREATE TABLE norm.consumption_norm (
    work_type_id    INTEGER     NOT NULL,
    material_id     INTEGER     NOT NULL,
    norm_value      NUMERIC(12,6) NOT NULL,
    effective_from  DATE        NOT NULL DEFAULT CURRENT_DATE,
    PRIMARY KEY (work_type_id, material_id, effective_from),
    CONSTRAINT fk_norm_work_type FOREIGN KEY (work_type_id) REFERENCES ref.work_type(work_type_id),
    CONSTRAINT fk_norm_material  FOREIGN KEY (material_id)  REFERENCES ref.material(material_id),
    CONSTRAINT chk_norm_value CHECK (norm_value >= 0)
);
COMMENT ON TABLE norm.consumption_norm IS 'Нормы расхода r_{ij} - связь работ и материалов';
