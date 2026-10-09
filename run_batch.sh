#!/bin/bash
BC=$(docker ps -q --filter "name=backend-vvekd3jmyymltrmfoi8vdbdu" | head -1)

docker cp /tmp/run_batch_agosto.py $BC:/tmp/

docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && bench --site salsamentariamultiespecial.duckdns.org console << EOF
import sys
sys.path.insert(0, "/tmp")
import run_batch_agosto
run_batch_agosto.run()
EOF'
