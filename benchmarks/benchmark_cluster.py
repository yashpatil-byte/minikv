"""
Benchmark distributed cluster performance.

Tests:
1. Write throughput
2. Read throughput
3. Mixed workload (80% reads, 20% writes)
4. Node failure scenario
5. Concurrent clients
"""

import asyncio
import httpx
import time
import random
import statistics
import argparse
from typing import List, Dict, Any


class ClusterBenchmark:
    """Benchmark suite for distributed MiniKV cluster"""
    
    def __init__(self, gateway_url: str = "http://localhost:8000"):
        self.gateway_url = gateway_url
        self.results: Dict[str, Any] = {}
    
    async def benchmark_writes(self, num_operations: int, concurrency: int = 100):
        """
        Benchmark write throughput.
        
        Args:
            num_operations: Total number of write operations
            concurrency: Number of concurrent requests
        """
        print(f"\n{'='*70}")
        print(f"  Write Benchmark ({num_operations:,} operations, concurrency={concurrency})")
        print(f"{'='*70}")
        
        latencies = []
        errors = 0
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            start_time = time.time()
            
            # Create batches of concurrent requests
            batch_size = concurrency
            num_batches = num_operations // batch_size
            
            for batch in range(num_batches):
                tasks = []
                
                for i in range(batch_size):
                    key_id = batch * batch_size + i
                    key = f"bench_key_{key_id}"
                    value = f"value_{random.randint(0, 1000000)}"
                    
                    tasks.append(self._write_operation(client, key, value, latencies))
                
                # Execute batch
                results = await asyncio.gather(*tasks, return_exceptions=True)
                errors += sum(1 for r in results if isinstance(r, Exception))
                
                # Progress indicator
                if (batch + 1) % 10 == 0:
                    elapsed = time.time() - start_time
                    completed = (batch + 1) * batch_size
                    rate = completed / elapsed if elapsed > 0 else 0
                    print(f"  Progress: {completed:,}/{num_operations:,} ops ({rate:.0f} ops/sec)")
            
            duration = time.time() - start_time
        
        # Calculate statistics
        throughput = num_operations / duration
        
        if latencies:
            mean_latency = statistics.mean(latencies) * 1000  # ms
            median_latency = statistics.median(latencies) * 1000
            p95_latency = statistics.quantiles(latencies, n=20)[18] * 1000
            p99_latency = statistics.quantiles(latencies, n=100)[98] * 1000
        else:
            mean_latency = median_latency = p95_latency = p99_latency = 0
        
        result = {
            "operation": "write",
            "total_operations": num_operations,
            "duration_seconds": duration,
            "throughput_ops_per_sec": throughput,
            "mean_latency_ms": mean_latency,
            "median_latency_ms": median_latency,
            "p95_latency_ms": p95_latency,
            "p99_latency_ms": p99_latency,
            "errors": errors,
            "success_rate": (num_operations - errors) / num_operations * 100
        }
        
        self.results["write"] = result
        self._print_result(result)
        
        return result
    
    async def benchmark_reads(self, num_operations: int, concurrency: int = 100):
        """
        Benchmark read throughput.
        
        Args:
            num_operations: Total number of read operations
            concurrency: Number of concurrent requests
        """
        print(f"\n{'='*70}")
        print(f"  Read Benchmark ({num_operations:,} operations, concurrency={concurrency})")
        print(f"{'='*70}")
        
        # Pre-populate some keys
        print("  Pre-populating data...")
        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(1000):
                key = f"bench_key_{i}"
                value = f"value_{i}"
                await client.post(
                    f"{self.gateway_url}/set/{key}",
                    json={"value": value}
                )
        
        latencies = []
        errors = 0
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            start_time = time.time()
            
            batch_size = concurrency
            num_batches = num_operations // batch_size
            
            for batch in range(num_batches):
                tasks = []
                
                for i in range(batch_size):
                    # Read random keys
                    key = f"bench_key_{random.randint(0, 999)}"
                    tasks.append(self._read_operation(client, key, latencies))
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                errors += sum(1 for r in results if isinstance(r, Exception))
                
                if (batch + 1) % 10 == 0:
                    elapsed = time.time() - start_time
                    completed = (batch + 1) * batch_size
                    rate = completed / elapsed if elapsed > 0 else 0
                    print(f"  Progress: {completed:,}/{num_operations:,} ops ({rate:.0f} ops/sec)")
            
            duration = time.time() - start_time
        
        # Calculate statistics
        throughput = num_operations / duration
        
        if latencies:
            mean_latency = statistics.mean(latencies) * 1000
            median_latency = statistics.median(latencies) * 1000
            p95_latency = statistics.quantiles(latencies, n=20)[18] * 1000
            p99_latency = statistics.quantiles(latencies, n=100)[98] * 1000
        else:
            mean_latency = median_latency = p95_latency = p99_latency = 0
        
        result = {
            "operation": "read",
            "total_operations": num_operations,
            "duration_seconds": duration,
            "throughput_ops_per_sec": throughput,
            "mean_latency_ms": mean_latency,
            "median_latency_ms": median_latency,
            "p95_latency_ms": p95_latency,
            "p99_latency_ms": p99_latency,
            "errors": errors,
            "success_rate": (num_operations - errors) / num_operations * 100
        }
        
        self.results["read"] = result
        self._print_result(result)
        
        return result
    
    async def benchmark_mixed(
        self,
        num_operations: int,
        read_ratio: float = 0.8,
        concurrency: int = 100
    ):
        """
        Benchmark mixed read/write workload.
        
        Args:
            num_operations: Total operations
            read_ratio: Ratio of reads (0.0-1.0)
            concurrency: Concurrent requests
        """
        print(f"\n{'='*70}")
        print(f"  Mixed Benchmark ({int(read_ratio*100)}% reads, {num_operations:,} ops)")
        print(f"{'='*70}")
        
        latencies = []
        errors = 0
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            start_time = time.time()
            
            batch_size = concurrency
            num_batches = num_operations // batch_size
            
            for batch in range(num_batches):
                tasks = []
                
                for i in range(batch_size):
                    key_id = batch * batch_size + i
                    key = f"bench_key_{key_id % 1000}"
                    
                    if random.random() < read_ratio:
                        # Read operation
                        tasks.append(self._read_operation(client, key, latencies))
                    else:
                        # Write operation
                        value = f"value_{random.randint(0, 1000000)}"
                        tasks.append(self._write_operation(client, key, value, latencies))
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                errors += sum(1 for r in results if isinstance(r, Exception))
                
                if (batch + 1) % 10 == 0:
                    elapsed = time.time() - start_time
                    completed = (batch + 1) * batch_size
                    rate = completed / elapsed if elapsed > 0 else 0
                    print(f"  Progress: {completed:,}/{num_operations:,} ops ({rate:.0f} ops/sec)")
            
            duration = time.time() - start_time
        
        throughput = num_operations / duration
        
        if latencies:
            mean_latency = statistics.mean(latencies) * 1000
            median_latency = statistics.median(latencies) * 1000
            p95_latency = statistics.quantiles(latencies, n=20)[18] * 1000
            p99_latency = statistics.quantiles(latencies, n=100)[98] * 1000
        else:
            mean_latency = median_latency = p95_latency = p99_latency = 0
        
        result = {
            "operation": f"mixed_{int(read_ratio*100)}_reads",
            "total_operations": num_operations,
            "duration_seconds": duration,
            "throughput_ops_per_sec": throughput,
            "mean_latency_ms": mean_latency,
            "median_latency_ms": median_latency,
            "p95_latency_ms": p95_latency,
            "p99_latency_ms": p99_latency,
            "errors": errors,
            "success_rate": (num_operations - errors) / num_operations * 100
        }
        
        self.results["mixed"] = result
        self._print_result(result)
        
        return result
    
    async def _write_operation(
        self,
        client: httpx.AsyncClient,
        key: str,
        value: str,
        latencies: List[float]
    ):
        """Execute single write operation"""
        start = time.time()
        try:
            await client.post(
                f"{self.gateway_url}/set/{key}",
                json={"value": value}
            )
            latencies.append(time.time() - start)
        except Exception as e:
            raise e
    
    async def _read_operation(
        self,
        client: httpx.AsyncClient,
        key: str,
        latencies: List[float]
    ):
        """Execute single read operation"""
        start = time.time()
        try:
            await client.get(f"{self.gateway_url}/get/{key}")
            latencies.append(time.time() - start)
        except Exception as e:
            raise e
    
    def _print_result(self, result: Dict[str, Any]):
        """Pretty print benchmark result"""
        print(f"\n  Results:")
        print(f"  ├─ Throughput:      {result['throughput_ops_per_sec']:,.0f} ops/sec")
        print(f"  ├─ Mean Latency:    {result['mean_latency_ms']:.2f} ms")
        print(f"  ├─ Median Latency:  {result['median_latency_ms']:.2f} ms")
        print(f"  ├─ P95 Latency:     {result['p95_latency_ms']:.2f} ms")
        print(f"  ├─ P99 Latency:     {result['p99_latency_ms']:.2f} ms")
        print(f"  └─ Success Rate:    {result['success_rate']:.1f}%")
    
    def print_summary(self):
        """Print final summary of all benchmarks"""
        print(f"\n{'='*70}")
        print(f"  BENCHMARK SUMMARY")
        print(f"{'='*70}\n")
        
        for operation, result in self.results.items():
            print(f"{operation.upper()} BENCHMARK:")
            print(f"  Throughput:  {result['throughput_ops_per_sec']:>10,.0f} ops/sec")
            print(f"  P99 Latency: {result['p99_latency_ms']:>10.2f} ms")
            print()
        
        # Check if we met the 250K ops/sec target
        if "mixed" in self.results:
            throughput = self.results["mixed"]["throughput_ops_per_sec"]
            target = 250000
            
            print(f"{'='*70}")
            print(f"  TARGET PERFORMANCE: 250,000 ops/sec")
            print(f"  ACHIEVED: {throughput:,.0f} ops/sec")
            
            if throughput >= target:
                print(f"  STATUS: ✓ TARGET MET! ({throughput/target:.1f}x)")
            else:
                print(f"  STATUS: ✗ Below target ({throughput/target:.1f}x)")
            
            print(f"{'='*70}\n")


async def main():
    parser = argparse.ArgumentParser(description="Benchmark MiniKV distributed cluster")
    parser.add_argument("--gateway", default="http://localhost:8000", help="Gateway URL")
    parser.add_argument("--operations", type=int, default=100000, help="Operations per test")
    parser.add_argument("--concurrency", type=int, default=100, help="Concurrent requests")
    
    args = parser.parse_args()
    
    print(f"{'='*70}")
    print(f"  MiniKV v2.0 - Distributed Cluster Benchmark")
    print(f"{'='*70}")
    print(f"  Gateway:     {args.gateway}")
    print(f"  Operations:  {args.operations:,}")
    print(f"  Concurrency: {args.concurrency}")
    print(f"{'='*70}")
    
    benchmark = ClusterBenchmark(args.gateway)
    
    # Run benchmarks
    await benchmark.benchmark_writes(args.operations, args.concurrency)
    await benchmark.benchmark_reads(args.operations, args.concurrency)
    await benchmark.benchmark_mixed(args.operations, read_ratio=0.8, concurrency=args.concurrency)
    
    # Print summary
    benchmark.print_summary()


if __name__ == "__main__":
    asyncio.run(main())

