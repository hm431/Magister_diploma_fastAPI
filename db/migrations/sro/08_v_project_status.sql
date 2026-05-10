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
