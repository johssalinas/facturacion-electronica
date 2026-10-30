-- Ventas por día en Octubre con IVA, acumuladas
SELECT 
    si.posting_date,
    COUNT(DISTINCT si.name) as facturas,
    SUM(si.grand_total) as total_dia,
    @running_total := @running_total + SUM(si.grand_total) as acumulado
FROM `tabSales Invoice` si
INNER JOIN `tabSales Taxes and Charges` stc ON stc.parent = si.name
CROSS JOIN (SELECT @running_total := 0) r
WHERE si.posting_date >= '2026-10-01'
AND si.posting_date <= '2026-10-31'
AND si.docstatus = 1
AND stc.parenttype = 'Sales Invoice'
AND stc.account_head LIKE '%ventas por pagar%'
AND stc.rate IN (19, 5)
GROUP BY si.posting_date
ORDER BY si.posting_date;
