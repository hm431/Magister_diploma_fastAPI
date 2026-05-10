-- Предшественники работ
CREATE TABLE sro.work_predecessor (
    work_id             INTEGER NOT NULL,
    predecessor_work_id INTEGER NOT NULL,
    PRIMARY KEY (work_id, predecessor_work_id),
    CONSTRAINT fk_wp_work        FOREIGN KEY (work_id)             REFERENCES sro.work(work_id) ON DELETE CASCADE,
    CONSTRAINT fk_wp_predecessor FOREIGN KEY (predecessor_work_id) REFERENCES sro.work(work_id),
    CONSTRAINT chk_wp_not_self   CHECK (work_id <> predecessor_work_id)
);
COMMENT ON TABLE sro.work_predecessor IS 'Технологические связи P_i - множество предшественников';
