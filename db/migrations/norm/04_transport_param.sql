-- Параметры транспортной доставки
CREATE TABLE norm.transport_param (
    material_id        INTEGER       NOT NULL,
    warehouse_id       INTEGER       NOT NULL,
    avg_capacity       NUMERIC(10,3) NOT NULL,
    avg_delivery_time  INTEGER       NOT NULL,
    PRIMARY KEY (material_id, warehouse_id),
    CONSTRAINT fk_tp_material  FOREIGN KEY (material_id)  REFERENCES ref.material(material_id),
    CONSTRAINT fk_tp_warehouse FOREIGN KEY (warehouse_id) REFERENCES ref.warehouse(warehouse_id),
    CONSTRAINT chk_tp_capacity CHECK (avg_capacity > 0),
    CONSTRAINT chk_tp_time     CHECK (avg_delivery_time > 0)
);
COMMENT ON TABLE norm.transport_param IS 'Параметры транспортной доставки (q_{jl} - грузоподъёмность, формула 2.25)';
