"""
Request router that dispatches incoming requests to a thread pool.
Manages worker threads and provides a high-level API for the KV store.
"""

import queue
import threading
from typing import Any, Dict, Optional, List
from .worker import Worker, WorkerRequest, OperationType
from core.store import KeyValueStore
from core.persistence import SQLitePersistence


class Router:
    """
    Request router that manages a pool of worker threads.
    Provides a thread-safe API for concurrent access to the KV store.
    """
    
    def __init__(
        self,
        num_workers: int = 4,
        queue_size: int = 100,
        enable_persistence: bool = True,
        enable_wal: bool = True,
        db_path: str = "minikv.db",
        wal_path: str = "minikv.wal"
    ):
        """
        Initialize the router with a worker pool.
        
        Args:
            num_workers: Number of worker threads to create
            queue_size: Maximum size of the request queue
            enable_persistence: Whether to enable SQLite persistence
            enable_wal: Whether to enable write-ahead logging
            db_path: Path to the database file
            wal_path: Path to the WAL file
        """
        self.num_workers = num_workers
        
        # Create the key-value store
        persistence = SQLitePersistence(db_path) if enable_persistence else None
        self.store = KeyValueStore(
            persistence=persistence,
            enable_wal=enable_wal,
            wal_file=wal_path
        )
        
        # Create request queue
        self.request_queue = queue.Queue(maxsize=queue_size)
        
        # Create worker pool
        self.workers: List[Worker] = []
        for i in range(num_workers):
            worker = Worker(i, self.request_queue, self.store)
            self.workers.append(worker)
        
        # Statistics
        self._lock = threading.Lock()
        self._total_requests = 0
        self._running = False
    
    def start(self):
        """Start all worker threads."""
        if self._running:
            return
        
        self._running = True
        for worker in self.workers:
            worker.start()
    
    def stop(self):
        """Stop all worker threads gracefully."""
        if not self._running:
            return
        
        self._running = False
        
        # Send shutdown signal to all workers
        for _ in self.workers:
            shutdown_request = WorkerRequest(operation=OperationType.SHUTDOWN)
            self.request_queue.put(shutdown_request)
        
        # Wait for all workers to stop
        for worker in self.workers:
            worker.stop()
        
        # Close the store
        self.store.close()
    
    def _submit_request(
        self,
        request: WorkerRequest,
        timeout: Optional[float] = None
    ) -> Any:
        """
        Submit a request to the worker pool and wait for result.
        
        Args:
            request: The request to submit
            timeout: Optional timeout in seconds
            
        Returns:
            The result of the operation
            
        Raises:
            RuntimeError: If the router is not running
            queue.Full: If the queue is full
            TimeoutError: If the operation times out
            Exception: If the operation fails
        """
        if not self._running:
            raise RuntimeError("Router is not running")
        
        with self._lock:
            self._total_requests += 1
        
        # Add request to queue
        self.request_queue.put(request, timeout=timeout or 5.0)
        
        # Wait for completion
        if not request.event.wait(timeout=timeout or 30.0):
            raise TimeoutError("Operation timed out")
        
        # Check for errors
        if request.error:
            raise Exception(request.error)
        
        return request.result
    
    # Public API methods
    
    def get(self, key: str, timeout: Optional[float] = None) -> Optional[Any]:
        """
        Get a value by key.
        
        Args:
            key: The key to retrieve
            timeout: Optional timeout in seconds
            
        Returns:
            The value if found, None otherwise
        """
        request = WorkerRequest(operation=OperationType.GET, key=key)
        return self._submit_request(request, timeout)
    
    def set(self, key: str, value: Any, timeout: Optional[float] = None) -> bool:
        """
        Set a key-value pair.
        
        Args:
            key: The key to set
            value: The value to set
            timeout: Optional timeout in seconds
            
        Returns:
            True on success
        """
        request = WorkerRequest(operation=OperationType.SET, key=key, value=value)
        return self._submit_request(request, timeout)
    
    def delete(self, key: str, timeout: Optional[float] = None) -> bool:
        """
        Delete a key-value pair.
        
        Args:
            key: The key to delete
            timeout: Optional timeout in seconds
            
        Returns:
            True if the key existed and was deleted
        """
        request = WorkerRequest(operation=OperationType.DELETE, key=key)
        return self._submit_request(request, timeout)
    
    def exists(self, key: str, timeout: Optional[float] = None) -> bool:
        """
        Check if a key exists.
        
        Args:
            key: The key to check
            timeout: Optional timeout in seconds
            
        Returns:
            True if the key exists
        """
        request = WorkerRequest(operation=OperationType.EXISTS, key=key)
        return self._submit_request(request, timeout)
    
    def keys(self, timeout: Optional[float] = None) -> List[str]:
        """
        Get all keys.
        
        Args:
            timeout: Optional timeout in seconds
            
        Returns:
            List of all keys
        """
        request = WorkerRequest(operation=OperationType.KEYS)
        return self._submit_request(request, timeout)
    
    def values(self, timeout: Optional[float] = None) -> List[Any]:
        """
        Get all values.
        
        Args:
            timeout: Optional timeout in seconds
            
        Returns:
            List of all values
        """
        request = WorkerRequest(operation=OperationType.VALUES)
        return self._submit_request(request, timeout)
    
    def items(self, timeout: Optional[float] = None) -> List[tuple]:
        """
        Get all key-value pairs.
        
        Args:
            timeout: Optional timeout in seconds
            
        Returns:
            List of (key, value) tuples
        """
        request = WorkerRequest(operation=OperationType.ITEMS)
        return self._submit_request(request, timeout)
    
    def clear(self, timeout: Optional[float] = None) -> bool:
        """
        Clear all key-value pairs.
        
        Args:
            timeout: Optional timeout in seconds
            
        Returns:
            True on success
        """
        request = WorkerRequest(operation=OperationType.CLEAR)
        return self._submit_request(request, timeout)
    
    def size(self, timeout: Optional[float] = None) -> int:
        """
        Get the number of key-value pairs.
        
        Args:
            timeout: Optional timeout in seconds
            
        Returns:
            Number of entries
        """
        request = WorkerRequest(operation=OperationType.SIZE)
        return self._submit_request(request, timeout)
    
    def update(self, data: Dict[str, Any], timeout: Optional[float] = None) -> bool:
        """
        Batch update multiple key-value pairs.
        
        Args:
            data: Dictionary of key-value pairs to set
            timeout: Optional timeout in seconds
            
        Returns:
            True on success
        """
        request = WorkerRequest(operation=OperationType.UPDATE, data=data)
        return self._submit_request(request, timeout)
    
    def checkpoint(self, timeout: Optional[float] = None) -> Dict[str, int]:
        """
        Force a checkpoint.
        
        Args:
            timeout: Optional timeout in seconds
            
        Returns:
            Checkpoint statistics
        """
        request = WorkerRequest(operation=OperationType.CHECKPOINT)
        return self._submit_request(request, timeout)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get router and worker statistics.
        
        Returns:
            Dictionary with statistics
        """
        with self._lock:
            stats = {
                'running': self._running,
                'total_requests': self._total_requests,
                'num_workers': self.num_workers,
                'queue_size': self.request_queue.qsize(),
                'store_size': self.store.size(),
                'workers': [worker.get_stats() for worker in self.workers]
            }
        
        return stats
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False

