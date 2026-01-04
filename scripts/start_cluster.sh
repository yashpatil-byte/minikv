#!/bin/bash
# Start a 3-node MiniKV cluster
# Usage: ./scripts/start_cluster.sh

set -e

echo "========================================================================"
echo "  MiniKV v2.0 - Starting 3-Node Distributed Cluster"
echo "========================================================================"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 not found"
    exit 1
fi

# Clean up old data files
echo "Cleaning up old data files..."
rm -f node_*.db node_*.wal 2>/dev/null || true

# Start Node 1
echo "Starting Node 1 on port 8001..."
python3 -m distributed.node_server 1 8001 > node1.log 2>&1 &
NODE1_PID=$!
echo "  PID: $NODE1_PID"

# Start Node 2
echo "Starting Node 2 on port 8002..."
python3 -m distributed.node_server 2 8002 > node2.log 2>&1 &
NODE2_PID=$!
echo "  PID: $NODE2_PID"

# Start Node 3
echo "Starting Node 3 on port 8003..."
python3 -m distributed.node_server 3 8003 > node3.log 2>&1 &
NODE3_PID=$!
echo "  PID: $NODE3_PID"

# Wait for nodes to start
echo ""
echo "Waiting for nodes to start (5 seconds)..."
sleep 5

# Initialize cluster (register peers)
echo ""
echo "Initializing cluster..."
python3 -m distributed.cluster_manager

# Start Gateway
echo ""
echo "Starting API Gateway on port 8000..."
python3 -m distributed.gateway > gateway.log 2>&1 &
GATEWAY_PID=$!
echo "  PID: $GATEWAY_PID"

# Save PIDs
echo "$NODE1_PID" > .minikv_node1.pid
echo "$NODE2_PID" > .minikv_node2.pid
echo "$NODE3_PID" > .minikv_node3.pid
echo "$GATEWAY_PID" > .minikv_gateway.pid

echo ""
echo "========================================================================"
echo "  Cluster Started Successfully!"
echo "========================================================================"
echo ""
echo "Nodes:"
echo "  - Node 1: http://localhost:8001  (PID: $NODE1_PID)"
echo "  - Node 2: http://localhost:8002  (PID: $NODE2_PID)"
echo "  - Node 3: http://localhost:8003  (PID: $NODE3_PID)"
echo ""
echo "Gateway:"
echo "  - API Gateway: http://localhost:8000  (PID: $GATEWAY_PID)"
echo ""
echo "Logs:"
echo "  - Node 1: node1.log"
echo "  - Node 2: node2.log"
echo "  - Node 3: node3.log"
echo "  - Gateway: gateway.log"
echo ""
echo "Commands:"
echo "  - Check status:  curl http://localhost:8000/cluster/status"
echo "  - Set key:       curl -X POST http://localhost:8000/set/mykey -H 'Content-Type: application/json' -d '{\"value\":\"myvalue\"}'"
echo "  - Get key:       curl http://localhost:8000/get/mykey"
echo "  - Stop cluster:  ./scripts/stop_cluster.sh"
echo ""
echo "========================================================================"

