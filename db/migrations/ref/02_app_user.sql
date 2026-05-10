-- Пользователи
CREATE TABLE ref.app_user (
    user_id    SERIAL PRIMARY KEY,
    login      VARCHAR(100) NOT NULL UNIQUE,
    full_name  VARCHAR(255) NOT NULL,
    role_id    INTEGER      NOT NULL,
    is_active  BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_user_role FOREIGN KEY (role_id) REFERENCES ref.role(role_id)
);
COMMENT ON TABLE ref.app_user IS 'Пользователи системы (аутентификация через Active Directory)';
