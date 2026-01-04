"""
Distributed MiniKV components for 3-node cluster.

This package contains:
- consistent_hash: Consistent hashing with virtual nodes
- node_server: Individual node HTTP API server
- gateway: API gateway for request routing
- cluster_manager: Peer registration and cluster membership
- merkle_tree: Anti-entropy data reconciliation
- metrics: Prometheus monitoring
"""

__version__ = "2.0.0"

__all__ = [
    "ConsistentHashRing",
    "NodeServer",
    "Gateway",
    "ClusterManager",
    "MerkleTree",
    "AntiEntropy"
]

