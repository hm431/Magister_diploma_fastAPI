-- Элементы расписания (результаты CPM)
CREATE TABLE sro.schedule_item (
    calculation_id INTEGER NOT NULL,
    work_id        INTEGER NOT NULL,
    es             INTEGER NOT NULL,
    ef             INTEGER NOT NULL,
    ls             INTEGER NOT NULL,
    lf             INTEGER NOT NULL,
    tf             INTEGER NOT NULL,
    is_critical    BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (calculation_id, work_id),
    CONSTRAINT fk_si_calc CHECK (es >= 0 AND ef >= es AND lf >= ls AND tf >= 0),
    CONSTRAINT fk_si_calculation FOREIGN KEY (calculation_id) REFERENCES sro.schedule_calculation(calculation_id) ON DELETE CASCADE,
    CONSTRAINT fk_si_work        FOREIGN KEY (work_id)        REFERENCES sro.work(work_id)
);
CREATE INDEX idx_si_work ON sro.schedule_item(work_id);
-- Поиск активных работ на дату
CREATE INDEX idx_schedule_item_dates ON sro.schedule_item(calculation_id, es, ef);
COMMENT ON TABLE sro.schedule_item IS 'Расчётные параметры работ: ES, EF, LS, LF, TF (формулы 2.1-2.5)';
