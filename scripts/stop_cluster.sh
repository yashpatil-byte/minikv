#!/bin/bash
# Stop the MiniKV cluster
# Usage: ./scripts/stop_cluster.sh

set -e

echo "========================================================================"
echo "  MiniKV v2.0 - Stopping Cluster"
echo "========================================================================"
echo ""

# Function to stop a process
stop_process() {
    local pid_file=$1
    local name=$2
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "Stopping $name (PID: $pid)..."
            kill "$pid" 2>/dev/null || true
            sleep 1
            
            # Force kill if still running
            if ps -p "$pid" > /dev/null 2>&1; then
                echo "  Force stopping $name..."
                kill -9 "$pid" 2>/dev/null || true
            fi
        else
            echo "$name (PID: $pid) not running"
        fi
        rm -f "$pid_file"
    else
        echo "$name PID file not found"
    fi
}

# Stop Gateway
stop_process ".minikv_gateway.pid" "Gateway"

# Stop Nodes
stop_process ".minikv_node1.pid" "Node 1"
stop_process ".minikv_node2.pid" "Node 2"
stop_process ".minikv_node3.pid" "Node 3"

echo ""
echo "========================================================================"
echo "  Cluster Stopped"
echo "========================================================================"

