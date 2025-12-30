"""
Fine-grained locking manager for thread-safe key-value operations.
Provides per-key locks to minimize contention and maximize concurrency.
"""

import threading
from typing import Dict
from contextlib import contextmanager


class LockManager:
    """
    Manages fine-grained locks for individual keys in the KV store.
    Creates locks on-demand and provides context managers for safe locking.
    """
    
    def __init__(self):
        """Initialize the lock manager with a dictionary of locks."""
        self._locks: Dict[str, threading.RLock] = {}
        self._locks_lock = threading.Lock()  # Protects the locks dictionary itself
    
    def _get_lock(self, key: str) -> threading.RLock:
        """
        Get or create a lock for the given key.
        
        Args:
            key: The key to get a lock for
            
        Returns:
            A reentrant lock for the specified key
        """
        if key not in self._locks:
            with self._locks_lock:
                # Double-check locking pattern
                if key not in self._locks:
                    self._locks[key] = threading.RLock()
        return self._locks[key]
    
    @contextmanager
    def lock(self, key: str):
        """
        Context manager for acquiring a lock on a specific key.
        
        Usage:
            with lock_manager.lock('mykey'):
                # Critical section - operate on 'mykey'
                pass
        
        Args:
            key: The key to lock
        """
        lock = self._get_lock(key)
        lock.acquire()
        try:
            yield
        finally:
            lock.release()
    
    @contextmanager
    def lock_multiple(self, *keys: str):
        """
        Context manager for acquiring locks on multiple keys.
        Acquires locks in sorted order to prevent deadlocks.
        
        Args:
            *keys: Variable number of keys to lock
        """
        # Sort keys to ensure consistent lock ordering (prevents deadlocks)
        sorted_keys = sorted(set(keys))
        locks = [self._get_lock(key) for key in sorted_keys]
        
        # Acquire all locks
        for lock in locks:
            lock.acquire()
        
        try:
            yield
        finally:
            # Release in reverse order
            for lock in reversed(locks):
                lock.release()
    
    def cleanup_unused_locks(self):
        """
        Remove locks for keys that are no longer being used.
        Call this periodically to prevent memory leaks.
        """
        with self._locks_lock:
            unused_keys = [
                key for key, lock in self._locks.items()
                if not lock._is_owned()  # Check if lock is currently held
            ]
            for key in unused_keys:
                del self._locks[key]
    
    def get_lock_count(self) -> int:
        """Return the current number of locks being managed."""
        return len(self._locks)

