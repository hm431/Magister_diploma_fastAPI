-- Договоры поставки
CREATE TABLE norm.supply_contract (
    contract_id           SERIAL PRIMARY KEY,
    supplier_id           INTEGER       NOT NULL,
    material_id           INTEGER       NOT NULL,
    price_per_unit        NUMERIC(12,2) NOT NULL,
    min_delivery_days     INTEGER       NOT NULL,
    max_volume_per_period NUMERIC(12,3),
    valid_from            DATE          NOT NULL,
    valid_to              DATE,
    CONSTRAINT fk_sc_supplier FOREIGN KEY (supplier_id) REFERENCES ref.supplier(supplier_id),
    CONSTRAINT fk_sc_material FOREIGN KEY (material_id) REFERENCES ref.material(material_id),
    CONSTRAINT chk_sc_price   CHECK (price_per_unit >= 0),
    CONSTRAINT chk_sc_days    CHECK (min_delivery_days >= 0),
    CONSTRAINT chk_sc_period  CHECK (valid_to IS NULL OR valid_to >= valid_from)
);
CREATE INDEX idx_sc_supplier ON norm.supply_contract(supplier_id);
CREATE INDEX idx_sc_material ON norm.supply_contract(material_id);
COMMENT ON TABLE norm.supply_contract IS 'Договоры поставки (содержит c_{jlt} и τ_{jl}^мин)';
COMMENT ON COLUMN norm.supply_contract.min_delivery_days IS 'τ_{jl}^мин - минимальный срок поставки (формула 2.16)';
