# Inventario reader

Lee y audita hojas de cálculo de inventario con `openpyxl` usando `uv`.

```powershell
uv run --project tools/inventario_reader python tools/inventario_reader/read_inventory.py "inventario 27-09-2026.xlsx"
```

La auditoría REST requiere `ERP_USER` y `ERP_PASSWORD` en el entorno. La auditoría SQL requiere además `ERP_DB_PASSWORD`; no guarda credenciales en archivos:

```powershell
$env:ERP_USER = "..."
$env:ERP_PASSWORD = "..."
uv run --project tools/inventario_reader python tools/inventario_reader/audit_erp.py "inventario 27-09-2026.xlsx"

$env:ERP_DB_PASSWORD = "..."
uv run --project tools/inventario_reader python tools/inventario_reader/sql_audit.py "inventario 27-09-2026.xlsx"
uv run --project tools/inventario_reader python tools/inventario_reader/sql_audit.py "inventario 27-09-2026.xlsx" invoices
```
