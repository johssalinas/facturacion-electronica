SELECT DISTINCT 
    stc.account_head, 
    stc.rate, 
    COUNT(DISTINCT si.name) as num_facturas
FROM `tabSales Taxes and Charges` stc
INNER JOIN `tabSales Invoice` si ON si.name = stc.parent
WHERE si.posting_date >= '2026-08-01'
AND si.posting_date <= '2026-08-31'
AND si.docstatus = 1
AND stc.parenttype = 'Sales Invoice'
GROUP BY stc.account_head, stc.rate
ORDER BY num_facturas DESC
LIMIT 10;
