-- Septiembre: encontrar días para llegar a $36,300,000 CON IVA
-- Restando SM1 ($2,094,652) ya generada
-- Objetivo restante: $34,205,348

SELECT 
    si.posting_date,
    COUNT(DISTINCT si.name) as facturas,
    SUM(si.grand_total) as total_con_iva,
    @running_total := @running_total + SUM(si.grand_total) as acumulado
FROM `tabSales Invoice` si
INNER JOIN `tabSales Taxes and Charges` stc ON stc.parent = si.name
CROSS JOIN (SELECT @running_total := 2094652.28) r
WHERE si.posting_date >= '2026-09-01'
AND si.posting_date <= '2026-09-30'
AND si.docstatus = 1
AND stc.parenttype = 'Sales Invoice'
AND stc.account_head LIKE '%ventas por pagar%'
AND stc.rate IN (19, 5)
GROUP BY si.posting_date
ORDER BY si.posting_date;
