-- Actualizar numbering_range_id para Dueno Fiscal Lorena
UPDATE `tabDueno Fiscal` 
SET numbering_range_id = 6141 
WHERE name = 'Lorena';

-- Verificar el cambio
SELECT name, numbering_range_id, ambiente 
FROM `tabDueno Fiscal` 
WHERE name = 'Lorena';
