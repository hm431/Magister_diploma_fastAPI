-- Журнал движения материалов
CREATE TABLE mtr.stock_movement (
    movement_id           SERIAL PRIMARY KEY,
    material_id           INTEGER       NOT NULL,
    warehouse_id          INTEGER       NOT NULL,
    movement_date         TIMESTAMP     NOT NULL,
    movement_type         VARCHAR(50)   NOT NULL,
    quantity              NUMERIC(12,3) NOT NULL,
    source_document_id    INTEGER,
    source_document_type  VARCHAR(50),
    CONSTRAINT fk_sm_material  FOREIGN KEY (material_id)  REFERENCES ref.material(material_id),
    CONSTRAINT fk_sm_warehouse FOREIGN KEY (warehouse_id) REFERENCES ref.warehouse(warehouse_id),
    CONSTRAINT chk_sm_type     CHECK (movement_type IN ('incoming', 'outgoing', 'transfer', 'writeoff')),
    CONSTRAINT chk_sm_quantity CHECK (quantity > 0)
);
CREATE INDEX idx_sm_material ON mtr.stock_movement(material_id);
CREATE INDEX idx_sm_date     ON mtr.stock_movement(movement_date);
COMMENT ON TABLE mtr.stock_movement IS 'Журнал движения материалов (приходы, расходы, перемещения)';
