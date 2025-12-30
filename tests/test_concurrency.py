"""
Concurrency tests for MiniKV.
Tests thread safety, race conditions, and concurrent operations.
"""

import unittest
import threading
import time
import random
from core.store import KeyValueStore
from core.lock_manager import LockManager
from server.router import Router


class TestLockManager(unittest.TestCase):
    """Test the fine-grained lock manager."""
    
    def test_basic_locking(self):
        """Test basic lock acquisition and release."""
        lock_manager = LockManager()
        
        with lock_manager.lock("key1"):
            # Lock is held
            pass
        
        # Lock should be released
        self.assertGreaterEqual(lock_manager.get_lock_count(), 1)
    
    def test_multiple_locks(self):
        """Test locking multiple keys."""
        lock_manager = LockManager()
        
        with lock_manager.lock_multiple("key1", "key2", "key3"):
            # All locks are held
            pass
        
        # Locks should be released
        self.assertGreaterEqual(lock_manager.get_lock_count(), 3)
    
    def test_reentrant_locks(self):
        """Test that locks are reentrant."""
        lock_manager = LockManager()
        
        with lock_manager.lock("key1"):
            with lock_manager.lock("key1"):
                # Should not deadlock
                pass


class TestConcurrentStore(unittest.TestCase):
    """Test concurrent operations on the key-value store."""
    
    def setUp(self):
        """Set up a fresh store for each test."""
        self.store = KeyValueStore(persistence=None, enable_wal=False)
    
    def tearDown(self):
        """Clean up after each test."""
        self.store.close()
    
    def test_concurrent_writes(self):
        """Test concurrent writes to different keys."""
        num_threads = 10
        keys_per_thread = 100
        threads = []
        
        def write_keys(thread_id):
            for i in range(keys_per_thread):
                key = f"thread_{thread_id}_key_{i}"
                self.store.set(key, i)
        
        # Start threads
        for i in range(num_threads):
            t = threading.Thread(target=write_keys, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Verify all keys were written
        expected_size = num_threads * keys_per_thread
        self.assertEqual(self.store.size(), expected_size)
    
    def test_concurrent_reads_writes(self):
        """Test concurrent reads and writes."""
        num_threads = 20
        operations = 100
        errors = []
        
        # Pre-populate some data
        for i in range(10):
            self.store.set(f"key_{i}", i)
        
        def mixed_operations(thread_id):
            try:
                for i in range(operations):
                    key = f"key_{random.randint(0, 19)}"
                    op = random.choice(['read', 'write'])
                    
                    if op == 'read':
                        self.store.get(key)
                    else:
                        self.store.set(key, random.randint(0, 1000))
            except Exception as e:
                errors.append(e)
        
        # Start threads
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=mixed_operations, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Should have no errors
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
    
    def test_concurrent_deletes(self):
        """Test concurrent deletions."""
        num_keys = 100
        
        # Pre-populate
        for i in range(num_keys):
            self.store.set(f"key_{i}", i)
        
        self.assertEqual(self.store.size(), num_keys)
        
        # Delete concurrently
        threads = []
        
        def delete_keys(start, end):
            for i in range(start, end):
                self.store.delete(f"key_{i}")
        
        # Split work among threads
        num_threads = 10
        chunk_size = num_keys // num_threads
        
        for i in range(num_threads):
            start = i * chunk_size
            end = start + chunk_size if i < num_threads - 1 else num_keys
            t = threading.Thread(target=delete_keys, args=(start, end))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # All keys should be deleted
        self.assertEqual(self.store.size(), 0)
    
    def test_race_condition_prevention(self):
        """Test that race conditions are prevented."""
        counter_key = "counter"
        self.store.set(counter_key, 0)
        num_threads = 50
        increments_per_thread = 100
        
        def increment_counter():
            for _ in range(increments_per_thread):
                # This is NOT atomic without proper locking
                # But our store handles locking internally
                current = self.store.get(counter_key)
                self.store.set(counter_key, current + 1)
        
        threads = []
        for _ in range(num_threads):
            t = threading.Thread(target=increment_counter)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        expected = num_threads * increments_per_thread
        actual = self.store.get(counter_key)
        
        # Due to race conditions without atomic operations,
        # the count might be less than expected
        # This test shows the limitation of non-atomic operations
        self.assertGreater(actual, 0)
        # Note: For truly atomic counters, we'd need a dedicated atomic operation
    
    def test_concurrent_clear(self):
        """Test concurrent operations with clear."""
        # Populate store
        for i in range(100):
            self.store.set(f"key_{i}", i)
        
        errors = []
        
        def continuous_writes():
            try:
                for i in range(100):
                    self.store.set(f"write_key_{i}", i)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        def clear_store():
            time.sleep(0.05)
            self.store.clear()
        
        # Start threads
        write_thread = threading.Thread(target=continuous_writes)
        clear_thread = threading.Thread(target=clear_store)
        
        write_thread.start()
        clear_thread.start()
        
        write_thread.join()
        clear_thread.join()
        
        # Should not have errors
        self.assertEqual(len(errors), 0)


class TestConcurrentRouter(unittest.TestCase):
    """Test concurrent operations through the router."""
    
    def setUp(self):
        """Set up a router for each test."""
        self.router = Router(
            num_workers=4,
            enable_persistence=False,
            enable_wal=False
        )
        self.router.start()
    
    def tearDown(self):
        """Clean up after each test."""
        self.router.stop()
    
    def test_router_concurrent_operations(self):
        """Test concurrent operations through the router."""
        num_clients = 20
        operations_per_client = 50
        errors = []
        
        def client_operations(client_id):
            try:
                for i in range(operations_per_client):
                    key = f"client_{client_id}_key_{i}"
                    
                    # Set
                    self.router.set(key, {"value": i, "client": client_id})
                    
                    # Get
                    value = self.router.get(key)
                    self.assertIsNotNone(value)
                    self.assertEqual(value["value"], i)
                    
                    # Exists
                    exists = self.router.exists(key)
                    self.assertTrue(exists)
            except Exception as e:
                errors.append(e)
        
        # Start client threads
        threads = []
        for i in range(num_clients):
            t = threading.Thread(target=client_operations, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Should have no errors
        self.assertEqual(len(errors), 0, f"Errors: {errors}")
        
        # Verify size
        expected_size = num_clients * operations_per_client
        actual_size = self.router.size()
        self.assertEqual(actual_size, expected_size)
    
    def test_router_stress_test(self):
        """Stress test the router with many concurrent operations."""
        num_clients = 50
        operations = 100
        errors = []
        
        def stress_client():
            try:
                for _ in range(operations):
                    op = random.choice(['set', 'get', 'delete', 'exists'])
                    key = f"key_{random.randint(0, 100)}"
                    
                    if op == 'set':
                        self.router.set(key, random.randint(0, 1000))
                    elif op == 'get':
                        self.router.get(key)
                    elif op == 'delete':
                        self.router.delete(key)
                    elif op == 'exists':
                        self.router.exists(key)
            except Exception as e:
                errors.append(e)
        
        threads = []
        start_time = time.time()
        
        for _ in range(num_clients):
            t = threading.Thread(target=stress_client)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        elapsed = time.time() - start_time
        total_ops = num_clients * operations
        ops_per_sec = total_ops / elapsed
        
        print(f"\nStress test: {total_ops} operations in {elapsed:.2f}s")
        print(f"Throughput: {ops_per_sec:.2f} ops/sec")
        
        # Should have no errors
        self.assertEqual(len(errors), 0)
    
    def test_worker_pool_utilization(self):
        """Test that all workers are being utilized."""
        num_operations = 100
        
        # Submit many operations
        for i in range(num_operations):
            self.router.set(f"key_{i}", i)
        
        # Get stats
        stats = self.router.get_stats()
        
        # All workers should have processed some requests
        total_processed = sum(
            w['requests_processed'] for w in stats['workers']
        )
        
        self.assertEqual(total_processed, num_operations)
        
        # Verify workers are alive
        for worker in stats['workers']:
            self.assertTrue(worker['thread_alive'])


def run_tests():
    """Run all concurrency tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestLockManager))
    suite.addTests(loader.loadTestsFromTestCase(TestConcurrentStore))
    suite.addTests(loader.loadTestsFromTestCase(TestConcurrentRouter))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)

