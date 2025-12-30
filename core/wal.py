"""
Write-Ahead Logging (WAL) for crash recovery and durability.
Records all write operations before they're applied to ensure data consistency.
"""

import json
import os
import threading
from datetime import datetime
from enum import Enum
from typing import Any, Optional, List, Dict
from dataclasses import dataclass, asdict


class WALOperation(Enum):
    """Types of operations that can be logged."""
    SET = "SET"
    DELETE = "DELETE"
    CLEAR = "CLEAR"


@dataclass
class WALEntry:
    """Represents a single entry in the write-ahead log."""
    timestamp: str
    operation: str
    key: Optional[str]
    value: Optional[Any]
    
    def to_json(self) -> str:
        """Serialize the entry to JSON."""
        return json.dumps(asdict(self))
    
    @staticmethod
    def from_json(json_str: str) -> 'WALEntry':
        """Deserialize an entry from JSON."""
        data = json.loads(json_str)
        return WALEntry(**data)


class WAL:
    """
    Write-Ahead Logger that records operations before they're applied.
    Enables crash recovery by replaying logged operations.
    """
    
    def __init__(self, log_file: str = "minikv.wal"):
        """
        Initialize the WAL with a log file.
        
        Args:
            log_file: Path to the write-ahead log file
        """
        self.log_file = log_file
        self._lock = threading.Lock()
        self._file_handle = None
        self._enabled = True
        
    def enable(self):
        """Enable WAL logging."""
        self._enabled = True
    
    def disable(self):
        """Disable WAL logging (useful for bulk operations)."""
        self._enabled = False
    
    def open(self):
        """Open the WAL file for appending."""
        if self._file_handle is None:
            self._file_handle = open(self.log_file, 'a', encoding='utf-8')
    
    def close(self):
        """Close the WAL file."""
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None
    
    def log_set(self, key: str, value: Any):
        """
        Log a SET operation.
        
        Args:
            key: The key being set
            value: The value being set
        """
        if not self._enabled:
            return
        
        entry = WALEntry(
            timestamp=datetime.utcnow().isoformat(),
            operation=WALOperation.SET.value,
            key=key,
            value=value
        )
        self._write_entry(entry)
    
    def log_delete(self, key: str):
        """
        Log a DELETE operation.
        
        Args:
            key: The key being deleted
        """
        if not self._enabled:
            return
        
        entry = WALEntry(
            timestamp=datetime.utcnow().isoformat(),
            operation=WALOperation.DELETE.value,
            key=key,
            value=None
        )
        self._write_entry(entry)
    
    def log_clear(self):
        """Log a CLEAR operation (removes all keys)."""
        if not self._enabled:
            return
        
        entry = WALEntry(
            timestamp=datetime.utcnow().isoformat(),
            operation=WALOperation.CLEAR.value,
            key=None,
            value=None
        )
        self._write_entry(entry)
    
    def _write_entry(self, entry: WALEntry):
        """
        Write an entry to the WAL file.
        
        Args:
            entry: The WAL entry to write
        """
        with self._lock:
            self.open()
            self._file_handle.write(entry.to_json() + '\n')
            self._file_handle.flush()  # Ensure it's written to disk
            os.fsync(self._file_handle.fileno())  # Force OS to write to disk
    
    def replay(self) -> List[WALEntry]:
        """
        Read and return all entries from the WAL file.
        Used for crash recovery.
        
        Returns:
            List of WAL entries in order
        """
        if not os.path.exists(self.log_file):
            return []
        
        entries = []
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = WALEntry.from_json(line)
                        entries.append(entry)
                    except json.JSONDecodeError:
                        # Skip corrupted entries
                        continue
        
        return entries
    
    def truncate(self):
        """Clear the WAL file (usually after successful persistence)."""
        with self._lock:
            self.close()
            if os.path.exists(self.log_file):
                os.remove(self.log_file)
    
    def checkpoint(self) -> int:
        """
        Force a checkpoint (flush to disk).
        
        Returns:
            Number of entries in the WAL
        """
        with self._lock:
            if self._file_handle:
                self._file_handle.flush()
                os.fsync(self._file_handle.fileno())
        
        return self.get_entry_count()
    
    def get_entry_count(self) -> int:
        """Return the number of entries in the WAL."""
        if not os.path.exists(self.log_file):
            return 0
        
        count = 0
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for _ in f:
                count += 1
        return count

