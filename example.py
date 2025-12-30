#!/usr/bin/env python3
"""
Example usage of MiniKV.
Demonstrates basic operations and features.
"""

from server.router import Router
import time


def main():
    print("=" * 60)
    print("  MiniKV Example")
    print("=" * 60)
    print()
    
    # Create router with 4 workers
    print("1. Creating router with 4 worker threads...")
    router = Router(
        num_workers=4,
        enable_persistence=True,
        enable_wal=True,
        db_path="example.db",
        wal_path="example.wal"
    )
    router.start()
    print("   ✓ Router started\n")
    
    try:
        # Basic operations
        print("2. Setting key-value pairs...")
        router.set("user:1", {"name": "Alice", "email": "alice@example.com", "age": 30})
        router.set("user:2", {"name": "Bob", "email": "bob@example.com", "age": 25})
        router.set("user:3", {"name": "Charlie", "email": "charlie@example.com", "age": 35})
        router.set("counter", 0)
        router.set("message", "Hello, MiniKV!")
        print("   ✓ 5 keys set\n")
        
        # Retrieving values
        print("3. Retrieving values...")
        user1 = router.get("user:1")
        print(f"   user:1 = {user1}")
        message = router.get("message")
        print(f"   message = {message}\n")
        
        # Checking existence
        print("4. Checking key existence...")
        exists = router.exists("user:1")
        print(f"   user:1 exists: {exists}")
        exists = router.exists("user:999")
        print(f"   user:999 exists: {exists}\n")
        
        # Batch update
        print("5. Batch updating keys...")
        router.update({
            "product:1": {"name": "Laptop", "price": 999.99},
            "product:2": {"name": "Mouse", "price": 29.99},
            "product:3": {"name": "Keyboard", "price": 79.99},
        })
        print("   ✓ 3 products added\n")
        
        # List operations
        print("6. Listing all keys...")
        keys = router.keys()
        print(f"   Total keys: {len(keys)}")
        print(f"   Keys: {', '.join(keys[:5])}{'...' if len(keys) > 5 else ''}\n")
        
        # Get size
        print("7. Getting store size...")
        size = router.size()
        print(f"   Store size: {size} entries\n")
        
        # Delete operation
        print("8. Deleting a key...")
        deleted = router.delete("user:3")
        print(f"   user:3 deleted: {deleted}")
        print(f"   New size: {router.size()}\n")
        
        # Checkpoint
        print("9. Creating checkpoint...")
        stats = router.checkpoint()
        print(f"   Checkpoint stats: {stats}\n")
        
        # System statistics
        print("10. System statistics...")
        stats = router.get_stats()
        print(f"   Running: {stats['running']}")
        print(f"   Total requests: {stats['total_requests']}")
        print(f"   Workers: {stats['num_workers']}")
        print(f"   Store size: {stats['store_size']}")
        print(f"   Queue size: {stats['queue_size']}\n")
        
        # Performance test
        print("11. Performance test (1000 operations)...")
        start = time.time()
        for i in range(1000):
            router.set(f"perf_test:{i}", i)
        elapsed = time.time() - start
        print(f"   1000 writes in {elapsed:.3f}s ({1000/elapsed:.2f} ops/sec)\n")
        
        # Clean up test data
        print("12. Cleaning up test data...")
        for i in range(1000):
            router.delete(f"perf_test:{i}")
        print("   ✓ Test data cleaned\n")
        
        print("=" * 60)
        print("  Example completed successfully!")
        print("=" * 60)
        print()
        print("To explore more:")
        print("  - Run the CLI: python -m client.cli")
        print("  - Run tests: python -m tests.test_concurrency")
        print("  - Run benchmarks: python -m benchmarks.benchmark")
        print()
    
    finally:
        # Stop the router
        router.stop()
        print("Router stopped.")


if __name__ == "__main__":
    main()

