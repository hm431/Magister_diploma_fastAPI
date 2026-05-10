-- Поставщики
CREATE TABLE ref.supplier (
    supplier_id       SERIAL PRIMARY KEY,
    name              VARCHAR(255) NOT NULL,
    inn               VARCHAR(12)  UNIQUE,
    reliability_class CHAR(1),
    CONSTRAINT chk_reliability CHECK (reliability_class IS NULL OR reliability_class IN ('A','B','C','D'))
);
COMMENT ON TABLE ref.supplier IS 'Справочник поставщиков';
