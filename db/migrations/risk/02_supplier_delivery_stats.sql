-- Статистика сроков поставок поставщиков
CREATE TABLE risk.supplier_delivery_stats (
    supplier_id   INTEGER       NOT NULL,
    material_id   INTEGER       NOT NULL,
    mu_log        NUMERIC(8,4)  NOT NULL,
    sigma_log     NUMERIC(8,4)  NOT NULL,
    sample_size   INTEGER       NOT NULL,
    last_updated  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (supplier_id, material_id),
    CONSTRAINT fk_sds_supplier FOREIGN KEY (supplier_id) REFERENCES ref.supplier(supplier_id),
    CONSTRAINT fk_sds_material FOREIGN KEY (material_id) REFERENCES ref.material(material_id),
    CONSTRAINT chk_sds_sigma   CHECK (sigma_log   >= 0),
    CONSTRAINT chk_sds_sample  CHECK (sample_size >= 0)
);
COMMENT ON TABLE risk.supplier_delivery_stats IS 'μ_{jk}, σ²_{jk} логнормального распределения (формулы 2.42-2.44)';
