import frappe

def run():
    cols = frappe.db.sql(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema=DATABASE() AND table_name='tabItem' "
        "ORDER BY column_name",
        as_list=True
    )
    names = [c[0] for c in cols]
    print("Columnas relevantes en tabItem:")
    for n in names:
        if any(k in n.lower() for k in ['company', 'group', 'uom', 'warehouse']):
            print(" ", n)
    
    print("\nColumnas en tabStock Ledger Entry:")
    cols2 = frappe.db.sql(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema=DATABASE() AND table_name='tabStock Ledger Entry' "
        "ORDER BY column_name",
        as_list=True
    )
    names2 = [c[0] for c in cols2]
    for n in names2:
        if any(k in n.lower() for k in ['warehouse', 'actual', 'qty', 'company']):
            print(" ", n)
