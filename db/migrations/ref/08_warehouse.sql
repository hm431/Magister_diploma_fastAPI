-- Склады
CREATE TABLE ref.warehouse (
    warehouse_id        SERIAL PRIMARY KEY,
    name                VARCHAR(255) NOT NULL,
    address             VARCHAR(500),
    capacity            NUMERIC(12,2),
    loading_posts       INTEGER      NOT NULL DEFAULT 1,
    service_rate        NUMERIC(8,4),
    allowed_wait_time   INTEGER,
    CONSTRAINT chk_capacity     CHECK (capacity IS NULL OR capacity > 0),
    CONSTRAINT chk_loading_pos  CHECK (loading_posts > 0),
    CONSTRAINT chk_service_rate CHECK (service_rate IS NULL OR service_rate > 0)
);
COMMENT ON TABLE ref.warehouse IS 'Склады отгрузки и приёмки';
COMMENT ON COLUMN ref.warehouse.capacity          IS 'U_max - вместимость склада (формула 2.23)';
COMMENT ON COLUMN ref.warehouse.loading_posts     IS 'n_р - количество разгрузочных постов (формула 2.26)';
COMMENT ON COLUMN ref.warehouse.service_rate      IS 'μ - интенсивность обслуживания (формула 2.26)';
COMMENT ON COLUMN ref.warehouse.allowed_wait_time IS 'W_q^доп - допустимое время ожидания, мин (формула 2.30)';
