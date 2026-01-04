"""
API Gateway that routes requests to appropriate nodes based on consistent hashing.
Provides single entry point for clients.

This is the "brain" of the distributed system - it:
1. Uses consistent hashing to determine which node owns a key
2. Routes requests to the correct node
3. Monitors node health via heartbeats
4. Implements failover by reading from replicas if primary is down
5. Dynamically updates the hash ring when nodes fail/recover
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import httpx
import asyncio
import time

from .consistent_hash import ConsistentHashRing
from .merkle_tree import AntiEntropy


class SetRequest(BaseModel):
    """Request model for SET operations"""
    value: Any


class Gateway:
    """
    API Gateway for distributed MiniKV cluster.
    Routes requests to correct nodes based on consistent hashing.
    """
    
    def __init__(self, nodes: Dict[int, str], health_check_interval: int = 5):
        """
        Initialize gateway with cluster nodes.
        
        Args:
            nodes: Dict of {node_id: "http://host:port"}
            health_check_interval: Seconds between health checks (default: 5s)
        
        Example:
            nodes = {
                1: "http://localhost:8001",
                2: "http://localhost:8002",
                3: "http://localhost:8003"
            }
            gateway = Gateway(nodes)
        """
        self.app = FastAPI(title="MiniKV-Gateway")
        self.nodes = nodes
        self.hash_ring = ConsistentHashRing(list(nodes.keys()))
        
        # Health tracking
        self.healthy_nodes = set(nodes.keys())  # Assume all healthy at start
        self.health_check_interval = health_check_interval
        self._health_check_task = None
        self._anti_entropy_task = None
        
        # Anti-entropy for data reconciliation
        self.anti_entropy = AntiEntropy()
        
        # Statistics
        self.total_requests = 0
        self.failed_requests = 0
        self.start_time = time.time()
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup FastAPI routes for gateway operations"""
        
        @self.app.on_event("startup")
        async def startup():
            """Start background tasks on gateway startup"""
            # Start health monitoring
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            print("Gateway started - health monitoring active")
            
            # Start anti-entropy background sync (every 10 minutes)
            self._anti_entropy_task = asyncio.create_task(self._anti_entropy_loop())
            print("Gateway started - anti-entropy sync active (10min intervals)")
        
        @self.app.on_event("shutdown")
        async def shutdown():
            """Clean shutdown of background tasks"""
            if self._health_check_task:
                self._health_check_task.cancel()
            if self._anti_entropy_task:
                self._anti_entropy_task.cancel()
        
        @self.app.post("/set/{key}")
        async def set_key(key: str, request: SetRequest):
            """
            Route SET request to appropriate node based on consistent hash.
            
            Args:
                key: Key to set
                request: SetRequest with value
                
            Returns:
                Response from the node
            """
            self.total_requests += 1
            
            try:
                # Get primary node for this key
                node_id = self.hash_ring.get_node(key)
                
                # Check if node is healthy
                if node_id not in self.healthy_nodes:
                    # Try replica nodes
                    replica_nodes = self.hash_ring.get_nodes_for_replication(key, n=2)
                    if len(replica_nodes) > 1:
                        node_id = replica_nodes[1]  # Use first replica
                    else:
                        raise HTTPException(
                            status_code=503,
                            detail=f"Primary node {node_id} is down and no replicas available"
                        )
                
                node_url = self.nodes[node_id]
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{node_url}/set",
                        json={"key": key, "value": request.value, "is_replica": False},
                        timeout=5.0
                    )
                    return response.json()
                    
            except Exception as e:
                self.failed_requests += 1
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/get/{key}")
        async def get_key(key: str):
            """
            Route GET request to appropriate node.
            Implements failover: if primary is down, read from replica.
            """
            self.total_requests += 1
            
            try:
                # Get primary and replica nodes
                replica_nodes = self.hash_ring.get_nodes_for_replication(key, n=2)
                
                # Try primary first
                for node_id in replica_nodes:
                    if node_id in self.healthy_nodes:
                        node_url = self.nodes[node_id]
                        
                        try:
                            async with httpx.AsyncClient() as client:
                                response = await client.get(
                                    f"{node_url}/get/{key}",
                                    timeout=5.0
                                )
                                return response.json()
                        except Exception as e:
                            # Try next replica
                            continue
                
                # All nodes failed
                raise HTTPException(
                    status_code=503,
                    detail=f"All replica nodes for key '{key}' are unavailable"
                )
                
            except HTTPException:
                raise
            except Exception as e:
                self.failed_requests += 1
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.delete("/delete/{key}")
        async def delete_key(key: str):
            """Route DELETE request to appropriate node"""
            self.total_requests += 1
            
            try:
                node_id = self.hash_ring.get_node(key)
                
                # Check if node is healthy
                if node_id not in self.healthy_nodes:
                    raise HTTPException(
                        status_code=503,
                        detail=f"Primary node {node_id} is down"
                    )
                
                node_url = self.nodes[node_id]
                
                async with httpx.AsyncClient() as client:
                    response = await client.delete(
                        f"{node_url}/delete/{key}",
                        timeout=5.0
                    )
                    return response.json()
                    
            except Exception as e:
                self.failed_requests += 1
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/exists/{key}")
        async def exists_key(key: str):
            """Check if key exists"""
            self.total_requests += 1
            
            try:
                node_id = self.hash_ring.get_node(key)
                node_url = self.nodes[node_id]
                
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{node_url}/exists/{key}",
                        timeout=5.0
                    )
                    return response.json()
                    
            except Exception as e:
                self.failed_requests += 1
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/cluster/status")
        async def cluster_status():
            """
            Get cluster health status for all nodes.
            Useful for monitoring and debugging.
            """
            status = {}
            
            async with httpx.AsyncClient() as client:
                for node_id, node_url in self.nodes.items():
                    try:
                        response = await client.get(
                            f"{node_url}/health",
                            timeout=2.0
                        )
                        node_status = response.json()
                        node_status["healthy"] = node_id in self.healthy_nodes
                        status[f"node_{node_id}"] = node_status
                    except Exception as e:
                        status[f"node_{node_id}"] = {
                            "status": "unhealthy",
                            "healthy": False,
                            "error": str(e)
                        }
            
            return {
                "cluster_size": len(self.nodes),
                "healthy_nodes": len(self.healthy_nodes),
                "unhealthy_nodes": len(self.nodes) - len(self.healthy_nodes),
                "nodes": status
            }
        
        @self.app.get("/cluster/distribution")
        async def key_distribution():
            """
            Show how keys are distributed across nodes.
            Useful for validating consistent hashing.
            """
            distribution = {}
            
            async with httpx.AsyncClient() as client:
                for node_id, node_url in self.nodes.items():
                    try:
                        response = await client.get(
                            f"{node_url}/keys",
                            timeout=2.0
                        )
                        keys_data = response.json()
                        distribution[f"node_{node_id}"] = {
                            "key_count": keys_data.get("count", 0),
                            "keys": keys_data.get("keys", [])[:10]  # First 10 keys
                        }
                    except Exception as e:
                        distribution[f"node_{node_id}"] = {
                            "error": str(e)
                        }
            
            return distribution
        
        @self.app.get("/stats")
        async def gateway_stats():
            """Gateway statistics"""
            uptime = time.time() - self.start_time
            
            return {
                "gateway": {
                    "uptime_seconds": int(uptime),
                    "total_requests": self.total_requests,
                    "failed_requests": self.failed_requests,
                    "success_rate": (
                        (self.total_requests - self.failed_requests) / self.total_requests * 100
                        if self.total_requests > 0 else 100.0
                    )
                },
                "cluster": {
                    "total_nodes": len(self.nodes),
                    "healthy_nodes": len(self.healthy_nodes),
                    "unhealthy_nodes": len(self.nodes) - len(self.healthy_nodes)
                }
            }
        
        @self.app.get("/health")
        async def health():
            """Gateway health check"""
            return {
                "status": "healthy",
                "cluster_healthy": len(self.healthy_nodes) >= (len(self.nodes) // 2 + 1)
            }
        
        @self.app.get("/")
        async def root():
            """Root endpoint with gateway information"""
            return {
                "service": "MiniKV Distributed Gateway",
                "version": "2.0.0",
                "cluster_size": len(self.nodes),
                "healthy_nodes": len(self.healthy_nodes),
                "status": "running"
            }
    
    async def _health_check_loop(self):
        """
        Periodically check node health (heartbeat-based failure detection).
        
        This runs every 5 seconds and:
        1. Pings each node's /health endpoint
        2. Updates healthy_nodes set
        3. Adds/removes nodes from hash ring based on health
        """
        while True:
            await asyncio.sleep(self.health_check_interval)
            
            async with httpx.AsyncClient() as client:
                for node_id, node_url in self.nodes.items():
                    try:
                        response = await client.get(
                            f"{node_url}/health",
                            timeout=2.0
                        )
                        
                        # Node responded successfully
                        if response.status_code == 200:
                            if node_id not in self.healthy_nodes:
                                print(f"[Gateway] Node {node_id} is back online")
                                self.hash_ring.add_node(node_id)
                                self.healthy_nodes.add(node_id)
                        else:
                            if node_id in self.healthy_nodes:
                                print(f"[Gateway] Node {node_id} returned non-200 status")
                                self.hash_ring.remove_node(node_id)
                                self.healthy_nodes.discard(node_id)
                                
                    except Exception as e:
                        # Node is down or unreachable
                        if node_id in self.healthy_nodes:
                            print(f"[Gateway] Node {node_id} is down: {e}")
                            self.hash_ring.remove_node(node_id)
                            self.healthy_nodes.discard(node_id)
    
    async def _anti_entropy_loop(self):
        """
        Periodically sync replicas using Merkle trees.
        Runs every 10 minutes to ensure eventual consistency.
        """
        # Wait 30 seconds before first sync (let cluster stabilize)
        await asyncio.sleep(30)
        
        while True:
            try:
                print("[Gateway] Starting anti-entropy sync...")
                
                # Only sync healthy nodes
                healthy_node_dict = {
                    node_id: url 
                    for node_id, url in self.nodes.items() 
                    if node_id in self.healthy_nodes
                }
                
                if len(healthy_node_dict) >= 2:
                    stats = await self.anti_entropy.sync_cluster(healthy_node_dict)
                    
                    if stats["total_keys_synced"] > 0:
                        print(f"[Gateway] Anti-entropy synced {stats['total_keys_synced']} keys across {stats['pairs_synced']} node pairs")
                    else:
                        print(f"[Gateway] Anti-entropy complete - all nodes in sync")
                    
                    if stats["errors"]:
                        print(f"[Gateway] Anti-entropy errors: {len(stats['errors'])}")
                else:
                    print(f"[Gateway] Skipping anti-entropy - not enough healthy nodes ({len(healthy_node_dict)})")
                
            except Exception as e:
                print(f"[Gateway] Anti-entropy error: {e}")
            
            # Wait 10 minutes before next sync
            await asyncio.sleep(600)
    
    def run(self, port: int = 8000):
        """Start the gateway"""
        import uvicorn
        print("=" * 60)
        print("  MiniKV v2.0 - API Gateway")
        print("=" * 60)
        print(f"  Port: {port}")
        print(f"  Cluster nodes: {len(self.nodes)}")
        print(f"  Health check interval: {self.health_check_interval}s")
        print("=" * 60)
        
        uvicorn.run(
            self.app,
            host="0.0.0.0",
            port=port,
            log_level="info"
        )


if __name__ == "__main__":
    # Configure cluster nodes
    nodes = {
        1: "http://localhost:8001",
        2: "http://localhost:8002",
        3: "http://localhost:8003"
    }
    
    gateway = Gateway(nodes, health_check_interval=5)
    gateway.run(port=8000)

