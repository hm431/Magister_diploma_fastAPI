-- Позиции акта КС-2
CREATE TABLE ops.ks2_item (
    act_id          INTEGER       NOT NULL,
    work_id         INTEGER       NOT NULL,
    accepted_volume NUMERIC(12,3) NOT NULL,
    unit_price      NUMERIC(12,2) NOT NULL,
    total           NUMERIC(15,2) NOT NULL,
    PRIMARY KEY (act_id, work_id),
    CONSTRAINT fk_ks2i_act    FOREIGN KEY (act_id)  REFERENCES ops.ks2_act(act_id) ON DELETE CASCADE,
    CONSTRAINT fk_ks2i_work   FOREIGN KEY (work_id) REFERENCES sro.work(work_id),
    CONSTRAINT chk_ks2i_volume CHECK (accepted_volume >= 0),
    CONSTRAINT chk_ks2i_price  CHECK (unit_price       >= 0),
    CONSTRAINT chk_ks2i_total  CHECK (total            >= 0)
);
COMMENT ON TABLE ops.ks2_item IS 'Позиции акта КС-2 по работам';
