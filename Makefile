# MiniKV Makefile - Easy Docker & Development Commands

.PHONY: help build run example test benchmark clean stop logs shell
.PHONY: cluster cluster-start cluster-stop cluster-test cluster-bench cluster-docker

# Default target
help:
	@echo "╔════════════════════════════════════════════════════════════╗"
	@echo "║          MiniKV - Available Commands                       ║"
	@echo "╠════════════════════════════════════════════════════════════╣"
	@echo "║  SINGLE-NODE (v1.0)                                        ║"
	@echo "║  make build       - Build Docker image                     ║"
	@echo "║  make run         - Run MiniKV CLI (interactive)           ║"
	@echo "║  make example     - Run example.py                         ║"
	@echo "║  make test        - Run all tests                          ║"
	@echo "║  make benchmark   - Run benchmarks                         ║"
	@echo "║                                                            ║"
	@echo "║  DISTRIBUTED CLUSTER (v2.0) ⭐ NEW!                        ║"
	@echo "║  make cluster-start    - Start 3-node cluster + gateway    ║"
	@echo "║  make cluster-stop     - Stop cluster                      ║"
	@echo "║  make cluster-test     - Test cluster                      ║"
	@echo "║  make cluster-bench    - Benchmark cluster (250K+ ops/sec) ║"
	@echo "║  make cluster-docker   - Start cluster in Docker           ║"
	@echo "║                                                            ║"
	@echo "║  UTILITIES                                                 ║"
	@echo "║  make logs        - Show container logs                    ║"
	@echo "║  make shell       - Get shell inside container             ║"
	@echo "║  make clean       - Remove containers and volumes          ║"
	@echo "║  make stop        - Stop all containers                    ║"
	@echo "╚════════════════════════════════════════════════════════════╝"
	@echo ""

# Build Docker image
build:
	@echo "Building MiniKV Docker image..."
	docker compose build
	@echo "✅ Build complete!"

# Run interactive CLI
run:
	@echo "Starting MiniKV CLI..."
	docker compose run --rm minikv-cli

# Run example
example:
	@echo "Running MiniKV example..."
	docker compose --profile example run --rm minikv-example

# Run tests
test:
	@echo "Running MiniKV tests..."
	docker compose --profile test run --rm minikv-tests

# Run benchmarks
benchmark:
	@echo "Running MiniKV benchmarks..."
	docker compose --profile benchmark run --rm minikv-benchmark

# Show logs
logs:
	docker compose logs -f

# Get shell access
shell:
	docker compose run --rm minikv-cli /bin/bash

# Clean up
clean:
	@echo "Cleaning up containers and volumes..."
	docker compose down -v
	@echo "✅ Cleanup complete!"

# Stop containers
stop:
	docker compose stop

# Development: Run locally (no Docker)
dev-run:
	python3 -m client.cli

dev-example:
	python3 example.py

dev-test:
	python3 -m tests.test_concurrency

dev-benchmark:
	python3 -m benchmarks.benchmark

# ============================================================================
# DISTRIBUTED CLUSTER COMMANDS (v2.0)
# ============================================================================

# Start 3-node cluster (local processes)
cluster-start:
	@echo "╔════════════════════════════════════════════════════════════╗"
	@echo "║  Starting MiniKV v2.0 - 3-Node Distributed Cluster        ║"
	@echo "╚════════════════════════════════════════════════════════════╝"
	@./scripts/start_cluster.sh

# Stop cluster
cluster-stop:
	@echo "Stopping cluster..."
	@./scripts/stop_cluster.sh

# Test cluster
cluster-test:
	@echo "╔════════════════════════════════════════════════════════════╗"
	@echo "║  Testing Distributed Cluster                               ║"
	@echo "╚════════════════════════════════════════════════════════════╝"
	@./scripts/test_cluster.sh

# Benchmark cluster
cluster-bench:
	@echo "╔════════════════════════════════════════════════════════════╗"
	@echo "║  Benchmarking Distributed Cluster                          ║"
	@echo "║  Target: 250,000+ ops/sec                                  ║"
	@echo "╚════════════════════════════════════════════════════════════╝"
	python3 -m benchmarks.benchmark_cluster --operations 100000 --concurrency 100

# Quick cluster benchmark
cluster-bench-quick:
	@echo "Running quick benchmark (10K ops)..."
	python3 -m benchmarks.benchmark_cluster --operations 10000 --concurrency 50

# Start cluster in Docker
cluster-docker:
	@echo "╔════════════════════════════════════════════════════════════╗"
	@echo "║  Starting Distributed Cluster in Docker                   ║"
	@echo "╚════════════════════════════════════════════════════════════╝"
	docker compose -f docker-compose-cluster.yml up -d
	@echo ""
	@echo "Waiting for cluster to initialize (30 seconds)..."
	@sleep 30
	@echo ""
	@echo "Initializing cluster (registering peers)..."
	docker compose -f docker-compose-cluster.yml --profile init up cluster-init
	@echo ""
	@echo "✅ Cluster ready!"
	@echo "   Gateway:    http://localhost:8000"
	@echo "   Node 1:     http://localhost:8001"
	@echo "   Node 2:     http://localhost:8002"
	@echo "   Node 3:     http://localhost:8003"
	@echo ""
	@echo "Test it:  curl http://localhost:8000/cluster/status | jq"
	@echo "Stop it:  make cluster-docker-stop"

# Stop Docker cluster
cluster-docker-stop:
	@echo "Stopping Docker cluster..."
	docker compose -f docker-compose-cluster.yml down

# Benchmark Docker cluster
cluster-docker-bench:
	@echo "Running benchmark in Docker..."
	docker compose -f docker-compose-cluster.yml --profile benchmark up benchmark

# Show cluster status
cluster-status:
	@echo "Cluster Status:"
	@curl -s http://localhost:8000/cluster/status | python3 -m json.tool || echo "❌ Cluster not running"

# Run distributed tests
cluster-test-unit:
	@echo "Running distributed unit tests..."
	python3 -m pytest tests/test_distributed.py -v

# All-in-one: Start + Test + Benchmark
cluster-demo:
	@echo "╔════════════════════════════════════════════════════════════╗"
	@echo "║  MiniKV v2.0 - Complete Demo                               ║"
	@echo "╚════════════════════════════════════════════════════════════╝"
	@$(MAKE) cluster-start
	@echo ""
	@echo "Waiting for cluster to stabilize (15 seconds)..."
	@sleep 15
	@echo ""
	@$(MAKE) cluster-test
	@echo ""
	@$(MAKE) cluster-bench-quick
	@echo ""
	@echo "╔════════════════════════════════════════════════════════════╗"
	@echo "║  Demo Complete!                                            ║"
	@echo "║  Cluster is still running. Stop with: make cluster-stop    ║"
	@echo "╚════════════════════════════════════════════════════════════╝"

