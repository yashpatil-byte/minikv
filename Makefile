# MiniKV Makefile - Easy Docker & Development Commands

.PHONY: help build run example test benchmark clean stop logs shell

# Default target
help:
	@echo "MiniKV - Available Commands:"
	@echo ""
	@echo "  make build       - Build Docker image"
	@echo "  make run         - Run MiniKV CLI (interactive)"
	@echo "  make example     - Run example.py"
	@echo "  make test        - Run all tests"
	@echo "  make benchmark   - Run benchmarks"
	@echo "  make logs        - Show container logs"
	@echo "  make shell       - Get shell inside container"
	@echo "  make clean       - Remove containers and volumes"
	@echo "  make stop        - Stop all containers"
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

