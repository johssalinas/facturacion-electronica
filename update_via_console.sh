#!/bin/bash
BC=$(docker ps -q --filter "name=backend-vvekd3jmyymltrmfoi8vdbdu" | head -1)

# Copiar script al contenedor
docker cp /tmp/update_numbering.py $BC:/tmp/

# Ejecutar con bench console
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && bench --site salsamentariamultiespecial.duckdns.org console << EOF
import sys
sys.path.insert(0, "/tmp")
import update_numbering
update_numbering.run()
EOF'
