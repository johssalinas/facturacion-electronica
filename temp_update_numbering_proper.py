import frappe

def run():
    frappe.db.set_value('Dueno Fiscal', 'Lorena', 'numbering_range_id', 6141)
    frappe.db.commit()
    doc = frappe.get_doc('Dueno Fiscal', 'Lorena')
    print(f"✓ numbering_range_id actualizado a: {doc.numbering_range_id}")
