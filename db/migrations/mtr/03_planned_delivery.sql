-- Плановые поставки (x_{jlt})
CREATE TABLE mtr.planned_delivery (
    planned_delivery_id SERIAL PRIMARY KEY,
    project_id          INTEGER       NOT NULL,
    material_id         INTEGER       NOT NULL,
    warehouse_id        INTEGER       NOT NULL,
    supplier_id         INTEGER       NOT NULL,
    planned_date        DATE          NOT NULL,
    planned_volume      NUMERIC(12,3) NOT NULL,
    unit_cost           NUMERIC(12,2) NOT NULL,
    status              VARCHAR(50)   NOT NULL DEFAULT 'planned',
    CONSTRAINT fk_pd_project   FOREIGN KEY (project_id)   REFERENCES sro.project(project_id) ON DELETE CASCADE,
    CONSTRAINT fk_pd_material  FOREIGN KEY (material_id)  REFERENCES ref.material(material_id),
    CONSTRAINT fk_pd_warehouse FOREIGN KEY (warehouse_id) REFERENCES ref.warehouse(warehouse_id),
    CONSTRAINT fk_pd_supplier  FOREIGN KEY (supplier_id)  REFERENCES ref.supplier(supplier_id),
    CONSTRAINT chk_pd_volume   CHECK (planned_volume > 0),
    CONSTRAINT chk_pd_cost     CHECK (unit_cost >= 0),
    CONSTRAINT chk_pd_status   CHECK (status IN ('planned', 'confirmed', 'shipped', 'delivered', 'cancelled'))
);
CREATE INDEX idx_pd_project  ON mtr.planned_delivery(project_id);
CREATE INDEX idx_pd_material ON mtr.planned_delivery(material_id);
CREATE INDEX idx_pd_date     ON mtr.planned_delivery(planned_date);
COMMENT ON TABLE mtr.planned_delivery IS 'Плановые поставки (x_{jlt} из формулы 2.12)';
