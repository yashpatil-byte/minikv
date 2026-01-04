"""
Prometheus metrics for distributed MiniKV monitoring.

Metrics exposed:
- Request count (by node, operation)
- Request latency (histograms)
- Store size (gauge)
- Replication failures
- Node health status
"""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
from fastapi import Response
from typing import Optional
import time


# Request metrics
request_count = Counter(
    'minikv_requests_total',
    'Total number of requests',
    ['node_id', 'operation']
)

request_latency = Histogram(
    'minikv_request_latency_seconds',
    'Request latency in seconds',
    ['node_id', 'operation'],
    buckets=(0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

# Store metrics
store_size = Gauge(
    'minikv_store_size',
    'Number of keys in store',
    ['node_id']
)

# Replication metrics
replication_failures = Counter(
    'minikv_replication_failures_total',
    'Total replication failures',
    ['node_id']
)

# Cluster metrics
cluster_healthy_nodes = Gauge(
    'minikv_cluster_healthy_nodes',
    'Number of healthy nodes in cluster'
)

cluster_total_nodes = Gauge(
    'minikv_cluster_total_nodes',
    'Total number of nodes in cluster'
)

# Gateway metrics
gateway_requests = Counter(
    'minikv_gateway_requests_total',
    'Total gateway requests',
    ['operation', 'status']
)

gateway_request_latency = Histogram(
    'minikv_gateway_request_latency_seconds',
    'Gateway request latency',
    ['operation'],
    buckets=(0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)


class MetricsTracker:
    """Helper class to track metrics with timing"""
    
    def __init__(self, node_id: Optional[int] = None):
        self.node_id = node_id
    
    def track_request(self, operation: str):
        """Context manager to track request metrics"""
        return RequestTimer(self.node_id, operation)
    
    def update_store_size(self, size: int):
        """Update store size gauge"""
        if self.node_id is not None:
            store_size.labels(node_id=self.node_id).set(size)
    
    def increment_replication_failure(self):
        """Increment replication failure counter"""
        if self.node_id is not None:
            replication_failures.labels(node_id=self.node_id).inc()


class RequestTimer:
    """Context manager for timing requests"""
    
    def __init__(self, node_id: Optional[int], operation: str):
        self.node_id = node_id
        self.operation = operation
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        
        if self.node_id is not None:
            request_count.labels(
                node_id=self.node_id,
                operation=self.operation
            ).inc()
            
            request_latency.labels(
                node_id=self.node_id,
                operation=self.operation
            ).observe(duration)
        
        return False


def add_metrics_endpoint(app, node_id: Optional[int] = None):
    """
    Add /metrics endpoint to FastAPI app for Prometheus scraping.
    
    Args:
        app: FastAPI application
        node_id: Optional node ID for node-specific metrics
    """
    
    @app.get("/metrics")
    def metrics():
        """Prometheus metrics endpoint"""
        return Response(
            content=generate_latest(REGISTRY),
            media_type="text/plain"
        )
    
    return app


# Example usage
if __name__ == "__main__":
    import random
    
    print("Simulating metrics collection...")
    print("=" * 60)
    
    # Simulate some operations
    tracker = MetricsTracker(node_id=1)
    
    for i in range(100):
        op = random.choice(['get', 'set', 'delete'])
        
        with tracker.track_request(op):
            # Simulate work
            time.sleep(random.uniform(0.001, 0.01))
        
        if random.random() < 0.1:
            tracker.increment_replication_failure()
    
    tracker.update_store_size(42)
    
    # Print metrics
    print("\nGenerated Prometheus metrics:")
    print("=" * 60)
    print(generate_latest(REGISTRY).decode('utf-8'))

