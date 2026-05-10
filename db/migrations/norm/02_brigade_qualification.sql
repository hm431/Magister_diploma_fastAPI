-- Квалификации бригад
CREATE TABLE norm.brigade_qualification (
    brigade_id        INTEGER NOT NULL,
    qualification_id  INTEGER NOT NULL,
    PRIMARY KEY (brigade_id, qualification_id),
    CONSTRAINT fk_bq_brigade       FOREIGN KEY (brigade_id)       REFERENCES ref.brigade(brigade_id)             ON DELETE CASCADE,
    CONSTRAINT fk_bq_qualification FOREIGN KEY (qualification_id) REFERENCES ref.qualification(qualification_id)
);
COMMENT ON TABLE norm.brigade_qualification IS 'Связь бригад и квалификаций (многие ко многим)';
