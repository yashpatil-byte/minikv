"""
Consistent hashing implementation for key distribution across nodes.
Uses virtual nodes for better load balancing.

WHY CONSISTENT HASHING?
- Better than simple modulo (key % num_nodes) because:
  1. Adding/removing nodes only affects ~1/N of keys (minimal reshuffling)
  2. Virtual nodes ensure even distribution despite physical node variations
  3. Supports dynamic cluster membership without full rebalancing
"""

import hashlib
from typing import List, Dict, Optional
from bisect import bisect_right


class ConsistentHashRing:
    def __init__(self, nodes: List[int], virtual_nodes: int = 150):
        """
        Initialize consistent hash ring.
        
        Args:
            nodes: List of node IDs (e.g., [1, 2, 3])
            virtual_nodes: Number of virtual nodes per physical node
                          (150 provides good balance: ~33% per node for 3 nodes)
        
        Example:
            ring = ConsistentHashRing([1, 2, 3], virtual_nodes=150)
            node = ring.get_node("user:123")  # Returns which node owns this key
        """
        self.virtual_nodes = virtual_nodes
        self.ring: Dict[int, int] = {}  # {hash_value: node_id}
        self.sorted_keys: List[int] = []
        
        for node_id in nodes:
            self.add_node(node_id)
    
    def _hash(self, key: str) -> int:
        """
        Generate hash value for a key (0 to 2^32-1).
        Uses MD5 for consistent distribution across the ring.
        
        Args:
            key: String to hash
            
        Returns:
            Integer hash value
        """
        return int(hashlib.md5(key.encode()).hexdigest(), 16)
    
    def add_node(self, node_id: int):
        """
        Add a node to the ring with its virtual nodes.
        
        Args:
            node_id: ID of the physical node to add
        """
        for i in range(self.virtual_nodes):
            # Create virtual node key: "node_id:virtual_index"
            virtual_key = f"{node_id}:{i}"
            hash_value = self._hash(virtual_key)
            self.ring[hash_value] = node_id
        
        # Keep ring sorted for efficient lookups
        self.sorted_keys = sorted(self.ring.keys())
    
    def remove_node(self, node_id: int):
        """
        Remove a node from the ring (for node failure handling).
        
        Args:
            node_id: ID of the physical node to remove
        """
        for i in range(self.virtual_nodes):
            virtual_key = f"{node_id}:{i}"
            hash_value = self._hash(virtual_key)
            if hash_value in self.ring:
                del self.ring[hash_value]
        
        self.sorted_keys = sorted(self.ring.keys())
    
    def get_node(self, key: str) -> int:
        """
        Get the primary node responsible for a key.
        
        Args:
            key: The key to look up
            
        Returns:
            Node ID that owns this key
            
        Raises:
            ValueError: If no nodes are in the ring
        """
        if not self.ring:
            raise ValueError("No nodes in ring")
        
        hash_value = self._hash(key)
        
        # Find first node with hash >= key hash (clockwise on ring)
        idx = bisect_right(self.sorted_keys, hash_value)
        
        # Wrap around if we're past the last key
        if idx == len(self.sorted_keys):
            idx = 0
        
        return self.ring[self.sorted_keys[idx]]
    
    def get_nodes_for_replication(self, key: str, n: int = 2) -> List[int]:
        """
        Get N distinct physical nodes for replication (primary + replicas).
        
        This is critical for fault tolerance: we replicate each key to N nodes,
        so if primary fails, we can read from replicas.
        
        Args:
            key: The key to replicate
            n: Number of replicas (including primary). Default=2 for N=2 replication
            
        Returns:
            List of node IDs [primary, replica1, replica2, ...]
            
        Example:
            nodes = ring.get_nodes_for_replication("user:123", n=2)
            # Returns [2, 3] meaning node 2 is primary, node 3 is backup
        """
        if not self.ring:
            return []
        
        hash_value = self._hash(key)
        idx = bisect_right(self.sorted_keys, hash_value)
        
        nodes = []
        seen_nodes = set()
        
        # Walk clockwise around ring to find N unique physical nodes
        for i in range(len(self.sorted_keys)):
            pos = (idx + i) % len(self.sorted_keys)
            node_id = self.ring[self.sorted_keys[pos]]
            
            if node_id not in seen_nodes:
                nodes.append(node_id)
                seen_nodes.add(node_id)
            
            if len(nodes) == n:
                break
        
        return nodes
    
    def get_key_distribution(self, sample_keys: List[str]) -> Dict[int, int]:
        """
        Analyze key distribution across nodes (for testing/validation).
        
        Args:
            sample_keys: List of keys to test
            
        Returns:
            Dict of {node_id: key_count}
        """
        distribution: Dict[int, int] = {}
        
        for key in sample_keys:
            try:
                node = self.get_node(key)
                distribution[node] = distribution.get(node, 0) + 1
            except ValueError:
                pass
        
        return distribution


# Test the hash ring
if __name__ == "__main__":
    ring = ConsistentHashRing([1, 2, 3])
    
    # Test key distribution
    keys = [f"key{i}" for i in range(1000)]
    distribution = ring.get_key_distribution(keys)
    
    print("Key distribution across 3 nodes (1000 keys):")
    print("=" * 50)
    for node_id in sorted(distribution.keys()):
        count = distribution[node_id]
        percentage = (count / len(keys)) * 100
        print(f"  Node {node_id}: {count:4d} keys ({percentage:.1f}%)")
    
    print("\nReplication test:")
    print("=" * 50)
    test_key = "user:123"
    primary_node = ring.get_node(test_key)
    replica_nodes = ring.get_nodes_for_replication(test_key, n=2)
    print(f"  Key: {test_key}")
    print(f"  Primary node: {primary_node}")
    print(f"  Replication nodes (N=2): {replica_nodes}")
    
    print("\nNode removal test:")
    print("=" * 50)
    print(f"  Before removal - {test_key} maps to: {ring.get_node(test_key)}")
    ring.remove_node(primary_node)
    print(f"  After removing node {primary_node} - {test_key} maps to: {ring.get_node(test_key)}")

