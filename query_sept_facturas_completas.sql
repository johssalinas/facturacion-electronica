-- Septiembre: Facturas completas (grand_total) que tienen IVA
-- Ya generada SM1 del 2026-09-01: $2,094,652.28
-- Meta total: $36,300,000
-- Falta: $34,205,347.72

SELECT 
    DATE(si.posting_date) as fecha,
    COUNT(DISTINCT si.name) as num_facturas,
    SUM(si.grand_total) as total_dia_con_iva,
    @running := @running + SUM(si.grand_total) as acumulado
FROM `tabSales Invoice` si
INNER JOIN (
    SELECT DISTINCT parent
    FROM `tabSales Taxes and Charges`
    WHERE parenttype = 'Sales Invoice'
    AND account_head LIKE '%ventas por pagar%'
    AND rate IN (19, 5)
) stc ON stc.parent = si.name
CROSS JOIN (SELECT @running := 2094652.28) init
WHERE si.posting_date >= '2026-09-01'
AND si.posting_date <= '2026-09-30'
AND si.docstatus = 1
AND IFNULL(si.is_return, 0) = 0
GROUP BY DATE(si.posting_date)
ORDER BY si.posting_date;
