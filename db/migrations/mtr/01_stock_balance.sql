-- Остатки на складах (S_{jt}, V_{jt})
CREATE TABLE mtr.stock_balance (
    stock_id          SERIAL PRIMARY KEY,
    material_id       INTEGER       NOT NULL,
    warehouse_id      INTEGER       NOT NULL,
    balance_date      DATE          NOT NULL,
    quantity          NUMERIC(12,3) NOT NULL,
    reserved_quantity NUMERIC(12,3) NOT NULL DEFAULT 0,
    CONSTRAINT fk_sb_material  FOREIGN KEY (material_id)  REFERENCES ref.material(material_id),
    CONSTRAINT fk_sb_warehouse FOREIGN KEY (warehouse_id) REFERENCES ref.warehouse(warehouse_id),
    CONSTRAINT chk_sb_quantity CHECK (quantity >= 0 AND reserved_quantity >= 0),
    CONSTRAINT uq_sb_position  UNIQUE (material_id, warehouse_id, balance_date)
);
CREATE INDEX idx_sb_material  ON mtr.stock_balance(material_id);
CREATE INDEX idx_sb_warehouse ON mtr.stock_balance(warehouse_id);
CREATE INDEX idx_sb_date      ON mtr.stock_balance(balance_date);
COMMENT ON TABLE mtr.stock_balance IS 'Остатки материалов на складах (S_{jt}, V_{jt} из формул 2.10, 2.21)';
