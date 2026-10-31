-- SEPTIEMBRE: Total por día de facturas con IVA (usando grand_total)
SELECT 
    DATE(si.posting_date) as fecha,
    COUNT(DISTINCT si.name) as num_facturas,
    SUM(si.grand_total) as total_dia_con_iva
FROM `tabSales Invoice` si
WHERE si.posting_date >= '2026-09-01'
AND si.posting_date <= '2026-09-30'
AND si.docstatus = 1
AND IFNULL(si.is_return, 0) = 0
AND EXISTS (
    SELECT 1
    FROM `tabSales Taxes and Charges` stc
    WHERE stc.parent = si.name
    AND stc.parenttype = 'Sales Invoice'
    AND stc.account_head LIKE '%ventas por pagar%'
    AND stc.rate IN (19, 5)
)
GROUP BY DATE(si.posting_date)
ORDER BY si.posting_date;

-- Separador
SELECT '---OCTUBRE---' as separador;

-- OCTUBRE: Total por día de facturas con IVA (usando grand_total)
SELECT 
    DATE(si.posting_date) as fecha,
    COUNT(DISTINCT si.name) as num_facturas,
    SUM(si.grand_total) as total_dia_con_iva
FROM `tabSales Invoice` si
WHERE si.posting_date >= '2026-10-01'
AND si.posting_date <= '2026-10-31'
AND si.docstatus = 1
AND IFNULL(si.is_return, 0) = 0
AND EXISTS (
    SELECT 1
    FROM `tabSales Taxes and Charges` stc
    WHERE stc.parent = si.name
    AND stc.parenttype = 'Sales Invoice'
    AND stc.account_head LIKE '%ventas por pagar%'
    AND stc.rate IN (19, 5)
)
GROUP BY DATE(si.posting_date)
ORDER BY si.posting_date;
