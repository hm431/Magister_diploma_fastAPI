-- Строительные участки
CREATE TABLE ref.site (
    site_id        SERIAL PRIMARY KEY,
    object_id      INTEGER NOT NULL,
    name           VARCHAR(255) NOT NULL,
    coordinates    POINT,
    planned_volume NUMERIC(12,3),
    CONSTRAINT fk_site_object FOREIGN KEY (object_id) REFERENCES ref.object(object_id) ON DELETE CASCADE
);
CREATE INDEX idx_site_object ON ref.site(object_id);
COMMENT ON TABLE ref.site IS 'Строительные участки в составе объектов';
