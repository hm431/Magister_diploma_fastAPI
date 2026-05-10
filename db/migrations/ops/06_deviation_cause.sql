-- Причины отклонений категории МТР
CREATE TABLE ops.deviation_cause (
    deviation_id    INTEGER NOT NULL,
    material_id     INTEGER NOT NULL,
    supplier_id     INTEGER NOT NULL,
    deficit_days    INTEGER NOT NULL,
    deficit_volume  NUMERIC(12,3) NOT NULL,
    PRIMARY KEY (deviation_id, material_id, supplier_id),
    CONSTRAINT fk_dc_deviation FOREIGN KEY (deviation_id) REFERENCES ops.deviation(deviation_id) ON DELETE CASCADE,
    CONSTRAINT fk_dc_material  FOREIGN KEY (material_id)  REFERENCES ref.material(material_id),
    CONSTRAINT fk_dc_supplier  FOREIGN KEY (supplier_id)  REFERENCES ref.supplier(supplier_id),
    CONSTRAINT chk_dc_days     CHECK (deficit_days   >= 0),
    CONSTRAINT chk_dc_volume   CHECK (deficit_volume >= 0)
);
COMMENT ON TABLE ops.deviation_cause IS 'Первопричины отклонений категории МТР с привязкой к поставщикам';
