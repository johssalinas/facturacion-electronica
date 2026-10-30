-- Total de facturas en Septiembre 2026
SELECT 
    'Total Facturas' as tipo,
    COUNT(*) as cantidad,
    SUM(grand_total) as total
FROM `tabSales Invoice`
WHERE posting_date >= '2026-09-01'
AND posting_date <= '2026-09-30'
AND docstatus = 1

UNION ALL

-- Facturas CON impuestos IVA 19% o 5%
SELECT 
    'Con IVA 19% o 5%' as tipo,
    COUNT(DISTINCT si.name) as cantidad,
    SUM(si.grand_total) as total
FROM `tabSales Invoice` si
INNER JOIN `tabSales Taxes and Charges` stc ON stc.parent = si.name
WHERE si.posting_date >= '2026-09-01'
AND si.posting_date <= '2026-09-30'
AND si.docstatus = 1
AND stc.parenttype = 'Sales Invoice'
AND stc.account_head LIKE '%ventas por pagar%'
AND stc.rate IN (19, 5)

UNION ALL

-- Facturas SIN impuestos
SELECT 
    'Sin impuestos' as tipo,
    COUNT(*) as cantidad,
    SUM(grand_total) as total
FROM `tabSales Invoice` si
WHERE si.posting_date >= '2026-09-01'
AND si.posting_date <= '2026-09-30'
AND si.docstatus = 1
AND NOT EXISTS (
    SELECT 1 
    FROM `tabSales Taxes and Charges` stc 
    WHERE stc.parent = si.name 
    AND stc.parenttype = 'Sales Invoice'
);
