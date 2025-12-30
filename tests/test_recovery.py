"""
Recovery tests for MiniKV.
Tests crash recovery, WAL replay, and persistence.
"""

import unittest
import os
import tempfile
import shutil
from core.store import KeyValueStore
from core.wal import WAL, WALEntry
from core.persistence import SQLitePersistence


class TestWAL(unittest.TestCase):
    """Test the Write-Ahead Log."""
    
    def setUp(self):
        """Set up a temporary WAL file."""
        self.temp_dir = tempfile.mkdtemp()
        self.wal_file = os.path.join(self.temp_dir, "test.wal")
        self.wal = WAL(self.wal_file)
        self.wal.open()
    
    def tearDown(self):
        """Clean up temporary files."""
        self.wal.close()
        shutil.rmtree(self.temp_dir)
    
    def test_wal_logging(self):
        """Test basic WAL logging."""
        # Log operations
        self.wal.log_set("key1", "value1")
        self.wal.log_set("key2", 42)
        self.wal.log_delete("key1")
        
        # Read back
        entries = self.wal.replay()
        self.assertEqual(len(entries), 3)
        
        self.assertEqual(entries[0].operation, "SET")
        self.assertEqual(entries[0].key, "key1")
        self.assertEqual(entries[0].value, "value1")
        
        self.assertEqual(entries[1].operation, "SET")
        self.assertEqual(entries[1].key, "key2")
        self.assertEqual(entries[1].value, 42)
        
        self.assertEqual(entries[2].operation, "DELETE")
        self.assertEqual(entries[2].key, "key1")
    
    def test_wal_checkpoint(self):
        """Test WAL checkpoint."""
        self.wal.log_set("key1", "value1")
        self.wal.log_set("key2", "value2")
        
        count = self.wal.checkpoint()
        self.assertEqual(count, 2)
    
    def test_wal_truncate(self):
        """Test WAL truncation."""
        self.wal.log_set("key1", "value1")
        self.wal.log_set("key2", "value2")
        
        self.assertEqual(self.wal.get_entry_count(), 2)
        
        self.wal.truncate()
        
        self.assertEqual(self.wal.get_entry_count(), 0)
    
    def test_wal_disable_enable(self):
        """Test disabling and enabling WAL."""
        self.wal.log_set("key1", "value1")
        
        self.wal.disable()
        self.wal.log_set("key2", "value2")  # Should not be logged
        
        self.wal.enable()
        self.wal.log_set("key3", "value3")
        
        entries = self.wal.replay()
        # Only key1 and key3 should be logged
        self.assertEqual(len(entries), 2)


class TestPersistence(unittest.TestCase):
    """Test the persistence layer."""
    
    def setUp(self):
        """Set up a temporary database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_file = os.path.join(self.temp_dir, "test.db")
        self.persistence = SQLitePersistence(self.db_file)
    
    def tearDown(self):
        """Clean up temporary files."""
        self.persistence.disconnect()
        shutil.rmtree(self.temp_dir)
    
    def test_save_load(self):
        """Test saving and loading data."""
        self.persistence.save("key1", "value1")
        self.persistence.save("key2", 42)
        self.persistence.save("key3", {"nested": "object"})
        
        self.assertEqual(self.persistence.load("key1"), "value1")
        self.assertEqual(self.persistence.load("key2"), 42)
        self.assertEqual(self.persistence.load("key3"), {"nested": "object"})
    
    def test_delete(self):
        """Test deleting data."""
        self.persistence.save("key1", "value1")
        self.assertTrue(self.persistence.exists("key1"))
        
        self.persistence.delete("key1")
        self.assertFalse(self.persistence.exists("key1"))
        self.assertIsNone(self.persistence.load("key1"))
    
    def test_load_all(self):
        """Test loading all data."""
        data = {
            "key1": "value1",
            "key2": 42,
            "key3": [1, 2, 3]
        }
        
        for key, value in data.items():
            self.persistence.save(key, value)
        
        loaded = self.persistence.load_all()
        self.assertEqual(loaded, data)
    
    def test_clear(self):
        """Test clearing all data."""
        self.persistence.save("key1", "value1")
        self.persistence.save("key2", "value2")
        
        self.assertEqual(self.persistence.get_size(), 2)
        
        self.persistence.clear()
        
        self.assertEqual(self.persistence.get_size(), 0)
    
    def test_update_existing(self):
        """Test updating existing keys."""
        self.persistence.save("key1", "old_value")
        self.persistence.save("key1", "new_value")
        
        self.assertEqual(self.persistence.load("key1"), "new_value")
        self.assertEqual(self.persistence.get_size(), 1)


class TestRecovery(unittest.TestCase):
    """Test crash recovery scenarios."""
    
    def setUp(self):
        """Set up temporary files."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_file = os.path.join(self.temp_dir, "test.db")
        self.wal_file = os.path.join(self.temp_dir, "test.wal")
    
    def tearDown(self):
        """Clean up temporary files."""
        shutil.rmtree(self.temp_dir)
    
    def test_recovery_from_wal(self):
        """Test recovering data from WAL after a crash."""
        # Create store and write data
        persistence = SQLitePersistence(self.db_file)
        store = KeyValueStore(
            persistence=persistence,
            enable_wal=True,
            wal_file=self.wal_file
        )
        
        store.set("key1", "value1")
        store.set("key2", 42)
        store.set("key3", [1, 2, 3])
        
        # Simulate crash (don't call close, just destroy the object)
        del store
        
        # Create new store - should recover from WAL
        persistence = SQLitePersistence(self.db_file)
        store = KeyValueStore(
            persistence=persistence,
            enable_wal=True,
            wal_file=self.wal_file
        )
        
        # Verify data was recovered
        self.assertEqual(store.get("key1"), "value1")
        self.assertEqual(store.get("key2"), 42)
        self.assertEqual(store.get("key3"), [1, 2, 3])
        self.assertEqual(store.size(), 3)
        
        store.close()
    
    def test_recovery_with_deletes(self):
        """Test recovery with delete operations."""
        # Create store
        persistence = SQLitePersistence(self.db_file)
        store = KeyValueStore(
            persistence=persistence,
            enable_wal=True,
            wal_file=self.wal_file
        )
        
        store.set("key1", "value1")
        store.set("key2", "value2")
        store.delete("key1")
        store.set("key3", "value3")
        
        # Simulate crash
        del store
        
        # Recover
        persistence = SQLitePersistence(self.db_file)
        store = KeyValueStore(
            persistence=persistence,
            enable_wal=True,
            wal_file=self.wal_file
        )
        
        # key1 should be deleted
        self.assertIsNone(store.get("key1"))
        self.assertEqual(store.get("key2"), "value2")
        self.assertEqual(store.get("key3"), "value3")
        self.assertEqual(store.size(), 2)
        
        store.close()
    
    def test_recovery_with_clear(self):
        """Test recovery with clear operation."""
        persistence = SQLitePersistence(self.db_file)
        store = KeyValueStore(
            persistence=persistence,
            enable_wal=True,
            wal_file=self.wal_file
        )
        
        store.set("key1", "value1")
        store.set("key2", "value2")
        store.clear()
        store.set("key3", "value3")
        
        # Simulate crash
        del store
        
        # Recover
        persistence = SQLitePersistence(self.db_file)
        store = KeyValueStore(
            persistence=persistence,
            enable_wal=True,
            wal_file=self.wal_file
        )
        
        # Only key3 should remain
        self.assertEqual(store.size(), 1)
        self.assertEqual(store.get("key3"), "value3")
        
        store.close()
    
    def test_persistence_without_wal(self):
        """Test loading from persistence when WAL is disabled."""
        # Create store with persistence but no WAL
        persistence = SQLitePersistence(self.db_file)
        store = KeyValueStore(
            persistence=persistence,
            enable_wal=False
        )
        
        store.set("key1", "value1")
        store.set("key2", "value2")
        store.close()
        
        # Create new store - should load from persistence
        persistence = SQLitePersistence(self.db_file)
        store = KeyValueStore(
            persistence=persistence,
            enable_wal=False
        )
        
        self.assertEqual(store.get("key1"), "value1")
        self.assertEqual(store.get("key2"), "value2")
        self.assertEqual(store.size(), 2)
        
        store.close()
    
    def test_checkpoint_and_recovery(self):
        """Test checkpoint followed by recovery."""
        persistence = SQLitePersistence(self.db_file)
        store = KeyValueStore(
            persistence=persistence,
            enable_wal=True,
            wal_file=self.wal_file
        )
        
        # Write data
        for i in range(100):
            store.set(f"key_{i}", i)
        
        # Checkpoint
        stats = store.checkpoint()
        self.assertEqual(stats['persisted_keys'], 100)
        
        # Close properly
        store.close()
        
        # Reopen - should load from persistence
        persistence = SQLitePersistence(self.db_file)
        store = KeyValueStore(
            persistence=persistence,
            enable_wal=True,
            wal_file=self.wal_file
        )
        
        # Verify all data
        self.assertEqual(store.size(), 100)
        for i in range(100):
            self.assertEqual(store.get(f"key_{i}"), i)
        
        store.close()


def run_tests():
    """Run all recovery tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestWAL))
    suite.addTests(loader.loadTestsFromTestCase(TestPersistence))
    suite.addTests(loader.loadTestsFromTestCase(TestRecovery))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)

