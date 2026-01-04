"""
Manages cluster membership and peer registration.

This utility helps bootstrap the cluster by:
1. Registering all nodes with each other for replication
2. Verifying cluster connectivity
3. Initializing the distributed system
"""

import httpx
import asyncio
from typing import Dict


class ClusterManager:
    """Manages cluster initialization and peer registration"""
    
    def __init__(self, nodes: Dict[int, str]):
        """
        Initialize cluster manager.
        
        Args:
            nodes: Dict of {node_id: "http://host:port"}
        """
        self.nodes = nodes
    
    async def register_peers(self):
        """
        Register all nodes with each other for replication.
        
        Each node needs to know about all other nodes so it can:
        - Replicate writes to backups
        - Perform read repair
        - Sync data via anti-entropy
        """
        print("Registering cluster peers...")
        print("=" * 60)
        
        async with httpx.AsyncClient() as client:
            for node_id, node_url in self.nodes.items():
                # Register all other nodes as peers
                for peer_id, peer_url in self.nodes.items():
                    if peer_id != node_id:
                        try:
                            response = await client.post(
                                f"{node_url}/register_peer",
                                params={"peer_id": peer_id, "peer_url": peer_url},
                                timeout=5.0
                            )
                            
                            if response.status_code == 200:
                                print(f"  ✓ Node {node_id} registered peer {peer_id}")
                            else:
                                print(f"  ✗ Node {node_id} failed to register peer {peer_id}: {response.status_code}")
                                
                        except Exception as e:
                            print(f"  ✗ Failed to register peer {peer_id} with node {node_id}: {e}")
        
        print("=" * 60)
        print("Peer registration complete!")
    
    async def verify_cluster(self):
        """
        Verify all nodes are healthy and responding.
        
        Returns:
            True if all nodes are healthy, False otherwise
        """
        print("\nVerifying cluster health...")
        print("=" * 60)
        
        all_healthy = True
        
        async with httpx.AsyncClient() as client:
            for node_id, node_url in self.nodes.items():
                try:
                    response = await client.get(
                        f"{node_url}/health",
                        timeout=3.0
                    )
                    
                    if response.status_code == 200:
                        health_data = response.json()
                        print(f"  ✓ Node {node_id}: {health_data.get('status', 'unknown')}")
                        print(f"    - Store size: {health_data.get('store_size', 0)} keys")
                        print(f"    - Peers: {health_data.get('peers', 0)}")
                    else:
                        print(f"  ✗ Node {node_id}: Unhealthy (status {response.status_code})")
                        all_healthy = False
                        
                except Exception as e:
                    print(f"  ✗ Node {node_id}: Unreachable ({e})")
                    all_healthy = False
        
        print("=" * 60)
        
        if all_healthy:
            print("✓ All nodes are healthy!")
        else:
            print("✗ Some nodes are unhealthy")
        
        return all_healthy
    
    async def initialize_cluster(self):
        """
        Full cluster initialization: register peers and verify health.
        
        Returns:
            True if initialization successful
        """
        print("\n" + "=" * 60)
        print("  MiniKV v2.0 - Cluster Initialization")
        print("=" * 60)
        print(f"  Nodes: {len(self.nodes)}")
        for node_id, node_url in self.nodes.items():
            print(f"    - Node {node_id}: {node_url}")
        print("=" * 60)
        
        # Step 1: Register peers
        await self.register_peers()
        
        # Step 2: Verify cluster health
        await asyncio.sleep(1)  # Give nodes time to process registrations
        healthy = await self.verify_cluster()
        
        if healthy:
            print("\n" + "=" * 60)
            print("  Cluster initialization successful!")
            print("  Gateway can now be started on port 8000")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("  Cluster initialization incomplete - some nodes unhealthy")
            print("=" * 60)
        
        return healthy


async def main():
    """Bootstrap a 3-node cluster"""
    import sys
    
    # Default 3-node local cluster
    nodes = {
        1: "http://localhost:8001",
        2: "http://localhost:8002",
        3: "http://localhost:8003"
    }
    
    manager = ClusterManager(nodes)
    success = await manager.initialize_cluster()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

