-- Техника и оборудование
CREATE TABLE ref.equipment (
    equipment_id        SERIAL PRIMARY KEY,
    type                VARCHAR(100) NOT NULL,
    model               VARCHAR(255),
    base_warehouse_id   INTEGER,
    availability_status VARCHAR(50)  NOT NULL DEFAULT 'available',
    CONSTRAINT fk_equipment_warehouse FOREIGN KEY (base_warehouse_id) REFERENCES ref.warehouse(warehouse_id),
    CONSTRAINT chk_avail_status CHECK (availability_status IN ('available', 'in_use', 'maintenance', 'broken'))
);
CREATE INDEX idx_equipment_warehouse ON ref.equipment(base_warehouse_id);
COMMENT ON TABLE ref.equipment IS 'Парк техники и оборудования';
