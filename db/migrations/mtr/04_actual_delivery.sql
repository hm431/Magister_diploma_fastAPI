-- Фактические поставки
CREATE TABLE mtr.actual_delivery (
    actual_delivery_id   SERIAL PRIMARY KEY,
    planned_delivery_id  INTEGER,
    material_id          INTEGER       NOT NULL,
    warehouse_id         INTEGER       NOT NULL,
    supplier_id          INTEGER       NOT NULL,
    actual_date          DATE          NOT NULL,
    actual_volume        NUMERIC(12,3) NOT NULL,
    deviation_days       INTEGER,
    CONSTRAINT fk_ad_planned   FOREIGN KEY (planned_delivery_id) REFERENCES mtr.planned_delivery(planned_delivery_id),
    CONSTRAINT fk_ad_material  FOREIGN KEY (material_id)         REFERENCES ref.material(material_id),
    CONSTRAINT fk_ad_warehouse FOREIGN KEY (warehouse_id)        REFERENCES ref.warehouse(warehouse_id),
    CONSTRAINT fk_ad_supplier  FOREIGN KEY (supplier_id)         REFERENCES ref.supplier(supplier_id),
    CONSTRAINT chk_ad_volume   CHECK (actual_volume > 0)
);
CREATE INDEX idx_ad_planned  ON mtr.actual_delivery(planned_delivery_id);
CREATE INDEX idx_ad_material ON mtr.actual_delivery(material_id);
CREATE INDEX idx_ad_date     ON mtr.actual_delivery(actual_date);
COMMENT ON TABLE mtr.actual_delivery IS 'Фактические поставки (синхронизация через ETL из 1С)';
