"""
Core in-memory key-value store implementation.
Provides thread-safe CRUD operations with optional persistence and WAL.
"""

from typing import Any, Dict, Optional, List
import threading
from .lock_manager import LockManager
from .wal import WAL
from .persistence import PersistenceBackend, SQLitePersistence


class KeyValueStore:
    """
    High-performance concurrent in-memory key-value store.
    Supports CRUD operations, persistence, and crash recovery.
    """
    
    def __init__(
        self,
        persistence: Optional[PersistenceBackend] = None,
        enable_wal: bool = True,
        wal_file: str = "minikv.wal"
    ):
        """
        Initialize the key-value store.
        
        Args:
            persistence: Optional persistence backend (SQLite, PostgreSQL)
            enable_wal: Whether to enable write-ahead logging
            wal_file: Path to the WAL file
        """
        self._data: Dict[str, Any] = {}
        self._lock_manager = LockManager()
        self._global_lock = threading.RLock()  # For operations affecting all keys
        
        # WAL setup
        self._wal: Optional[WAL] = None
        if enable_wal:
            self._wal = WAL(wal_file)
            self._wal.open()
        
        # Persistence setup
        self._persistence = persistence
        
        # Recovery
        if self._wal and self._persistence:
            self._recover_from_wal()
        elif self._persistence:
            self._load_from_persistence()
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a key-value pair in the store.
        
        Args:
            key: The key to set
            value: The value to associate with the key
        """
        with self._lock_manager.lock(key):
            # Log to WAL first
            if self._wal:
                self._wal.log_set(key, value)
            
            # Update in-memory store
            self._data[key] = value
            
            # Persist to backend
            if self._persistence:
                self._persistence.save(key, value)
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get a value by key from the store.
        
        Args:
            key: The key to retrieve
            
        Returns:
            The value if found, None otherwise
        """
        with self._lock_manager.lock(key):
            return self._data.get(key)
    
    def delete(self, key: str) -> bool:
        """
        Delete a key-value pair from the store.
        
        Args:
            key: The key to delete
            
        Returns:
            True if the key existed and was deleted, False otherwise
        """
        with self._lock_manager.lock(key):
            if key not in self._data:
                return False
            
            # Log to WAL first
            if self._wal:
                self._wal.log_delete(key)
            
            # Remove from in-memory store
            del self._data[key]
            
            # Remove from persistence
            if self._persistence:
                self._persistence.delete(key)
            
            return True
    
    def exists(self, key: str) -> bool:
        """
        Check if a key exists in the store.
        
        Args:
            key: The key to check
            
        Returns:
            True if the key exists, False otherwise
        """
        with self._lock_manager.lock(key):
            return key in self._data
    
    def keys(self) -> List[str]:
        """
        Get all keys in the store.
        
        Returns:
            List of all keys
        """
        with self._global_lock:
            return list(self._data.keys())
    
    def values(self) -> List[Any]:
        """
        Get all values in the store.
        
        Returns:
            List of all values
        """
        with self._global_lock:
            return list(self._data.values())
    
    def items(self) -> List[tuple]:
        """
        Get all key-value pairs in the store.
        
        Returns:
            List of (key, value) tuples
        """
        with self._global_lock:
            return list(self._data.items())
    
    def clear(self) -> None:
        """Clear all key-value pairs from the store."""
        with self._global_lock:
            # Log to WAL first
            if self._wal:
                self._wal.log_clear()
            
            # Clear in-memory store
            self._data.clear()
            
            # Clear persistence
            if self._persistence:
                self._persistence.clear()
    
    def size(self) -> int:
        """
        Get the number of key-value pairs in the store.
        
        Returns:
            Number of entries
        """
        with self._global_lock:
            return len(self._data)
    
    def update(self, data: Dict[str, Any]) -> None:
        """
        Batch update multiple key-value pairs.
        
        Args:
            data: Dictionary of key-value pairs to set
        """
        # Disable WAL temporarily for bulk operations
        if self._wal:
            self._wal.disable()
        
        try:
            for key, value in data.items():
                self.set(key, value)
        finally:
            if self._wal:
                self._wal.enable()
                # Log a checkpoint after bulk operation
                self._wal.checkpoint()
    
    def _recover_from_wal(self) -> None:
        """Recover data from WAL after a crash."""
        if not self._wal:
            return
        
        entries = self._wal.replay()
        
        # Disable persistence and WAL during recovery
        temp_persistence = self._persistence
        self._persistence = None
        if self._wal:
            self._wal.disable()
        
        try:
            for entry in entries:
                if entry.operation == "SET":
                    self._data[entry.key] = entry.value
                elif entry.operation == "DELETE":
                    self._data.pop(entry.key, None)
                elif entry.operation == "CLEAR":
                    self._data.clear()
        finally:
            # Re-enable persistence and WAL
            self._persistence = temp_persistence
            if self._wal:
                self._wal.enable()
        
        # Persist recovered data
        if self._persistence:
            for key, value in self._data.items():
                self._persistence.save(key, value)
        
        # Truncate WAL after successful recovery
        if self._wal:
            self._wal.truncate()
    
    def _load_from_persistence(self) -> None:
        """Load data from persistence backend on startup."""
        if not self._persistence:
            return
        
        data = self._persistence.load_all()
        self._data.update(data)
    
    def checkpoint(self) -> Dict[str, int]:
        """
        Force a checkpoint (flush WAL and sync with persistence).
        
        Returns:
            Dictionary with checkpoint statistics
        """
        stats = {}
        
        if self._wal:
            stats['wal_entries'] = self._wal.checkpoint()
        
        if self._persistence:
            stats['persisted_keys'] = self._persistence.get_size()
        
        return stats
    
    def close(self) -> None:
        """Clean shutdown of the store."""
        # Checkpoint before closing
        self.checkpoint()
        
        # Close WAL
        if self._wal:
            self._wal.close()
        
        # Close persistence
        if self._persistence:
            self._persistence.disconnect()
    
    def __len__(self) -> int:
        """Return the number of key-value pairs."""
        return self.size()
    
    def __contains__(self, key: str) -> bool:
        """Check if a key exists using 'in' operator."""
        return self.exists(key)
    
    def __getitem__(self, key: str) -> Any:
        """Get a value using bracket notation."""
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value
    
    def __setitem__(self, key: str, value: Any) -> None:
        """Set a value using bracket notation."""
        self.set(key, value)
    
    def __delitem__(self, key: str) -> None:
        """Delete a key using del statement."""
        if not self.delete(key):
            raise KeyError(key)

