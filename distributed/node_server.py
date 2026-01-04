"""
Individual node server that exposes HTTP API for cluster communication.
Each node runs its own Router + Store instance on different ports.

WHY ASYNC REPLICATION?
- Faster writes: Primary responds immediately without waiting for replicas
- Better availability: Primary can accept writes even if replicas are slow/down
- Trade-off: Eventual consistency instead of strong consistency (acceptable for KV store)
"""

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Any, Optional, Dict, List
import uvicorn
import asyncio
import httpx
import time

from server.router import Router


class SetRequest(BaseModel):
    """Request model for SET operations"""
    key: str
    value: Any
    is_replica: bool = False  # True if this is a replication write


class GetRequest(BaseModel):
    """Request model for GET operations"""
    key: str


class NodeServer:
    """
    Individual node server in the distributed cluster.
    Each node maintains its own in-memory store, WAL, and persistence.
    """
    
    def __init__(self, node_id: int, port: int, num_workers: int = 4):
        """
        Initialize node server.
        
        Args:
            node_id: Unique identifier for this node (1, 2, 3)
            port: HTTP port for this node (8001, 8002, 8003)
            num_workers: Number of worker threads for Router
        """
        self.node_id = node_id
        self.port = port
        self.app = FastAPI(title=f"MiniKV-Node-{node_id}")
        
        # Initialize local store with isolated data files
        self.router = Router(
            num_workers=num_workers,
            enable_persistence=True,
            enable_wal=True,
            db_path=f"node_{node_id}.db",
            wal_path=f"node_{node_id}.wal"
        )
        self.router.start()
        
        # Track cluster peers for replication
        self.peers: Dict[int, str] = {}  # {node_id: "http://host:port"}
        
        # Metrics
        self.total_reads = 0
        self.total_writes = 0
        self.replication_failures = 0
        self.start_time = time.time()
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup FastAPI routes for node operations"""
        
        @self.app.post("/set")
        async def set_key(req: SetRequest):
            """
            Set a key-value pair (primary write).
            If this is a primary write, asynchronously replicate to peers.
            """
            try:
                self.router.set(req.key, req.value)
                self.total_writes += 1
                
                # Async replicate to peers (if not already a replica write)
                if not req.is_replica and self.peers:
                    asyncio.create_task(self._replicate_set(req.key, req.value))
                
                return {"status": "ok", "node_id": self.node_id}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/get/{key}")
        async def get_key(key: str):
            """
            Get a value by key.
            Performs read repair in background if inconsistencies detected.
            """
            try:
                value = self.router.get(key)
                self.total_reads += 1
                
                # Background read repair (don't wait for it)
                if value is not None and self.peers:
                    asyncio.create_task(self._read_repair(key, value))
                
                return {"key": key, "value": value, "node_id": self.node_id}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.delete("/delete/{key}")
        async def delete_key(key: str):
            """Delete a key and replicate deletion to peers"""
            try:
                deleted = self.router.delete(key)
                self.total_writes += 1
                
                # Async replicate deletion
                if self.peers:
                    asyncio.create_task(self._replicate_delete(key))
                
                return {"deleted": deleted, "node_id": self.node_id}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/exists/{key}")
        async def exists_key(key: str):
            """Check if key exists"""
            try:
                exists = self.router.exists(key)
                return {"key": key, "exists": exists, "node_id": self.node_id}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/keys")
        async def get_keys():
            """Get all keys in this node"""
            try:
                keys = self.router.keys()
                return {"keys": keys, "count": len(keys), "node_id": self.node_id}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/health")
        async def health():
            """
            Health check endpoint for monitoring.
            Used by gateway for heartbeat-based failure detection.
            """
            uptime = time.time() - self.start_time
            return {
                "node_id": self.node_id,
                "status": "healthy",
                "uptime_seconds": int(uptime),
                "store_size": self.router.size(),
                "total_reads": self.total_reads,
                "total_writes": self.total_writes,
                "replication_failures": self.replication_failures,
                "peers": len(self.peers)
            }
        
        @self.app.get("/stats")
        async def stats():
            """
            Detailed node statistics including all key-value pairs.
            Used for anti-entropy Merkle tree comparisons.
            """
            router_stats = self.router.get_stats()
            
            # Get all data for Merkle tree comparison
            all_items = self.router.items()
            data_dict = {k: v for k, v in all_items}
            
            return {
                "node_id": self.node_id,
                "uptime": time.time() - self.start_time,
                "total_reads": self.total_reads,
                "total_writes": self.total_writes,
                "replication_failures": self.replication_failures,
                "router_stats": router_stats,
                "data": data_dict  # All key-value pairs for anti-entropy
            }
        
        @self.app.post("/register_peer")
        async def register_peer(peer_id: int, peer_url: str):
            """
            Register a peer node for replication.
            Called by cluster manager during initialization.
            """
            self.peers[peer_id] = peer_url
            return {
                "status": "ok",
                "message": f"Registered peer {peer_id}",
                "total_peers": len(self.peers)
            }
        
        @self.app.get("/")
        async def root():
            """Root endpoint with node information"""
            return {
                "service": "MiniKV Distributed Node",
                "node_id": self.node_id,
                "version": "2.0.0",
                "port": self.port,
                "status": "running"
            }
    
    async def _replicate_set(self, key: str, value: Any):
        """
        Replicate SET operation to peer nodes asynchronously.
        This implements N=2 replication (primary + 1 backup).
        
        Args:
            key: Key to replicate
            value: Value to replicate
        """
        async with httpx.AsyncClient() as client:
            # Replicate to ALL peers (eventually consistent)
            tasks = []
            for peer_id, peer_url in self.peers.items():
                tasks.append(self._replicate_to_peer(
                    client, peer_url, key, value, peer_id
                ))
            
            # Fire and forget - don't wait for replication
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _replicate_to_peer(
        self,
        client: httpx.AsyncClient,
        peer_url: str,
        key: str,
        value: Any,
        peer_id: int
    ):
        """Helper to replicate to a single peer"""
        try:
            response = await client.post(
                f"{peer_url}/set",
                json={"key": key, "value": value, "is_replica": True},
                timeout=2.0
            )
            if response.status_code != 200:
                self.replication_failures += 1
        except Exception as e:
            # Log failure but don't crash
            self.replication_failures += 1
            print(f"[Node {self.node_id}] Replication to node {peer_id} failed: {e}")
    
    async def _replicate_delete(self, key: str):
        """Replicate DELETE operation to peer nodes asynchronously"""
        async with httpx.AsyncClient() as client:
            tasks = []
            for peer_id, peer_url in self.peers.items():
                tasks.append(self._delete_from_peer(client, peer_url, key, peer_id))
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _delete_from_peer(
        self,
        client: httpx.AsyncClient,
        peer_url: str,
        key: str,
        peer_id: int
    ):
        """Helper to delete from a single peer"""
        try:
            await client.delete(f"{peer_url}/delete/{key}", timeout=2.0)
        except Exception as e:
            self.replication_failures += 1
            print(f"[Node {self.node_id}] Delete replication to node {peer_id} failed: {e}")
    
    async def _read_repair(self, key: str, expected_value: Any):
        """
        Perform read repair: ensure replicas have the correct value.
        This helps maintain eventual consistency.
        
        Args:
            key: Key that was read
            expected_value: Value from primary node
        """
        async with httpx.AsyncClient() as client:
            for peer_id, peer_url in self.peers.items():
                try:
                    # Check if peer has the key
                    response = await client.get(
                        f"{peer_url}/get/{key}",
                        timeout=1.0
                    )
                    
                    if response.status_code == 200:
                        peer_value = response.json().get("value")
                        
                        # If peer has different value, repair it
                        if peer_value != expected_value:
                            await client.post(
                                f"{peer_url}/set",
                                json={"key": key, "value": expected_value, "is_replica": True},
                                timeout=1.0
                            )
                except Exception:
                    # Silently ignore read repair failures
                    pass
    
    def run(self):
        """Start the node server"""
        print(f"Starting MiniKV Node {self.node_id} on port {self.port}")
        uvicorn.run(
            self.app,
            host="0.0.0.0",
            port=self.port,
            log_level="info"
        )
    
    def stop(self):
        """Stop the node server gracefully"""
        self.router.stop()


if __name__ == "__main__":
    import sys
    
    # Parse command line arguments
    node_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000 + node_id
    
    print("=" * 60)
    print(f"  MiniKV v2.0 - Distributed Node {node_id}")
    print("=" * 60)
    print(f"  Port: {port}")
    print(f"  Database: node_{node_id}.db")
    print(f"  WAL: node_{node_id}.wal")
    print("=" * 60)
    
    server = NodeServer(node_id, port)
    
    try:
        server.run()
    except KeyboardInterrupt:
        print(f"\nShutting down node {node_id}...")
        server.stop()

