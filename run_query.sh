#!/bin/bash
BC=$(docker ps -q --filter "name=backend-vvekd3jmyymltrmfoi8vdbdu" | head -1)
docker cp /tmp/query_logs.py $BC:/tmp/
docker exec $BC bash -lc 'cd /home/frappe/frappe-bench && bench --site salsamentariamultiespecial.duckdns.org console << EOF
import sys
sys.path.insert(0, "/tmp")
import query_logs
query_logs.run()
EOF'
