-- Журнал фактического выполнения работ (КС-6)
CREATE TABLE ops.work_execution (
    execution_id        SERIAL PRIMARY KEY,
    work_id             INTEGER       NOT NULL,
    execution_date      DATE          NOT NULL,
    fact_volume         NUMERIC(12,3) NOT NULL,
    fact_percent        NUMERIC(5,4)  NOT NULL,
    responsible_user_id INTEGER       NOT NULL,
    comments            TEXT,
    CONSTRAINT fk_we_work CHECK (fact_percent BETWEEN 0 AND 1),
    CONSTRAINT fk_we_work_fk  FOREIGN KEY (work_id)             REFERENCES sro.work(work_id) ON DELETE CASCADE,
    CONSTRAINT fk_we_user     FOREIGN KEY (responsible_user_id) REFERENCES ref.app_user(user_id),
    CONSTRAINT chk_we_volume  CHECK (fact_volume >= 0)
);
CREATE INDEX idx_we_work ON ops.work_execution(work_id);
CREATE INDEX idx_we_date ON ops.work_execution(execution_date);
COMMENT ON TABLE ops.work_execution IS 'Журнал КС-6 (общий журнал работ), p_i^факт (формула 2.51)';
