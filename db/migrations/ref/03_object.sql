-- Объекты строительства
CREATE TABLE ref.object (
    object_id       SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    address         VARCHAR(500),
    type            VARCHAR(100) NOT NULL,
    planned_start   DATE,
    planned_finish  DATE,
    contract_amount NUMERIC(15,2),
    customer        VARCHAR(255),
    CONSTRAINT chk_object_type CHECK (type IN (
        'Водозабор', 'Насосная станция', 'Водопровод',
        'Коллектор', 'Очистные сооружения', 'Иное')),
    CONSTRAINT chk_object_dates CHECK (planned_finish IS NULL OR planned_finish >= planned_start)
);
COMMENT ON TABLE ref.object IS 'Справочник объектов строительства';
