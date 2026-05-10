-- Справки о стоимости КС-3
CREATE TABLE ops.ks3_certificate (
    certificate_id SERIAL PRIMARY KEY,
    project_id     INTEGER       NOT NULL,
    period_start   DATE          NOT NULL,
    period_end     DATE          NOT NULL,
    total_amount   NUMERIC(15,2) NOT NULL,
    CONSTRAINT fk_ks3_project FOREIGN KEY (project_id) REFERENCES sro.project(project_id) ON DELETE CASCADE,
    CONSTRAINT chk_ks3_period CHECK (period_end >= period_start),
    CONSTRAINT chk_ks3_amount CHECK (total_amount >= 0)
);
COMMENT ON TABLE ops.ks3_certificate IS 'Справки о стоимости выполненных работ КС-3';
