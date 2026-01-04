# MiniKV v2.0 - Quick Start Guide

Get a 3-node distributed cluster running in **5 minutes**!

---

## Prerequisites

- Python 3.8+
- `pip install -r requirements.txt`
- Ports 8000-8003 available

---

## Method 1: Shell Scripts (Easiest)

### Start Cluster

```bash
# Clean start
./scripts/start_cluster.sh
```

This will:
1. Start Node 1 on port 8001
2. Start Node 2 on port 8002
3. Start Node 3 on port 8003
4. Register peers (nodes know about each other)
5. Start Gateway on port 8000

**Wait 30 seconds for full initialization.**

### Test Cluster

```bash
# Run basic tests
./scripts/test_cluster.sh
```

### Check Status

```bash
# Cluster health
curl http://localhost:8000/cluster/status | jq

# Expected output:
# {
#   "cluster_size": 3,
#   "healthy_nodes": 3,
#   "unhealthy_nodes": 0,
#   "nodes": {
#     "node_1": { "status": "healthy", "store_size": 0 },
#     "node_2": { "status": "healthy", "store_size": 0 },
#     "node_3": { "status": "healthy", "store_size": 0 }
#   }
# }
```

### Use the Cluster

```bash
# Set a key
curl -X POST http://localhost:8000/set/user:123 \
  -H 'Content-Type: application/json' \
  -d '{"value": {"name": "Alice", "age": 30}}'

# Get a key
curl http://localhost:8000/get/user:123 | jq

# Check key distribution
curl http://localhost:8000/cluster/distribution | jq

# Gateway stats
curl http://localhost:8000/stats | jq
```

### Run Benchmarks

```bash
# Full benchmark (100K operations)
python -m benchmarks.benchmark_cluster

# Quick test (10K operations)
python -m benchmarks.benchmark_cluster --operations 10000
```

### Stop Cluster

```bash
./scripts/stop_cluster.sh
```

---

## Method 2: Docker (Most Reliable)

### Start Cluster

```bash
# Start all services (3 nodes + gateway)
docker-compose -f docker-compose-cluster.yml up -d

# Wait for services to be ready
sleep 30

# Initialize cluster (register peers)
docker-compose -f docker-compose-cluster.yml --profile init up cluster-init

# Check logs
docker-compose -f docker-compose-cluster.yml logs -f
```

### Test Cluster

```bash
# Cluster status
curl http://localhost:8000/cluster/status | jq

# Set/Get operations
curl -X POST http://localhost:8000/set/test \
  -H 'Content-Type: application/json' \
  -d '{"value": "hello"}'

curl http://localhost:8000/get/test | jq
```

### Run Benchmark

```bash
docker-compose -f docker-compose-cluster.yml --profile benchmark up benchmark
```

### Stop Cluster

```bash
docker-compose -f docker-compose-cluster.yml down

# Clean volumes
docker-compose -f docker-compose-cluster.yml down -v
```

---

## Method 3: Manual (For Learning)

### Terminal 1: Node 1

```bash
python -m distributed.node_server 1 8001
```

### Terminal 2: Node 2

```bash
python -m distributed.node_server 2 8002
```

### Terminal 3: Node 3

```bash
python -m distributed.node_server 3 8003
```

### Terminal 4: Initialize Cluster

```bash
# Wait 5 seconds for nodes to start
sleep 5

# Register peers
python -m distributed.cluster_manager
```

### Terminal 5: Gateway

```bash
python -m distributed.gateway
```

### Terminal 6: Test

```bash
# Wait 10 seconds for everything to be ready
sleep 10

# Test
curl http://localhost:8000/cluster/status | jq
curl -X POST http://localhost:8000/set/test -d '{"value": "works"}' -H 'Content-Type: application/json'
curl http://localhost:8000/get/test | jq
```

---

## Common Operations

### Write Data

```bash
# Simple value
curl -X POST http://localhost:8000/set/username \
  -H 'Content-Type: application/json' \
  -d '{"value": "alice"}'

# JSON object
curl -X POST http://localhost:8000/set/user:1 \
  -H 'Content-Type: application/json' \
  -d '{"value": {"name": "Alice", "email": "alice@example.com"}}'

# Array
curl -X POST http://localhost:8000/set/tags \
  -H 'Content-Type: application/json' \
  -d '{"value": ["python", "distributed", "kv"]}'
```

### Read Data

```bash
curl http://localhost:8000/get/username | jq
curl http://localhost:8000/get/user:1 | jq
curl http://localhost:8000/get/tags | jq
```

### Delete Data

```bash
curl -X DELETE http://localhost:8000/delete/username | jq
```

### Check Cluster Health

```bash
# Full cluster status
curl http://localhost:8000/cluster/status | jq

# Key distribution (how keys are spread across nodes)
curl http://localhost:8000/cluster/distribution | jq

# Gateway statistics
curl http://localhost:8000/stats | jq
```

### Check Individual Nodes

```bash
# Node 1 health
curl http://localhost:8001/health | jq

# Node 2 statistics
curl http://localhost:8002/stats | jq

# Node 3 keys
curl http://localhost:8003/keys | jq
```

---

## Testing Fault Tolerance

### Simulate Node Failure

```bash
# Kill Node 1
kill $(cat .minikv_node1.pid)

# Wait for health check (5 seconds)
sleep 5

# Cluster should still work (reads from replicas)
curl http://localhost:8000/cluster/status | jq

# Should show 2 healthy nodes
curl http://localhost:8000/get/test | jq  # Still works!
```

### Recover Node

```bash
# Restart Node 1
python -m distributed.node_server 1 8001 > node1.log 2>&1 &
echo $! > .minikv_node1.pid

# Wait for recovery
sleep 10

# Cluster should be healthy again
curl http://localhost:8000/cluster/status | jq
# Should show 3 healthy nodes
```

---

## Monitoring

### Prometheus Metrics

```bash
# Gateway metrics
curl http://localhost:8000/metrics

# Node 1 metrics
curl http://localhost:8001/metrics

# Parse specific metric
curl -s http://localhost:8000/metrics | grep minikv_requests_total
```

### Health Monitoring

```bash
# Watch cluster status (updates every 2 seconds)
watch -n 2 'curl -s http://localhost:8000/cluster/status | jq'

# Watch gateway stats
watch -n 2 'curl -s http://localhost:8000/stats | jq'
```

---

## Performance Testing

### Quick Test (1K operations)

```bash
python -m benchmarks.benchmark_cluster --operations 1000 --concurrency 50
```

### Medium Test (10K operations)

```bash
python -m benchmarks.benchmark_cluster --operations 10000 --concurrency 100
```

### Full Test (100K operations)

```bash
python -m benchmarks.benchmark_cluster --operations 100000 --concurrency 100
```

### Stress Test (1M operations)

```bash
python -m benchmarks.benchmark_cluster --operations 1000000 --concurrency 200
```

---

## Troubleshooting

### Cluster Won't Start

```bash
# Check if ports are in use
lsof -i :8000
lsof -i :8001
lsof -i :8002
lsof -i :8003

# Kill old processes
pkill -f "node_server"
pkill -f "gateway"

# Clean up
rm -f .minikv_*.pid
rm -f node_*.db node_*.wal node*.log gateway.log

# Try again
./scripts/start_cluster.sh
```

### Nodes Not Communicating

```bash
# Re-register peers
python -m distributed.cluster_manager

# Check logs
tail -f node1.log
tail -f node2.log
tail -f node3.log
tail -f gateway.log
```

### High Latency

```bash
# Check replication failures
curl http://localhost:8001/health | jq '.replication_failures'
curl http://localhost:8002/health | jq '.replication_failures'
curl http://localhost:8003/health | jq '.replication_failures'

# Check if all nodes are healthy
curl http://localhost:8000/cluster/status | jq '.healthy_nodes'
```

### Data Not Replicating

```bash
# Check anti-entropy logs
tail -f gateway.log | grep "Anti-Entropy"

# Force check: Write a key and verify on all nodes
curl -X POST http://localhost:8000/set/repl_test -d '{"value": "test"}' -H 'Content-Type: application/json'
sleep 2

# Check all nodes
curl http://localhost:8001/get/repl_test | jq
curl http://localhost:8002/get/repl_test | jq
curl http://localhost:8003/get/repl_test | jq
```

---

## Next Steps

1. **Read Full Docs**: `cat README_DISTRIBUTED.md`
2. **Run Benchmarks**: `python -m benchmarks.benchmark_cluster`
3. **Run Tests**: `python -m pytest tests/test_distributed.py -v`
4. **Explore Code**: Check `distributed/` directory
5. **Try Chaos**: Kill nodes and see recovery in action

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `./scripts/start_cluster.sh` | Start 3-node cluster + gateway |
| `./scripts/stop_cluster.sh` | Stop cluster |
| `./scripts/test_cluster.sh` | Run basic tests |
| `curl localhost:8000/cluster/status \| jq` | Check health |
| `curl -X POST localhost:8000/set/KEY -d '{"value":"VAL"}' -H 'Content-Type: application/json'` | Set key |
| `curl localhost:8000/get/KEY \| jq` | Get key |
| `python -m benchmarks.benchmark_cluster` | Run benchmark |
| `python -m pytest tests/test_distributed.py -v` | Run tests |

---

**Happy Distributed Computing! 🚀**

