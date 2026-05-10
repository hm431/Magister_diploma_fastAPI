-- ============================================================================
-- DDL-СКРИПТ БАЗЫ ДАННЫХ
-- Проектное решение по автоматизации задач подсистем КИС
-- ООО "Тюмень Водоканал"
-- ----------------------------------------------------------------------------
-- Подсистемы: СРО (Управление строительными работами и объектами)
--             МТР (Управление материально-техническими ресурсами)
-- СУБД: PostgreSQL 14+
-- ============================================================================

-- ============================================================================
-- СОЗДАНИЕ СХЕМ (функциональных модулей)
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS ref;          -- Справочники
CREATE SCHEMA IF NOT EXISTS norm;         -- Нормативно-справочный аппарат
CREATE SCHEMA IF NOT EXISTS sro;          -- Календарное планирование
CREATE SCHEMA IF NOT EXISTS mtr;          -- Материально-техническое обеспечение
CREATE SCHEMA IF NOT EXISTS ops;          -- Оперативный учёт
CREATE SCHEMA IF NOT EXISTS risk;         -- Анализ рисков

COMMENT ON SCHEMA ref  IS 'Справочники предметной области';
COMMENT ON SCHEMA norm IS 'Нормативно-справочный аппарат (связующие таблицы)';
COMMENT ON SCHEMA sro  IS 'Подсистема управления строительными работами и объектами';
COMMENT ON SCHEMA mtr  IS 'Подсистема управления материально-техническими ресурсами';
COMMENT ON SCHEMA ops  IS 'Оперативный учёт хода строительства (КС-6, КС-2, КС-3)';
COMMENT ON SCHEMA risk IS 'Анализ рисков (имитационное моделирование Монте-Карло)';


-- ============================================================================
-- МОДУЛЬ 1. СПРАВОЧНИКИ ПРЕДМЕТНОЙ ОБЛАСТИ (schema: ref)
-- ============================================================================

-- Роли пользователей
CREATE TABLE ref.role (
    role_id      SERIAL PRIMARY KEY,
    name         VARCHAR(50)  NOT NULL UNIQUE,
    permissions  JSONB        NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_role_name CHECK (name IN ('Администратор', 'ПТО', 'МТС', 'Руководитель'))
);
COMMENT ON TABLE ref.role IS 'Роли пользователей системы';

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

-- Строительные участки
CREATE TABLE ref.site (
    site_id        SERIAL PRIMARY KEY,
    object_id      INTEGER NOT NULL,
    name           VARCHAR(255) NOT NULL,
    coordinates    POINT,
    planned_volume NUMERIC(12,3),
    CONSTRAINT fk_site_object FOREIGN KEY (object_id) REFERENCES ref.object(object_id) ON DELETE CASCADE
);
CREATE INDEX idx_site_object ON ref.site(object_id);
COMMENT ON TABLE ref.site IS 'Строительные участки в составе объектов';

-- Типы работ
CREATE TABLE ref.work_type (
    work_type_id           SERIAL PRIMARY KEY,
    name                   VARCHAR(255) NOT NULL,
    unit                   VARCHAR(20)  NOT NULL,
    normative_productivity NUMERIC(10,3),
    technological_group    VARCHAR(100)
);
COMMENT ON TABLE ref.work_type IS 'Справочник типовых СМР';

-- Материалы
CREATE TABLE ref.material (
    material_id            SERIAL PRIMARY KEY,
    name                   VARCHAR(255) NOT NULL,
    unit                   VARCHAR(20)  NOT NULL,
    storage_coefficient    NUMERIC(8,4),
    category               VARCHAR(100),
    requires_certification BOOLEAN      NOT NULL DEFAULT FALSE,
    CONSTRAINT chk_storage_coef CHECK (storage_coefficient IS NULL OR storage_coefficient >= 0)
);
COMMENT ON TABLE ref.material IS 'Номенклатурный справочник материалов';
COMMENT ON COLUMN ref.material.storage_coefficient IS 'Коэффициент w_j (формула 2.22) - удельная площадь/объём хранения';

-- Поставщики
CREATE TABLE ref.supplier (
    supplier_id       SERIAL PRIMARY KEY,
    name              VARCHAR(255) NOT NULL,
    inn               VARCHAR(12)  UNIQUE,
    reliability_class CHAR(1),
    CONSTRAINT chk_reliability CHECK (reliability_class IS NULL OR reliability_class IN ('A','B','C','D'))
);
COMMENT ON TABLE ref.supplier IS 'Справочник поставщиков';

-- Склады
CREATE TABLE ref.warehouse (
    warehouse_id        SERIAL PRIMARY KEY,
    name                VARCHAR(255) NOT NULL,
    address             VARCHAR(500),
    capacity            NUMERIC(12,2),
    loading_posts       INTEGER      NOT NULL DEFAULT 1,
    service_rate        NUMERIC(8,4),
    allowed_wait_time   INTEGER,
    CONSTRAINT chk_capacity     CHECK (capacity IS NULL OR capacity > 0),
    CONSTRAINT chk_loading_pos  CHECK (loading_posts > 0),
    CONSTRAINT chk_service_rate CHECK (service_rate IS NULL OR service_rate > 0)
);
COMMENT ON TABLE ref.warehouse IS 'Склады отгрузки и приёмки';
COMMENT ON COLUMN ref.warehouse.capacity          IS 'U_max - вместимость склада (формула 2.23)';
COMMENT ON COLUMN ref.warehouse.loading_posts     IS 'n_р - количество разгрузочных постов (формула 2.26)';
COMMENT ON COLUMN ref.warehouse.service_rate      IS 'μ - интенсивность обслуживания (формула 2.26)';
COMMENT ON COLUMN ref.warehouse.allowed_wait_time IS 'W_q^доп - допустимое время ожидания, мин (формула 2.30)';

-- Бригады
CREATE TABLE ref.brigade (
    brigade_id    SERIAL PRIMARY KEY,
    name          VARCHAR(255) NOT NULL,
    headcount     INTEGER      NOT NULL,
    base_location VARCHAR(255),
    CONSTRAINT chk_headcount CHECK (headcount > 0)
);
COMMENT ON TABLE ref.brigade IS 'Производственные бригады';

-- Техника и оборудование
CREATE TABLE ref.equipment (
    equipment_id        SERIAL PRIMARY KEY,
    type                VARCHAR(100) NOT NULL,
    model               VARCHAR(255),
    base_warehouse_id   INTEGER,
    availability_status VARCHAR(50)  NOT NULL DEFAULT 'available',
    CONSTRAINT fk_equipment_warehouse FOREIGN KEY (base_warehouse_id) REFERENCES ref.warehouse(warehouse_id),
    CONSTRAINT chk_avail_status CHECK (availability_status IN ('available', 'in_use', 'maintenance', 'broken'))
);
CREATE INDEX idx_equipment_warehouse ON ref.equipment(base_warehouse_id);
COMMENT ON TABLE ref.equipment IS 'Парк техники и оборудования';

-- Квалификации
CREATE TABLE ref.qualification (
    qualification_id SERIAL PRIMARY KEY,
    name             VARCHAR(255) NOT NULL,
    level            INTEGER,
    CONSTRAINT chk_qual_level CHECK (level IS NULL OR level BETWEEN 1 AND 10)
);
COMMENT ON TABLE ref.qualification IS 'Квалификационные требования и разряды';


-- ============================================================================
-- МОДУЛЬ 2. НОРМАТИВНО-СПРАВОЧНЫЙ АППАРАТ (schema: norm)
-- ============================================================================

-- Нормы расхода материалов (r_{ij} из формулы 2.9)
CREATE TABLE norm.consumption_norm (
    work_type_id    INTEGER     NOT NULL,
    material_id     INTEGER     NOT NULL,
    norm_value      NUMERIC(12,6) NOT NULL,
    effective_from  DATE        NOT NULL DEFAULT CURRENT_DATE,
    PRIMARY KEY (work_type_id, material_id, effective_from),
    CONSTRAINT fk_norm_work_type FOREIGN KEY (work_type_id) REFERENCES ref.work_type(work_type_id),
    CONSTRAINT fk_norm_material  FOREIGN KEY (material_id)  REFERENCES ref.material(material_id),
    CONSTRAINT chk_norm_value CHECK (norm_value >= 0)
);
COMMENT ON TABLE norm.consumption_norm IS 'Нормы расхода r_{ij} - связь работ и материалов';

-- Квалификации бригад
CREATE TABLE norm.brigade_qualification (
    brigade_id        INTEGER NOT NULL,
    qualification_id  INTEGER NOT NULL,
    PRIMARY KEY (brigade_id, qualification_id),
    CONSTRAINT fk_bq_brigade       FOREIGN KEY (brigade_id)       REFERENCES ref.brigade(brigade_id)             ON DELETE CASCADE,
    CONSTRAINT fk_bq_qualification FOREIGN KEY (qualification_id) REFERENCES ref.qualification(qualification_id)
);
COMMENT ON TABLE norm.brigade_qualification IS 'Связь бригад и квалификаций (многие ко многим)';

-- Договоры поставки
CREATE TABLE norm.supply_contract (
    contract_id           SERIAL PRIMARY KEY,
    supplier_id           INTEGER       NOT NULL,
    material_id           INTEGER       NOT NULL,
    price_per_unit        NUMERIC(12,2) NOT NULL,
    min_delivery_days     INTEGER       NOT NULL,
    max_volume_per_period NUMERIC(12,3),
    valid_from            DATE          NOT NULL,
    valid_to              DATE,
    CONSTRAINT fk_sc_supplier FOREIGN KEY (supplier_id) REFERENCES ref.supplier(supplier_id),
    CONSTRAINT fk_sc_material FOREIGN KEY (material_id) REFERENCES ref.material(material_id),
    CONSTRAINT chk_sc_price   CHECK (price_per_unit >= 0),
    CONSTRAINT chk_sc_days    CHECK (min_delivery_days >= 0),
    CONSTRAINT chk_sc_period  CHECK (valid_to IS NULL OR valid_to >= valid_from)
);
CREATE INDEX idx_sc_supplier ON norm.supply_contract(supplier_id);
CREATE INDEX idx_sc_material ON norm.supply_contract(material_id);
COMMENT ON TABLE norm.supply_contract IS 'Договоры поставки (содержит c_{jlt} и τ_{jl}^мин)';
COMMENT ON COLUMN norm.supply_contract.min_delivery_days IS 'τ_{jl}^мин - минимальный срок поставки (формула 2.16)';

-- Параметры транспортной доставки
CREATE TABLE norm.transport_param (
    material_id        INTEGER       NOT NULL,
    warehouse_id       INTEGER       NOT NULL,
    avg_capacity       NUMERIC(10,3) NOT NULL,
    avg_delivery_time  INTEGER       NOT NULL,
    PRIMARY KEY (material_id, warehouse_id),
    CONSTRAINT fk_tp_material  FOREIGN KEY (material_id)  REFERENCES ref.material(material_id),
    CONSTRAINT fk_tp_warehouse FOREIGN KEY (warehouse_id) REFERENCES ref.warehouse(warehouse_id),
    CONSTRAINT chk_tp_capacity CHECK (avg_capacity > 0),
    CONSTRAINT chk_tp_time     CHECK (avg_delivery_time > 0)
);
COMMENT ON TABLE norm.transport_param IS 'Параметры транспортной доставки (q_{jl} - грузоподъёмность, формула 2.25)';


-- ============================================================================
-- МОДУЛЬ 3. КАЛЕНДАРНОЕ ПЛАНИРОВАНИЕ - подсистема СРО (schema: sro)
-- ============================================================================

-- Проекты
CREATE TABLE sro.project (
    project_id    SERIAL PRIMARY KEY,
    object_id     INTEGER     NOT NULL,
    status        VARCHAR(50) NOT NULL DEFAULT 'planned',
    plan_start    DATE        NOT NULL,
    plan_finish   DATE        NOT NULL,
    actual_start  DATE,
    actual_finish DATE,
    CONSTRAINT fk_project_object FOREIGN KEY (object_id) REFERENCES ref.object(object_id),
    CONSTRAINT chk_project_status CHECK (status IN ('planned', 'in_progress', 'completed', 'suspended', 'cancelled')),
    CONSTRAINT chk_project_dates  CHECK (plan_finish >= plan_start)
);
CREATE INDEX idx_project_object ON sro.project(object_id);
CREATE INDEX idx_project_status ON sro.project(status);
COMMENT ON TABLE sro.project IS 'Проекты строительства (T_план - plan_finish)';

-- Работы
CREATE TABLE sro.work (
    work_id                  SERIAL PRIMARY KEY,
    project_id               INTEGER NOT NULL,
    site_id                  INTEGER NOT NULL,
    work_type_id             INTEGER NOT NULL,
    duration                 INTEGER NOT NULL,
    volume                   NUMERIC(12,3) NOT NULL,
    required_qualification_id INTEGER,
    required_equipment_type  VARCHAR(100),
    CONSTRAINT fk_work_project   FOREIGN KEY (project_id)                REFERENCES sro.project(project_id) ON DELETE CASCADE,
    CONSTRAINT fk_work_site      FOREIGN KEY (site_id)                   REFERENCES ref.site(site_id),
    CONSTRAINT fk_work_type      FOREIGN KEY (work_type_id)              REFERENCES ref.work_type(work_type_id),
    CONSTRAINT fk_work_qual      FOREIGN KEY (required_qualification_id) REFERENCES ref.qualification(qualification_id),
    CONSTRAINT chk_work_duration CHECK (duration > 0),
    CONSTRAINT chk_work_volume   CHECK (volume   > 0)
);
CREATE INDEX idx_work_project ON sro.work(project_id);
CREATE INDEX idx_work_site    ON sro.work(site_id);
COMMENT ON TABLE sro.work IS 'Работы проекта (множество I, d_i = duration, v_i = volume)';

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

-- Расчёты календарного графика
CREATE TABLE sro.schedule_calculation (
    calculation_id   SERIAL PRIMARY KEY,
    project_id       INTEGER     NOT NULL,
    calculation_date TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    version          INTEGER     NOT NULL DEFAULT 1,
    t_min            INTEGER,
    scenario         VARCHAR(50) NOT NULL DEFAULT 'plan',
    CONSTRAINT fk_sc_project   FOREIGN KEY (project_id) REFERENCES sro.project(project_id) ON DELETE CASCADE,
    CONSTRAINT chk_sc_scenario CHECK (scenario IN ('plan', 'actual', 'counterfactual', 'correction'))
);
CREATE INDEX idx_sched_calc_project ON sro.schedule_calculation(project_id);
COMMENT ON TABLE sro.schedule_calculation IS 'Версии расчёта календарного графика';
COMMENT ON COLUMN sro.schedule_calculation.t_min IS 'T_min - минимальная продолжительность проекта (формула 2.7)';

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
COMMENT ON TABLE sro.schedule_item IS 'Расчётные параметры работ: ES, EF, LS, LF, TF (формулы 2.1-2.5)';

-- Назначения бригад на участки
CREATE TABLE sro.brigade_assignment (
    assignment_id           SERIAL PRIMARY KEY,
    brigade_id              INTEGER NOT NULL,
    site_id                 INTEGER NOT NULL,
    period_start            DATE    NOT NULL,
    period_end              DATE    NOT NULL,
    assignment_cost         NUMERIC(12,4),
    schedule_calculation_id INTEGER NOT NULL,
    CONSTRAINT fk_ba_brigade  FOREIGN KEY (brigade_id)              REFERENCES ref.brigade(brigade_id),
    CONSTRAINT fk_ba_site     FOREIGN KEY (site_id)                 REFERENCES ref.site(site_id),
    CONSTRAINT fk_ba_calc     FOREIGN KEY (schedule_calculation_id) REFERENCES sro.schedule_calculation(calculation_id) ON DELETE CASCADE,
    CONSTRAINT chk_ba_period  CHECK (period_end >= period_start)
);
CREATE INDEX idx_ba_brigade ON sro.brigade_assignment(brigade_id);
CREATE INDEX idx_ba_site    ON sro.brigade_assignment(site_id);
CREATE INDEX idx_ba_calc    ON sro.brigade_assignment(schedule_calculation_id);
COMMENT ON TABLE sro.brigade_assignment IS 'Назначения бригад (y_{ks} из формулы 2.31), c_{ks} = assignment_cost';

-- Закрепление техники за участками
CREATE TABLE sro.equipment_assignment (
    equipment_id INTEGER NOT NULL,
    site_id      INTEGER NOT NULL,
    period_start DATE    NOT NULL,
    period_end   DATE    NOT NULL,
    PRIMARY KEY (equipment_id, site_id, period_start),
    CONSTRAINT fk_ea_equipment FOREIGN KEY (equipment_id) REFERENCES ref.equipment(equipment_id),
    CONSTRAINT fk_ea_site      FOREIGN KEY (site_id)      REFERENCES ref.site(site_id),
    CONSTRAINT chk_ea_period   CHECK (period_end >= period_start)
);
COMMENT ON TABLE sro.equipment_assignment IS 'Закрепление техники за строительными участками';


-- ============================================================================
-- МОДУЛЬ 4. МАТЕРИАЛЬНО-ТЕХНИЧЕСКОЕ ОБЕСПЕЧЕНИЕ - подсистема МТР (schema: mtr)
-- ============================================================================

-- Остатки на складах (S_{jt}, V_{jt})
CREATE TABLE mtr.stock_balance (
    stock_id          SERIAL PRIMARY KEY,
    material_id       INTEGER       NOT NULL,
    warehouse_id      INTEGER       NOT NULL,
    balance_date      DATE          NOT NULL,
    quantity          NUMERIC(12,3) NOT NULL,
    reserved_quantity NUMERIC(12,3) NOT NULL DEFAULT 0,
    CONSTRAINT fk_sb_material  FOREIGN KEY (material_id)  REFERENCES ref.material(material_id),
    CONSTRAINT fk_sb_warehouse FOREIGN KEY (warehouse_id) REFERENCES ref.warehouse(warehouse_id),
    CONSTRAINT chk_sb_quantity CHECK (quantity >= 0 AND reserved_quantity >= 0),
    CONSTRAINT uq_sb_position  UNIQUE (material_id, warehouse_id, balance_date)
);
CREATE INDEX idx_sb_material  ON mtr.stock_balance(material_id);
CREATE INDEX idx_sb_warehouse ON mtr.stock_balance(warehouse_id);
CREATE INDEX idx_sb_date      ON mtr.stock_balance(balance_date);
COMMENT ON TABLE mtr.stock_balance IS 'Остатки материалов на складах (S_{jt}, V_{jt} из формул 2.10, 2.21)';

-- Журнал движения материалов
CREATE TABLE mtr.stock_movement (
    movement_id           SERIAL PRIMARY KEY,
    material_id           INTEGER       NOT NULL,
    warehouse_id          INTEGER       NOT NULL,
    movement_date         TIMESTAMP     NOT NULL,
    movement_type         VARCHAR(50)   NOT NULL,
    quantity              NUMERIC(12,3) NOT NULL,
    source_document_id    INTEGER,
    source_document_type  VARCHAR(50),
    CONSTRAINT fk_sm_material  FOREIGN KEY (material_id)  REFERENCES ref.material(material_id),
    CONSTRAINT fk_sm_warehouse FOREIGN KEY (warehouse_id) REFERENCES ref.warehouse(warehouse_id),
    CONSTRAINT chk_sm_type     CHECK (movement_type IN ('incoming', 'outgoing', 'transfer', 'writeoff')),
    CONSTRAINT chk_sm_quantity CHECK (quantity > 0)
);
CREATE INDEX idx_sm_material ON mtr.stock_movement(material_id);
CREATE INDEX idx_sm_date     ON mtr.stock_movement(movement_date);
COMMENT ON TABLE mtr.stock_movement IS 'Журнал движения материалов (приходы, расходы, перемещения)';

-- Плановые поставки (x_{jlt})
CREATE TABLE mtr.planned_delivery (
    planned_delivery_id SERIAL PRIMARY KEY,
    project_id          INTEGER       NOT NULL,
    material_id         INTEGER       NOT NULL,
    warehouse_id        INTEGER       NOT NULL,
    supplier_id         INTEGER       NOT NULL,
    planned_date        DATE          NOT NULL,
    planned_volume      NUMERIC(12,3) NOT NULL,
    unit_cost           NUMERIC(12,2) NOT NULL,
    status              VARCHAR(50)   NOT NULL DEFAULT 'planned',
    CONSTRAINT fk_pd_project   FOREIGN KEY (project_id)   REFERENCES sro.project(project_id) ON DELETE CASCADE,
    CONSTRAINT fk_pd_material  FOREIGN KEY (material_id)  REFERENCES ref.material(material_id),
    CONSTRAINT fk_pd_warehouse FOREIGN KEY (warehouse_id) REFERENCES ref.warehouse(warehouse_id),
    CONSTRAINT fk_pd_supplier  FOREIGN KEY (supplier_id)  REFERENCES ref.supplier(supplier_id),
    CONSTRAINT chk_pd_volume   CHECK (planned_volume > 0),
    CONSTRAINT chk_pd_cost     CHECK (unit_cost >= 0),
    CONSTRAINT chk_pd_status   CHECK (status IN ('planned', 'confirmed', 'shipped', 'delivered', 'cancelled'))
);
CREATE INDEX idx_pd_project  ON mtr.planned_delivery(project_id);
CREATE INDEX idx_pd_material ON mtr.planned_delivery(material_id);
CREATE INDEX idx_pd_date     ON mtr.planned_delivery(planned_date);
COMMENT ON TABLE mtr.planned_delivery IS 'Плановые поставки (x_{jlt} из формулы 2.12)';

-- Фактические поставки
CREATE TABLE mtr.actual_delivery (
    actual_delivery_id   SERIAL PRIMARY KEY,
    planned_delivery_id  INTEGER,
    material_id          INTEGER       NOT NULL,
    warehouse_id         INTEGER       NOT NULL,
    supplier_id          INTEGER       NOT NULL,
    actual_date          DATE          NOT NULL,
    actual_volume        NUMERIC(12,3) NOT NULL,
    deviation_days       INTEGER,
    CONSTRAINT fk_ad_planned   FOREIGN KEY (planned_delivery_id) REFERENCES mtr.planned_delivery(planned_delivery_id),
    CONSTRAINT fk_ad_material  FOREIGN KEY (material_id)         REFERENCES ref.material(material_id),
    CONSTRAINT fk_ad_warehouse FOREIGN KEY (warehouse_id)        REFERENCES ref.warehouse(warehouse_id),
    CONSTRAINT fk_ad_supplier  FOREIGN KEY (supplier_id)         REFERENCES ref.supplier(supplier_id),
    CONSTRAINT chk_ad_volume   CHECK (actual_volume > 0)
);
CREATE INDEX idx_ad_planned  ON mtr.actual_delivery(planned_delivery_id);
CREATE INDEX idx_ad_material ON mtr.actual_delivery(material_id);
CREATE INDEX idx_ad_date     ON mtr.actual_delivery(actual_date);
COMMENT ON TABLE mtr.actual_delivery IS 'Фактические поставки (синхронизация через ETL из 1С)';

-- Плановая потребность в материалах (Q_{jt})
CREATE TABLE mtr.material_demand (
    project_id              INTEGER       NOT NULL,
    material_id             INTEGER       NOT NULL,
    demand_date             DATE          NOT NULL,
    quantity                NUMERIC(12,3) NOT NULL,
    schedule_calculation_id INTEGER       NOT NULL,
    PRIMARY KEY (project_id, material_id, demand_date, schedule_calculation_id),
    CONSTRAINT fk_md_project  FOREIGN KEY (project_id)              REFERENCES sro.project(project_id) ON DELETE CASCADE,
    CONSTRAINT fk_md_material FOREIGN KEY (material_id)             REFERENCES ref.material(material_id),
    CONSTRAINT fk_md_calc     FOREIGN KEY (schedule_calculation_id) REFERENCES sro.schedule_calculation(calculation_id) ON DELETE CASCADE,
    CONSTRAINT chk_md_qty     CHECK (quantity >= 0)
);
COMMENT ON TABLE mtr.material_demand IS 'Плановая потребность Q_{jt} (формула 2.9)';

-- Профиль загрузки склада (U_t)
CREATE TABLE mtr.warehouse_load_profile (
    warehouse_id    INTEGER       NOT NULL,
    profile_date    DATE          NOT NULL,
    total_load      NUMERIC(12,2) NOT NULL,
    peak_indicator  BOOLEAN       NOT NULL DEFAULT FALSE,
    queue_length    NUMERIC(8,3),
    wait_time       NUMERIC(8,3),
    PRIMARY KEY (warehouse_id, profile_date),
    CONSTRAINT fk_wlp_warehouse FOREIGN KEY (warehouse_id) REFERENCES ref.warehouse(warehouse_id),
    CONSTRAINT chk_wlp_load     CHECK (total_load >= 0)
);
CREATE INDEX idx_wlp_date ON mtr.warehouse_load_profile(profile_date);
COMMENT ON TABLE mtr.warehouse_load_profile IS 'Загрузка склада U_t (формула 2.22), L_q (2.28), W_q (2.29)';

-- Даты гарантированной доступности материалов (T_доступ(j))
CREATE TABLE mtr.material_availability_date (
    project_id        INTEGER NOT NULL,
    material_id       INTEGER NOT NULL,
    availability_date DATE    NOT NULL,
    calculation_id    INTEGER NOT NULL,
    PRIMARY KEY (project_id, material_id, calculation_id),
    CONSTRAINT fk_mad_project  FOREIGN KEY (project_id)     REFERENCES sro.project(project_id) ON DELETE CASCADE,
    CONSTRAINT fk_mad_material FOREIGN KEY (material_id)    REFERENCES ref.material(material_id),
    CONSTRAINT fk_mad_calc     FOREIGN KEY (calculation_id) REFERENCES sro.schedule_calculation(calculation_id) ON DELETE CASCADE
);
COMMENT ON TABLE mtr.material_availability_date IS 'T_доступ(j) - даты гарантированной доступности (формула 2.18)';


-- ============================================================================
-- МОДУЛЬ 5. ОПЕРАТИВНЫЙ УЧЁТ (schema: ops)
-- ============================================================================

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

-- Справки о стоимости КС-3
CREATE TABLE ops.ks3_certificate (
    certificate_id SERIAL PRIMARY KEY,
    project_id     INTEGER       NOT NULL,
    period_start   DATE          NOT NULL,
    period_end     DATE          NOT NULL,
    total_amount   NUMERIC(15,2) NOT NULL,
    CONSTRAINT fk_ks3_project FOREIGN KEY (project_id) REFERENCES sro.project(project_id) ON DELETE CASCADE,
    CONSTRAINT chk_ks3_period CHECK (period_end >= period_start),
    CONSTRAINT chk_ks3_amount CHECK (total_amount >= 0)
);
COMMENT ON TABLE ops.ks3_certificate IS 'Справки о стоимости выполненных работ КС-3';

-- Отклонения по работам
CREATE TABLE ops.deviation (
    deviation_id    SERIAL PRIMARY KEY,
    work_id         INTEGER      NOT NULL,
    detection_date  DATE         NOT NULL,
    plan_percent    NUMERIC(5,4) NOT NULL,
    fact_percent    NUMERIC(5,4) NOT NULL,
    delta_percent   NUMERIC(5,4) NOT NULL,
    chi_mtr         BOOLEAN      NOT NULL DEFAULT FALSE,
    category        VARCHAR(50)  NOT NULL,
    CONSTRAINT fk_dev_work CHECK (
        plan_percent  BETWEEN 0 AND 1 AND
        fact_percent  BETWEEN 0 AND 1 AND
        delta_percent BETWEEN -1 AND 1),
    CONSTRAINT fk_dev_work_fk FOREIGN KEY (work_id) REFERENCES sro.work(work_id) ON DELETE CASCADE,
    CONSTRAINT chk_dev_cat    CHECK (category IN ('MTR', 'weather', 'technological', 'personnel', 'other'))
);
CREATE INDEX idx_dev_work     ON ops.deviation(work_id);
CREATE INDEX idx_dev_date     ON ops.deviation(detection_date);
CREATE INDEX idx_dev_category ON ops.deviation(category);
COMMENT ON TABLE ops.deviation IS 'Отклонения Δp_i (формула 2.51), χ_i^МТР (формула 2.53)';

-- Причины отклонений категории МТР
CREATE TABLE ops.deviation_cause (
    deviation_id    INTEGER NOT NULL,
    material_id     INTEGER NOT NULL,
    supplier_id     INTEGER NOT NULL,
    deficit_days    INTEGER NOT NULL,
    deficit_volume  NUMERIC(12,3) NOT NULL,
    PRIMARY KEY (deviation_id, material_id, supplier_id),
    CONSTRAINT fk_dc_deviation FOREIGN KEY (deviation_id) REFERENCES ops.deviation(deviation_id) ON DELETE CASCADE,
    CONSTRAINT fk_dc_material  FOREIGN KEY (material_id)  REFERENCES ref.material(material_id),
    CONSTRAINT fk_dc_supplier  FOREIGN KEY (supplier_id)  REFERENCES ref.supplier(supplier_id),
    CONSTRAINT chk_dc_days     CHECK (deficit_days   >= 0),
    CONSTRAINT chk_dc_volume   CHECK (deficit_volume >= 0)
);
COMMENT ON TABLE ops.deviation_cause IS 'Первопричины отклонений категории МТР с привязкой к поставщикам';


-- ============================================================================
-- МОДУЛЬ 6. АНАЛИЗ РИСКОВ (schema: risk)
-- ============================================================================

-- Параметры бета-распределения длительностей работ
CREATE TABLE risk.work_risk_params (
    work_id           INTEGER PRIMARY KEY,
    optimistic        NUMERIC(8,3) NOT NULL,
    most_likely       NUMERIC(8,3) NOT NULL,
    pessimistic       NUMERIC(8,3) NOT NULL,
    alpha             NUMERIC(8,4),
    beta              NUMERIC(8,4),
    expected_duration NUMERIC(8,3),
    std_deviation     NUMERIC(8,3),
    CONSTRAINT fk_wrp_work FOREIGN KEY (work_id) REFERENCES sro.work(work_id) ON DELETE CASCADE,
    CONSTRAINT chk_wrp_order CHECK (optimistic <= most_likely AND most_likely <= pessimistic)
);
COMMENT ON TABLE risk.work_risk_params IS 'Параметры бета-распределения d_i (a_i, m_i, b_i из формулы 2.39)';

-- Статистика сроков поставок поставщиков
CREATE TABLE risk.supplier_delivery_stats (
    supplier_id   INTEGER       NOT NULL,
    material_id   INTEGER       NOT NULL,
    mu_log        NUMERIC(8,4)  NOT NULL,
    sigma_log     NUMERIC(8,4)  NOT NULL,
    sample_size   INTEGER       NOT NULL,
    last_updated  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (supplier_id, material_id),
    CONSTRAINT fk_sds_supplier FOREIGN KEY (supplier_id) REFERENCES ref.supplier(supplier_id),
    CONSTRAINT fk_sds_material FOREIGN KEY (material_id) REFERENCES ref.material(material_id),
    CONSTRAINT chk_sds_sigma   CHECK (sigma_log   >= 0),
    CONSTRAINT chk_sds_sample  CHECK (sample_size >= 0)
);
COMMENT ON TABLE risk.supplier_delivery_stats IS 'μ_{jk}, σ²_{jk} логнормального распределения (формулы 2.42-2.44)';

-- Запуски имитации Монте-Карло
CREATE TABLE risk.monte_carlo_run (
    run_id            SERIAL PRIMARY KEY,
    project_id        INTEGER      NOT NULL,
    run_date          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    iterations_count  INTEGER      NOT NULL,
    seed              BIGINT,
    mean_duration     NUMERIC(10,3),
    std_duration      NUMERIC(10,3),
    prob_on_time      NUMERIC(5,4),
    CONSTRAINT fk_mcr_project   FOREIGN KEY (project_id) REFERENCES sro.project(project_id) ON DELETE CASCADE,
    CONSTRAINT chk_mcr_iter     CHECK (iterations_count > 0),
    CONSTRAINT chk_mcr_prob     CHECK (prob_on_time IS NULL OR prob_on_time BETWEEN 0 AND 1)
);
CREATE INDEX idx_mcr_project ON risk.monte_carlo_run(project_id);
COMMENT ON TABLE risk.monte_carlo_run IS 'Запуски Монте-Карло: E[T] (2.47), σ[T] (2.48), P(T≤T_план) (2.46)';

-- Итерации Монте-Карло
CREATE TABLE risk.monte_carlo_iteration (
    run_id          INTEGER NOT NULL,
    iteration_number INTEGER NOT NULL,
    t_r             NUMERIC(10,3) NOT NULL,
    c_r             NUMERIC(15,2),
    PRIMARY KEY (run_id, iteration_number),
    CONSTRAINT fk_mci_run FOREIGN KEY (run_id) REFERENCES risk.monte_carlo_run(run_id) ON DELETE CASCADE
);
COMMENT ON TABLE risk.monte_carlo_iteration IS 'Результаты отдельных итераций T^{(r)} (2.45), C^{(r)}';

-- Индексы критичности работ
CREATE TABLE risk.work_criticality_index (
    run_id             INTEGER      NOT NULL,
    work_id            INTEGER      NOT NULL,
    criticality_index  NUMERIC(5,4) NOT NULL,
    risk_critical      BOOLEAN      NOT NULL DEFAULT FALSE,
    PRIMARY KEY (run_id, work_id),
    CONSTRAINT fk_wci_run  FOREIGN KEY (run_id)  REFERENCES risk.monte_carlo_run(run_id) ON DELETE CASCADE,
    CONSTRAINT fk_wci_work FOREIGN KEY (work_id) REFERENCES sro.work(work_id),
    CONSTRAINT chk_wci_idx CHECK (criticality_index BETWEEN 0 AND 1)
);
COMMENT ON TABLE risk.work_criticality_index IS 'Индекс критичности CI_i (формула 2.50)';

-- Квантили распределения длительности проекта
CREATE TABLE risk.risk_quantile (
    run_id      INTEGER      NOT NULL,
    gamma_level NUMERIC(4,3) NOT NULL,
    t_gamma     NUMERIC(10,3) NOT NULL,
    PRIMARY KEY (run_id, gamma_level),
    CONSTRAINT fk_rq_run    FOREIGN KEY (run_id) REFERENCES risk.monte_carlo_run(run_id) ON DELETE CASCADE,
    CONSTRAINT chk_rq_gamma CHECK (gamma_level BETWEEN 0 AND 1)
);
COMMENT ON TABLE risk.risk_quantile IS 'Квантили T_γ из формулы 2.49';

-- Корректирующие сценарии
CREATE TABLE risk.correction_scenario (
    scenario_id      SERIAL PRIMARY KEY,
    deviation_id     INTEGER      NOT NULL,
    generation_date  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description      TEXT,
    delta_t          NUMERIC(8,3),
    delta_c          NUMERIC(15,2),
    delta_r          NUMERIC(5,4),
    j_score          NUMERIC(10,4),
    is_recommended   BOOLEAN      NOT NULL DEFAULT FALSE,
    CONSTRAINT fk_cs_deviation FOREIGN KEY (deviation_id) REFERENCES ops.deviation(deviation_id) ON DELETE CASCADE
);
CREATE INDEX idx_cs_deviation ON risk.correction_scenario(deviation_id);
COMMENT ON TABLE risk.correction_scenario IS 'Сценарии корректировки σ (формулы 2.63-2.64)';

-- Управляющие воздействия в составе сценариев
CREATE TABLE risk.scenario_action (
    scenario_id INTEGER     NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    target_id   INTEGER,
    parameters  JSONB,
    PRIMARY KEY (scenario_id, action_type, COALESCE(target_id, 0)),
    CONSTRAINT fk_sa_scenario FOREIGN KEY (scenario_id) REFERENCES risk.correction_scenario(scenario_id) ON DELETE CASCADE,
    CONSTRAINT chk_sa_type CHECK (action_type IN ('expedite_delivery', 'reassign_brigade', 'parallelize_works', 'add_resources', 'other'))
);
COMMENT ON TABLE risk.scenario_action IS 'Управляющие воздействия в составе корректирующего сценария';


-- ============================================================================
-- ДОПОЛНИТЕЛЬНЫЕ ИНДЕКСЫ ДЛЯ ЧАСТО ВЫПОЛНЯЕМЫХ ЗАПРОСОВ
-- ============================================================================

-- Поиск активных работ на дату
CREATE INDEX idx_schedule_item_dates ON sro.schedule_item(calculation_id, es, ef);

-- Поиск отклонений по проекту через work
CREATE INDEX idx_deviation_chi_mtr ON ops.deviation(chi_mtr) WHERE chi_mtr = TRUE;

-- Поиск рисковых работ
CREATE INDEX idx_wci_risk_critical ON risk.work_criticality_index(risk_critical) WHERE risk_critical = TRUE;

-- Поиск рекомендованных сценариев
CREATE INDEX idx_cs_recommended ON risk.correction_scenario(is_recommended) WHERE is_recommended = TRUE;


-- ============================================================================
-- ПРЕДСТАВЛЕНИЯ (VIEWS) ДЛЯ КЛЮЧЕВЫХ ОТЧЁТОВ
-- ============================================================================

-- Текущий статус проектов
CREATE OR REPLACE VIEW sro.v_project_status AS
SELECT
    p.project_id,
    o.name        AS object_name,
    p.status,
    p.plan_start,
    p.plan_finish,
    p.actual_start,
    p.actual_finish,
    (SELECT COUNT(*) FROM sro.work w WHERE w.project_id = p.project_id) AS total_works,
    (SELECT COUNT(*) FROM sro.work w
       JOIN ops.work_execution we ON we.work_id = w.work_id
       WHERE w.project_id = p.project_id AND we.fact_percent = 1) AS completed_works
FROM sro.project p
JOIN ref.object o ON o.object_id = p.object_id;

-- Дефицит материалов по проекту
CREATE OR REPLACE VIEW mtr.v_material_deficit AS
SELECT
    md.project_id,
    m.name AS material_name,
    md.demand_date,
    md.quantity AS demand,
    COALESCE(SUM(sb.quantity), 0) AS available,
    md.quantity - COALESCE(SUM(sb.quantity), 0) AS deficit
FROM mtr.material_demand md
JOIN ref.material m       ON m.material_id  = md.material_id
LEFT JOIN mtr.stock_balance sb
    ON sb.material_id  = md.material_id
   AND sb.balance_date = md.demand_date
GROUP BY md.project_id, m.name, md.demand_date, md.quantity
HAVING md.quantity > COALESCE(SUM(sb.quantity), 0);

-- ============================================================================
-- КОНЕЦ СКРИПТА
-- ============================================================================