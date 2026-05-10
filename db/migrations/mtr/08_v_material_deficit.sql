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
