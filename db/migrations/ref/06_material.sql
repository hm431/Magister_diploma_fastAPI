-- Материалы
CREATE TABLE ref.material (
    material_id            SERIAL PRIMARY KEY,
    name                   VARCHAR(255) NOT NULL,
    unit                   VARCHAR(20)  NOT NULL,
    storage_coefficient    NUMERIC(8,4),
    category               VARCHAR(100),
    requires_certification BOOLEAN      NOT NULL DEFAULT FALSE,
    CONSTRAINT chk_storage_coef CHECK (storage_coefficient IS NULL OR storage_coefficient >= 0)
);
COMMENT ON TABLE ref.material IS 'Номенклатурный справочник материалов';
COMMENT ON COLUMN ref.material.storage_coefficient IS 'Коэффициент w_j (формула 2.22) - удельная площадь/объём хранения';
