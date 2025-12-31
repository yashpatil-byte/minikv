# MiniKV — Concurrent In-Memory Key-Value Store

A high-performance, concurrent in-memory key-value store implemented in Python. MiniKV supports basic CRUD operations with "thread-safe access" designed to efficiently handle multiple client requests concurrently. The system implements fine-grained locking, write-ahead logging (WAL), and persistence using SQLite or PostgreSQL, providing durability, crash recovery, and consistency guarantees.

## Features

- **High Performance**: In-memory storage with optimized concurrent access
- **Thread-Safe**: Fine-grained locking mechanism for maximum concurrency
- **Durability**: Write-Ahead Logging (WAL) ensures no data loss
- **Persistence**: Optional SQLite or PostgreSQL backend for durability
- **Crash Recovery**: Automatic recovery from WAL after crashes
- **Concurrent Processing**: Thread pool with worker threads for parallel request handling
- **Benchmarking Framework**: Built-in performance testing and metrics

## Architecture

```
Client (CLI/API)
       ↓
Concurrent Requests
       ↓
Request Router (Thread Pool / Workers)
       ↓
   ┌──────────────┬──────────────────┐
   ↓              ↓                  ↓
WAL Logger  →  In-Memory    →  Persistence
(Append)       KV Store      (SQLite/PostgreSQL)
```

### Components

- **Client (CLI/API)**: Users interact with the key-value store via a CLI or API client
- **Request Router**: Dispatches incoming requests to a thread pool for concurrent processing
- **In-Memory KV Store**: Uses a dictionary with fine-grained locking for thread-safe operations
- **WAL Logger**: Records write operations before applying to persistence, ensuring recovery
- **Persistence** (SQLite/PostgreSQL): Optionally persists data for durability

## Installation

MiniKV requires Python 3.8 or higher.

### Option 1: Using Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/minikv.git
cd minikv

# Build the Docker image
make build
# OR
docker-compose build

# Run MiniKV CLI
make run
# OR
docker-compose run --rm minikv-cli

# Run example
make example

# Run tests
make test

# Run benchmarks
make benchmark
```

### Option 2: Local Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/minikv.git
cd minikv

# Install dependencies (optional, only if using PostgreSQL)
pip install -r requirements.txt

# For PostgreSQL support
pip install psycopg2-binary
```

## Quick Start

### Interactive CLI

Start the interactive CLI:

```bash
python -m client.cli
```

This opens an interactive shell:

```
==============================================================
  MiniKV - Concurrent In-Memory Key-Value Store
==============================================================
Type 'help' for available commands or 'exit' to quit.

minikv> SET user:1 {"name": "John", "age": 30}
OK
minikv> GET user:1
{
  "name": "John",
  "age": 30
}
minikv> KEYS
1) user:1
minikv> EXIT
```

### CLI Options

```bash
# Specify number of worker threads
python -m client.cli --workers 8

# Disable persistence
python -m client.cli --no-persistence

# Disable write-ahead logging
python -m client.cli --no-wal

# Custom database and WAL file paths
python -m client.cli --db /path/to/db.sqlite --wal /path/to/wal.log

# Execute a single command
python -m client.cli --command "SET key1 value1"
```

## CLI Commands

| Command | Description | Example |
|---------|-------------|---------|
| `SET <key> <value>` | Set a key-value pair | `SET user:1 "John"` |
| `GET <key>` | Get value for a key | `GET user:1` |
| `DELETE <key>` | Delete a key | `DELETE user:1` |
| `EXISTS <key>` | Check if key exists | `EXISTS user:1` |
| `KEYS` | List all keys | `KEYS` |
| `VALUES` | List all values | `VALUES` |
| `ITEMS` | List all key-value pairs | `ITEMS` |
| `SIZE` | Get number of entries | `SIZE` |
| `CLEAR` | Clear all data | `CLEAR` |
| `UPDATE <json>` | Batch update keys | `UPDATE {"k1": "v1", "k2": 42}` |
| `CHECKPOINT` | Force a checkpoint | `CHECKPOINT` |
| `STATS` | Display system stats | `STATS` |
| `HELP` | Display help | `HELP` |
| `EXIT` / `QUIT` | Exit the CLI | `EXIT` |

### Value Types

MiniKV supports JSON values. You can store strings, numbers, objects, and arrays:

```bash
# String
SET name "John Doe"

# Number
SET age 30

# Object
SET user {"name": "John", "email": "john@example.com", "age": 30}

# Array
SET tags ["python", "database", "concurrent"]
```

## Programmatic Usage

### Basic Usage

```python
from server.router import Router

# Create and start router
router = Router(num_workers=4, enable_persistence=True, enable_wal=True)
router.start()

try:
    # Set values
    router.set("user:1", {"name": "John", "age": 30})
    router.set("user:2", {"name": "Jane", "age": 25})
    
    # Get values
    user = router.get("user:1")
    print(user)  # {'name': 'John', 'age': 30}
    
    # Check existence
    exists = router.exists("user:1")
    print(exists)  # True
    
    # Delete
    deleted = router.delete("user:2")
    print(deleted)  # True
    
    # Batch update
    router.update({
        "key1": "value1",
        "key2": 42,
        "key3": [1, 2, 3]
    })
    
    # Get all keys
    keys = router.keys()
    print(keys)
    
    # Get stats
    stats = router.get_stats()
    print(stats)

finally:
    router.stop()
```

### Context Manager

```python
from server.router import Router

with Router(num_workers=4) as router:
    router.set("key", "value")
    value = router.get("key")
    print(value)
# Router is automatically stopped
```

### Direct Store Usage

```python
from core.store import KeyValueStore
from core.persistence import SQLitePersistence

# Create store with persistence
persistence = SQLitePersistence("data.db")
store = KeyValueStore(persistence=persistence, enable_wal=True)

# Use store
store.set("key1", "value1")
value = store.get("key1")

# Close when done
store.close()
```

## Running Tests

### Concurrency Tests

```bash
python -m tests.test_concurrency
```

Tests include:
- Fine-grained locking
- Concurrent reads and writes
- Race condition prevention
- Worker pool utilization

### Recovery Tests

```bash
python -m tests.test_recovery
```

Tests include:
- WAL logging and replay
- Crash recovery scenarios
- Persistence layer operations
- Checkpoint and recovery

### Run All Tests

```bash
python -m unittest discover tests
```

## Running Benchmarks

```bash
# Basic benchmark
python -m benchmarks.benchmark

# Custom parameters
python -m benchmarks.benchmark --workers 8 --operations 50000

# With persistence enabled
python -m benchmarks.benchmark --persistence --wal

# Help
python -m benchmarks.benchmark --help
```

Example output:

```
======================================================================
  MiniKV Benchmark Suite
======================================================================

Running Write Benchmark (10000 operations)...
  Completed in 2.45s
  Throughput: 4081.63 ops/sec

Running Read Benchmark (10000 operations)...
  Completed in 1.87s
  Throughput: 5347.59 ops/sec

Running Mixed Benchmark (80% reads) (10000 operations)...
  Completed in 2.12s
  Throughput: 4716.98 ops/sec

======================================================================
  Summary
======================================================================

Write Benchmark:
  Total Operations: 10000
  Mean Latency:     0.245 ms
  Median Latency:   0.232 ms
  P95 Latency:      0.412 ms
  P99 Latency:      0.589 ms

...
```

## Configuration

### Worker Threads

Adjust the number of worker threads based on your workload:

```python
router = Router(num_workers=8)  # 8 worker threads
```

### Persistence Options

**SQLite** (default):
```python
router = Router(
    enable_persistence=True,
    db_path="minikv.db"
)
```

**PostgreSQL**:
```python
from core.persistence import PostgreSQLPersistence
from core.store import KeyValueStore

persistence = PostgreSQLPersistence(
    "host=localhost dbname=minikv user=postgres password=pass"
)
store = KeyValueStore(persistence=persistence)
```

**No Persistence** (in-memory only):
```python
router = Router(enable_persistence=False)
```

### Write-Ahead Logging

Enable/disable WAL:

```python
router = Router(
    enable_wal=True,
    wal_path="minikv.wal"
)
```

## Docker Deployment

MiniKV is fully containerized with Docker support for reproducible deployments.

### Quick Start with Docker

```bash
# Build the image
docker-compose build

# Run the CLI
docker-compose run --rm minikv-cli

# Run example
docker-compose --profile example run --rm minikv-example

# Run tests
docker-compose --profile test run --rm minikv-tests

# Run benchmarks
docker-compose --profile benchmark run --rm minikv-benchmark
```

### Using Makefile (Easier)

```bash
# Build
make build

# Run CLI
make run

# Run example
make example

# Run tests
make test

# Run benchmarks
make benchmark

# Clean up
make clean
```

### Docker Features

- **Multi-stage build**: Optimized image size
- **Volume persistence**: Data survives container restarts
- **Health checks**: Automatic container health monitoring
- **Isolated environment**: Consistent behavior across systems
- **Easy CI/CD integration**: Ready for automated testing

### Docker Image Details

```bash
# Build custom image
docker build -t minikv:custom .

# Run with custom settings
docker run -it \
  -e MINIKV_WORKERS=8 \
  -v $(pwd)/data:/app/data \
  minikv:custom

# Get shell access
docker-compose run --rm minikv-cli /bin/bash
```

## Performance Characteristics

- **Throughput**: 4,000-10,000 ops/sec (depending on operation type and concurrency)
- **Latency**: 
  - Mean: 0.2-0.5 ms
  - P95: 0.4-0.8 ms
  - P99: 0.5-1.5 ms
- **Scalability**: Linear scaling up to CPU core count with worker threads

## Project Structure

```
minikv/
├── core/
│   ├── store.py          # In-memory KV store
│   ├── lock_manager.py   # Fine-grained locking logic
│   ├── wal.py            # Write-ahead logging
│   └── persistence.py    # SQLite/PostgreSQL integration
├── server/
│   ├── worker.py         # Thread worker logic
│   └── router.py         # Router dispatching
├── client/
│   └── cli.py            # CLI interface
├── benchmarks/
│   └── benchmark.py      # Performance benchmarking
├── tests/
│   ├── test_concurrency.py   # Concurrency tests
│   └── test_recovery.py      # Recovery tests
├── docs/
│   └── architecture.py   # Architecture documentation
├── requirements.txt      # Dependencies
└── README.md            # This file
```

## Design Decisions

### Fine-Grained Locking

Instead of a global lock, MiniKV uses per-key locks to maximize concurrency. Multiple threads can operate on different keys simultaneously without blocking each other.

### Write-Ahead Logging

All write operations are logged before being applied. This ensures:
- **Durability**: Operations survive crashes
- **Consistency**: Operations are applied in order during recovery
- **Atomicity**: Either all operations in the log are applied or none

### Thread Pool Architecture

The router dispatches requests to a pool of worker threads, allowing:
- **Concurrent Processing**: Multiple requests handled simultaneously
- **Load Balancing**: Work distributed across workers
- **Isolation**: Worker failures don't affect other workers

## Limitations

- **Not Distributed**: Single-node only (no clustering/replication)
- **No Transactions**: No multi-key atomic operations
- **No TTL/Expiration**: Keys don't automatically expire
- **No Pub/Sub**: No publish/subscribe functionality
- **Memory Bound**: All data must fit in memory

## Future Enhancements

- [ ] TTL/expiration support
- [ ] Multi-key transactions
- [ ] Pub/Sub messaging
- [ ] Distributed clustering
- [ ] Replication
- [ ] HTTP/REST API
- [ ] Client libraries (Python, Node.js, etc.)
- [ ] LRU eviction policy
- [ ] Compression support

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Write tests for your changes
4. Ensure all tests pass
5. Submit a pull request

## Support

For issues, questions, or contributions, please open an issue on GitHub.

---

**MiniKV** - Built with Python 🐍

