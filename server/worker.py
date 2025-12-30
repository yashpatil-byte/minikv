"""
Worker thread logic for processing client requests concurrently.
Each worker handles operations on the key-value store.
"""

import threading
import queue
from typing import Any, Dict, Optional, Callable
from enum import Enum
import traceback


class OperationType(Enum):
    """Types of operations supported by workers."""
    GET = "GET"
    SET = "SET"
    DELETE = "DELETE"
    EXISTS = "EXISTS"
    KEYS = "KEYS"
    VALUES = "VALUES"
    ITEMS = "ITEMS"
    CLEAR = "CLEAR"
    SIZE = "SIZE"
    UPDATE = "UPDATE"
    CHECKPOINT = "CHECKPOINT"
    SHUTDOWN = "SHUTDOWN"


class WorkerRequest:
    """Represents a request to be processed by a worker."""
    
    def __init__(
        self,
        operation: OperationType,
        key: Optional[str] = None,
        value: Optional[Any] = None,
        data: Optional[Dict[str, Any]] = None,
        callback: Optional[Callable] = None
    ):
        """
        Initialize a worker request.
        
        Args:
            operation: The operation type to perform
            key: Optional key for operations that need it
            value: Optional value for SET operations
            data: Optional data dict for UPDATE operations
            callback: Optional callback function to handle the result
        """
        self.operation = operation
        self.key = key
        self.value = value
        self.data = data
        self.callback = callback
        self.result = None
        self.error = None
        self.event = threading.Event()


class Worker:
    """
    Worker thread that processes requests from a queue.
    """
    
    def __init__(
        self,
        worker_id: int,
        request_queue: queue.Queue,
        store: Any  # KeyValueStore instance
    ):
        """
        Initialize a worker thread.
        
        Args:
            worker_id: Unique identifier for this worker
            request_queue: Queue to receive requests from
            store: The KeyValueStore instance to operate on
        """
        self.worker_id = worker_id
        self.request_queue = request_queue
        self.store = store
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self.requests_processed = 0
    
    def start(self):
        """Start the worker thread."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(
            target=self._run,
            name=f"Worker-{self.worker_id}",
            daemon=True
        )
        self.thread.start()
    
    def stop(self):
        """Stop the worker thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5.0)
    
    def _run(self):
        """Main worker loop that processes requests."""
        while self.running:
            try:
                # Get request with timeout to allow checking running flag
                request = self.request_queue.get(timeout=0.1)
                
                # Process the request
                self._process_request(request)
                self.requests_processed += 1
                
                # Mark task as done
                self.request_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                # Log error but keep worker running
                print(f"Worker {self.worker_id} error: {e}")
                traceback.print_exc()
    
    def _process_request(self, request: WorkerRequest):
        """
        Process a single request.
        
        Args:
            request: The request to process
        """
        try:
            # Handle shutdown specially
            if request.operation == OperationType.SHUTDOWN:
                self.running = False
                request.result = True
                request.event.set()
                return
            
            # Execute the operation
            if request.operation == OperationType.GET:
                request.result = self.store.get(request.key)
            
            elif request.operation == OperationType.SET:
                self.store.set(request.key, request.value)
                request.result = True
            
            elif request.operation == OperationType.DELETE:
                request.result = self.store.delete(request.key)
            
            elif request.operation == OperationType.EXISTS:
                request.result = self.store.exists(request.key)
            
            elif request.operation == OperationType.KEYS:
                request.result = self.store.keys()
            
            elif request.operation == OperationType.VALUES:
                request.result = self.store.values()
            
            elif request.operation == OperationType.ITEMS:
                request.result = self.store.items()
            
            elif request.operation == OperationType.CLEAR:
                self.store.clear()
                request.result = True
            
            elif request.operation == OperationType.SIZE:
                request.result = self.store.size()
            
            elif request.operation == OperationType.UPDATE:
                self.store.update(request.data)
                request.result = True
            
            elif request.operation == OperationType.CHECKPOINT:
                request.result = self.store.checkpoint()
            
            else:
                request.error = f"Unknown operation: {request.operation}"
        
        except Exception as e:
            request.error = str(e)
            request.result = None
        
        finally:
            # Signal completion
            request.event.set()
            
            # Call callback if provided
            if request.callback:
                try:
                    request.callback(request)
                except Exception as e:
                    print(f"Callback error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get worker statistics.
        
        Returns:
            Dictionary with worker stats
        """
        return {
            'worker_id': self.worker_id,
            'running': self.running,
            'requests_processed': self.requests_processed,
            'thread_alive': self.thread.is_alive() if self.thread else False
        }

