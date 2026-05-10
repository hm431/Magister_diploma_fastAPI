-- Роли пользователей
CREATE TABLE ref.role (
    role_id      SERIAL PRIMARY KEY,
    name         VARCHAR(50)  NOT NULL UNIQUE,
    permissions  JSONB        NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_role_name CHECK (name IN ('Администратор', 'ПТО', 'МТС', 'Руководитель'))
);
COMMENT ON TABLE ref.role IS 'Роли пользователей системы';
