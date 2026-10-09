#!/bin/bash
BC=$(docker ps -q --filter "name=backend-vvekd3jmyymltrmfoi8vdbdu" | head -1)
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && bench --site salsamentariamultiespecial.duckdns.org execute "frappe.db.set_value(\"Dueno Fiscal\", \"Lorena\", \"numbering_range_id\", 6141); frappe.db.commit()"'
echo "✓ numbering_range_id actualizado a 6141"
