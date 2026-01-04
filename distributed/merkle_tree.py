"""
Merkle tree for efficient data comparison between nodes.

WHY MERKLE TREES?
- Comparing entire datasets key-by-key is expensive (O(n) network calls)
- Merkle trees allow quick comparison: if root hashes match, data is identical
- If roots differ, can efficiently find diverging subtrees (O(log n))
- Used by: Cassandra, DynamoDB, Bitcoin, Git

HOW IT WORKS:
1. Hash each key-value pair (leaf nodes)
2. Build tree bottom-up by combining hashes
3. Compare root hashes between nodes
4. If different, traverse tree to find divergent keys
"""

import hashlib
from typing import Dict, List, Set, Tuple, Any
import json


class MerkleTree:
    """Merkle tree for data integrity verification"""
    
    def __init__(self, data: Dict[str, Any]):
        """
        Build Merkle tree from key-value store.
        
        Args:
            data: Dictionary of key-value pairs
        """
        self.leaves: Dict[str, str] = {}
        self.data = data
        
        # Create leaf hashes (sorted by key for consistency)
        for key in sorted(data.keys()):
            value_str = json.dumps(data[key], sort_keys=True)
            key_value = f"{key}:{value_str}"
            self.leaves[key] = hashlib.sha256(key_value.encode()).hexdigest()
        
        # Build tree bottom-up
        self.root = self._build_tree(list(self.leaves.values()))
    
    def _build_tree(self, hashes: List[str]) -> str:
        """
        Recursively build tree from leaf hashes.
        
        Args:
            hashes: List of hash values
            
        Returns:
            Root hash
        """
        if not hashes:
            return hashlib.sha256(b"").hexdigest()
        if len(hashes) == 1:
            return hashes[0]
        
        # Pair up hashes and create parent level
        parents = []
        for i in range(0, len(hashes), 2):
            if i + 1 < len(hashes):
                combined = hashes[i] + hashes[i + 1]
            else:
                # Odd number of nodes - duplicate last one
                combined = hashes[i] + hashes[i]
            
            parent_hash = hashlib.sha256(combined.encode()).hexdigest()
            parents.append(parent_hash)
        
        # Recursively build parent level
        return self._build_tree(parents)
    
    def get_root_hash(self) -> str:
        """
        Get root hash for comparison.
        
        Returns:
            SHA256 hash of the entire tree
        """
        return self.root
    
    def get_leaf_hash(self, key: str) -> str:
        """
        Get hash of a specific key.
        
        Args:
            key: Key to look up
            
        Returns:
            Hash of the key-value pair
        """
        return self.leaves.get(key, "")
    
    def get_divergent_keys(self, other: 'MerkleTree') -> Tuple[Set[str], Set[str], Set[str]]:
        """
        Find keys that differ between two trees.
        
        Args:
            other: Another MerkleTree to compare
            
        Returns:
            Tuple of (keys_only_in_self, keys_only_in_other, keys_with_different_values)
        """
        self_keys = set(self.leaves.keys())
        other_keys = set(other.leaves.keys())
        
        # Keys only in self
        only_in_self = self_keys - other_keys
        
        # Keys only in other
        only_in_other = other_keys - self_keys
        
        # Keys in both but with different values
        different_values = set()
        for key in self_keys & other_keys:
            if self.leaves[key] != other.leaves[key]:
                different_values.add(key)
        
        return only_in_self, only_in_other, different_values


class AntiEntropy:
    """
    Background process to sync replicas using Merkle trees.
    
    This ensures eventual consistency by:
    1. Periodically comparing Merkle tree root hashes
    2. If different, finding divergent keys
    3. Syncing those keys between nodes
    """
    
    async def sync_nodes(self, node1_url: str, node2_url: str) -> Dict[str, Any]:
        """
        Compare two nodes and sync differences.
        
        Args:
            node1_url: URL of first node
            node2_url: URL of second node
            
        Returns:
            Dictionary with sync statistics
        """
        import httpx
        
        stats = {
            "synced": False,
            "keys_synced": 0,
            "keys_only_in_node1": 0,
            "keys_only_in_node2": 0,
            "keys_with_conflicts": 0,
            "error": None
        }
        
        try:
            async with httpx.AsyncClient() as client:
                # Get all data from both nodes
                resp1 = await client.get(f"{node1_url}/stats", timeout=10.0)
                resp2 = await client.get(f"{node2_url}/stats", timeout=10.0)
                
                if resp1.status_code != 200 or resp2.status_code != 200:
                    stats["error"] = "Failed to fetch node stats"
                    return stats
                
                # Extract data
                data1 = resp1.json().get("data", {})
                data2 = resp2.json().get("data", {})
                
                # Build Merkle trees
                tree1 = MerkleTree(data1)
                tree2 = MerkleTree(data2)
                
                # Quick check: if roots match, data is in sync
                if tree1.get_root_hash() == tree2.get_root_hash():
                    stats["synced"] = True
                    return stats
                
                # Find divergent keys
                only_in_1, only_in_2, conflicts = tree1.get_divergent_keys(tree2)
                
                stats["keys_only_in_node1"] = len(only_in_1)
                stats["keys_only_in_node2"] = len(only_in_2)
                stats["keys_with_conflicts"] = len(conflicts)
                
                # Sync: Copy keys from node1 to node2
                for key in only_in_1:
                    try:
                        await client.post(
                            f"{node2_url}/set",
                            json={"key": key, "value": data1[key], "is_replica": True},
                            timeout=2.0
                        )
                        stats["keys_synced"] += 1
                    except Exception as e:
                        print(f"Failed to sync key {key} from node1 to node2: {e}")
                
                # Sync: Copy keys from node2 to node1
                for key in only_in_2:
                    try:
                        await client.post(
                            f"{node1_url}/set",
                            json={"key": key, "value": data2[key], "is_replica": True},
                            timeout=2.0
                        )
                        stats["keys_synced"] += 1
                    except Exception as e:
                        print(f"Failed to sync key {key} from node2 to node1: {e}")
                
                # Conflict resolution: Last-write-wins (use node1's value)
                for key in conflicts:
                    try:
                        await client.post(
                            f"{node2_url}/set",
                            json={"key": key, "value": data1[key], "is_replica": True},
                            timeout=2.0
                        )
                        stats["keys_synced"] += 1
                    except Exception as e:
                        print(f"Failed to resolve conflict for key {key}: {e}")
                
                stats["synced"] = True
                
        except Exception as e:
            stats["error"] = str(e)
        
        return stats
    
    async def sync_cluster(self, nodes: Dict[int, str]) -> Dict[str, Any]:
        """
        Sync all node pairs in a cluster.
        
        Args:
            nodes: Dict of {node_id: "http://host:port"}
            
        Returns:
            Dictionary with cluster-wide sync statistics
        """
        total_stats = {
            "pairs_synced": 0,
            "total_keys_synced": 0,
            "errors": []
        }
        
        # Sync all unique pairs
        node_ids = list(nodes.keys())
        for i in range(len(node_ids)):
            for j in range(i + 1, len(node_ids)):
                node1_id = node_ids[i]
                node2_id = node_ids[j]
                node1_url = nodes[node1_id]
                node2_url = nodes[node2_id]
                
                print(f"[Anti-Entropy] Syncing Node {node1_id} <-> Node {node2_id}")
                
                stats = await self.sync_nodes(node1_url, node2_url)
                
                if stats["synced"]:
                    total_stats["pairs_synced"] += 1
                    total_stats["total_keys_synced"] += stats["keys_synced"]
                    
                    if stats["keys_synced"] > 0:
                        print(f"  ✓ Synced {stats['keys_synced']} keys")
                    else:
                        print(f"  ✓ Already in sync")
                else:
                    error_msg = f"Node {node1_id} <-> {node2_id}: {stats['error']}"
                    total_stats["errors"].append(error_msg)
                    print(f"  ✗ {error_msg}")
        
        return total_stats


# Test Merkle tree
if __name__ == "__main__":
    print("=" * 60)
    print("  Merkle Tree Test")
    print("=" * 60)
    
    # Test 1: Identical data
    data1 = {"key1": "value1", "key2": "value2", "key3": "value3"}
    data2 = {"key1": "value1", "key2": "value2", "key3": "value3"}
    
    tree1 = MerkleTree(data1)
    tree2 = MerkleTree(data2)
    
    print("\nTest 1: Identical data")
    print(f"  Tree1 root: {tree1.get_root_hash()[:16]}...")
    print(f"  Tree2 root: {tree2.get_root_hash()[:16]}...")
    print(f"  Match: {tree1.get_root_hash() == tree2.get_root_hash()}")
    
    # Test 2: Different data
    data3 = {"key1": "value1", "key2": "DIFFERENT", "key4": "value4"}
    tree3 = MerkleTree(data3)
    
    print("\nTest 2: Different data")
    print(f"  Tree1 root: {tree1.get_root_hash()[:16]}...")
    print(f"  Tree3 root: {tree3.get_root_hash()[:16]}...")
    print(f"  Match: {tree1.get_root_hash() == tree3.get_root_hash()}")
    
    # Test 3: Find divergent keys
    only_in_1, only_in_3, conflicts = tree1.get_divergent_keys(tree3)
    
    print("\nTest 3: Divergent keys")
    print(f"  Only in tree1: {only_in_1}")
    print(f"  Only in tree3: {only_in_3}")
    print(f"  Conflicts: {conflicts}")
    
    print("\n" + "=" * 60)

