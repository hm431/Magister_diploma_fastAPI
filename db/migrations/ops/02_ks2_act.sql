-- Акты выполненных работ (КС-2)
CREATE TABLE ops.ks2_act (
    act_id                 SERIAL PRIMARY KEY,
    project_id             INTEGER       NOT NULL,
    act_number             VARCHAR(50)   NOT NULL,
    act_date               DATE          NOT NULL,
    total_amount           NUMERIC(15,2) NOT NULL,
    signed_status          VARCHAR(50)   NOT NULL DEFAULT 'draft',
    electronic_signature_id VARCHAR(255),
    CONSTRAINT fk_ks2_project FOREIGN KEY (project_id) REFERENCES sro.project(project_id) ON DELETE CASCADE,
    CONSTRAINT chk_ks2_status CHECK (signed_status IN ('draft', 'signed_contractor', 'signed_customer', 'rejected')),
    CONSTRAINT chk_ks2_amount CHECK (total_amount >= 0),
    CONSTRAINT uq_ks2_number  UNIQUE (project_id, act_number)
);
CREATE INDEX idx_ks2_project ON ops.ks2_act(project_id);
COMMENT ON TABLE ops.ks2_act IS 'Акты выполненных работ КС-2 (электронное подписание по СП 543.1325800.2024)';
