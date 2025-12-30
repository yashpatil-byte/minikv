"""
Benchmarking framework for MiniKV.
Measures throughput and latency under different workloads.
"""

import time
import threading
import statistics
from typing import List, Dict, Any
import random
from server.router import Router


class Benchmark:
    """Base class for benchmarks."""
    
    def __init__(self, router: Router, name: str):
        """
        Initialize a benchmark.
        
        Args:
            router: The router to benchmark
            name: Name of the benchmark
        """
        self.router = router
        self.name = name
        self.results = []
    
    def run(self):
        """Run the benchmark. Override in subclasses."""
        raise NotImplementedError
    
    def report(self) -> Dict[str, Any]:
        """
        Generate a report of the benchmark results.
        
        Returns:
            Dictionary with benchmark statistics
        """
        if not self.results:
            return {"name": self.name, "error": "No results"}
        
        return {
            "name": self.name,
            "total_operations": len(self.results),
            "mean_latency_ms": statistics.mean(self.results) * 1000,
            "median_latency_ms": statistics.median(self.results) * 1000,
            "min_latency_ms": min(self.results) * 1000,
            "max_latency_ms": max(self.results) * 1000,
            "p95_latency_ms": statistics.quantiles(self.results, n=20)[18] * 1000,
            "p99_latency_ms": statistics.quantiles(self.results, n=100)[98] * 1000,
        }


class WriteBenchmark(Benchmark):
    """Benchmark for write operations."""
    
    def __init__(self, router: Router, num_operations: int = 10000):
        """
        Initialize write benchmark.
        
        Args:
            router: The router to benchmark
            num_operations: Number of write operations to perform
        """
        super().__init__(router, "Write Benchmark")
        self.num_operations = num_operations
    
    def run(self):
        """Run write benchmark."""
        print(f"Running {self.name} ({self.num_operations} operations)...")
        
        start_time = time.time()
        
        for i in range(self.num_operations):
            op_start = time.time()
            self.router.set(f"key_{i}", {"value": i, "data": "x" * 100})
            op_end = time.time()
            self.results.append(op_end - op_start)
        
        end_time = time.time()
        elapsed = end_time - start_time
        throughput = self.num_operations / elapsed
        
        print(f"  Completed in {elapsed:.2f}s")
        print(f"  Throughput: {throughput:.2f} ops/sec\n")


class ReadBenchmark(Benchmark):
    """Benchmark for read operations."""
    
    def __init__(self, router: Router, num_operations: int = 10000):
        """
        Initialize read benchmark.
        
        Args:
            router: The router to benchmark
            num_operations: Number of read operations to perform
        """
        super().__init__(router, "Read Benchmark")
        self.num_operations = num_operations
    
    def run(self):
        """Run read benchmark."""
        # Pre-populate data
        print(f"Preparing data for {self.name}...")
        for i in range(1000):
            self.router.set(f"key_{i}", {"value": i})
        
        print(f"Running {self.name} ({self.num_operations} operations)...")
        
        start_time = time.time()
        
        for i in range(self.num_operations):
            key = f"key_{random.randint(0, 999)}"
            op_start = time.time()
            self.router.get(key)
            op_end = time.time()
            self.results.append(op_end - op_start)
        
        end_time = time.time()
        elapsed = end_time - start_time
        throughput = self.num_operations / elapsed
        
        print(f"  Completed in {elapsed:.2f}s")
        print(f"  Throughput: {throughput:.2f} ops/sec\n")


class MixedBenchmark(Benchmark):
    """Benchmark for mixed read/write workload."""
    
    def __init__(
        self,
        router: Router,
        num_operations: int = 10000,
        read_ratio: float = 0.8
    ):
        """
        Initialize mixed benchmark.
        
        Args:
            router: The router to benchmark
            num_operations: Number of operations to perform
            read_ratio: Ratio of reads to total operations (0.0 to 1.0)
        """
        super().__init__(router, f"Mixed Benchmark ({int(read_ratio*100)}% reads)")
        self.num_operations = num_operations
        self.read_ratio = read_ratio
    
    def run(self):
        """Run mixed benchmark."""
        # Pre-populate data
        print(f"Preparing data for {self.name}...")
        for i in range(1000):
            self.router.set(f"key_{i}", {"value": i})
        
        print(f"Running {self.name} ({self.num_operations} operations)...")
        
        start_time = time.time()
        
        for i in range(self.num_operations):
            key = f"key_{random.randint(0, 999)}"
            op_start = time.time()
            
            if random.random() < self.read_ratio:
                self.router.get(key)
            else:
                self.router.set(key, {"value": random.randint(0, 10000)})
            
            op_end = time.time()
            self.results.append(op_end - op_start)
        
        end_time = time.time()
        elapsed = end_time - start_time
        throughput = self.num_operations / elapsed
        
        print(f"  Completed in {elapsed:.2f}s")
        print(f"  Throughput: {throughput:.2f} ops/sec\n")


class ConcurrentBenchmark(Benchmark):
    """Benchmark for concurrent operations."""
    
    def __init__(
        self,
        router: Router,
        num_threads: int = 10,
        operations_per_thread: int = 1000
    ):
        """
        Initialize concurrent benchmark.
        
        Args:
            router: The router to benchmark
            num_threads: Number of concurrent threads
            operations_per_thread: Operations per thread
        """
        super().__init__(
            router,
            f"Concurrent Benchmark ({num_threads} threads)"
        )
        self.num_threads = num_threads
        self.operations_per_thread = operations_per_thread
        self.results_lock = threading.Lock()
    
    def run(self):
        """Run concurrent benchmark."""
        print(f"Running {self.name} ({self.num_threads * self.operations_per_thread} total ops)...")
        
        def thread_work(thread_id):
            thread_results = []
            for i in range(self.operations_per_thread):
                key = f"thread_{thread_id}_key_{i}"
                
                op_start = time.time()
                
                # Mixed operations
                op = random.choice(['set', 'get', 'exists'])
                if op == 'set':
                    self.router.set(key, {"value": i, "thread": thread_id})
                elif op == 'get':
                    self.router.get(key)
                else:
                    self.router.exists(key)
                
                op_end = time.time()
                thread_results.append(op_end - op_start)
            
            with self.results_lock:
                self.results.extend(thread_results)
        
        threads = []
        start_time = time.time()
        
        for i in range(self.num_threads):
            t = threading.Thread(target=thread_work, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        end_time = time.time()
        elapsed = end_time - start_time
        total_ops = self.num_threads * self.operations_per_thread
        throughput = total_ops / elapsed
        
        print(f"  Completed in {elapsed:.2f}s")
        print(f"  Throughput: {throughput:.2f} ops/sec\n")


class BenchmarkSuite:
    """Suite of benchmarks to run."""
    
    def __init__(
        self,
        num_workers: int = 4,
        enable_persistence: bool = False,
        enable_wal: bool = False
    ):
        """
        Initialize benchmark suite.
        
        Args:
            num_workers: Number of worker threads
            enable_persistence: Whether to enable persistence
            enable_wal: Whether to enable WAL
        """
        self.router = Router(
            num_workers=num_workers,
            enable_persistence=enable_persistence,
            enable_wal=enable_wal
        )
        self.benchmarks: List[Benchmark] = []
    
    def add_benchmark(self, benchmark: Benchmark):
        """Add a benchmark to the suite."""
        self.benchmarks.append(benchmark)
    
    def run_all(self):
        """Run all benchmarks in the suite."""
        print("=" * 70)
        print("  MiniKV Benchmark Suite")
        print("=" * 70)
        print()
        
        self.router.start()
        
        try:
            for benchmark in self.benchmarks:
                benchmark.run()
                
                # Clear store between benchmarks
                self.router.clear()
            
            # Print summary
            print("=" * 70)
            print("  Summary")
            print("=" * 70)
            print()
            
            for benchmark in self.benchmarks:
                report = benchmark.report()
                print(f"{report['name']}:")
                print(f"  Total Operations: {report['total_operations']}")
                print(f"  Mean Latency:     {report['mean_latency_ms']:.3f} ms")
                print(f"  Median Latency:   {report['median_latency_ms']:.3f} ms")
                print(f"  P95 Latency:      {report['p95_latency_ms']:.3f} ms")
                print(f"  P99 Latency:      {report['p99_latency_ms']:.3f} ms")
                print()
            
            # Print system stats
            stats = self.router.get_stats()
            print("System Statistics:")
            print(f"  Workers: {stats['num_workers']}")
            print(f"  Total Requests Processed: {stats['total_requests']}")
            print()
        
        finally:
            self.router.stop()


def main():
    """Run the benchmark suite."""
    import argparse
    
    parser = argparse.ArgumentParser(description="MiniKV Benchmark Suite")
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of worker threads (default: 4)"
    )
    parser.add_argument(
        "--operations",
        type=int,
        default=10000,
        help="Number of operations per benchmark (default: 10000)"
    )
    parser.add_argument(
        "--persistence",
        action="store_true",
        help="Enable persistence"
    )
    parser.add_argument(
        "--wal",
        action="store_true",
        help="Enable write-ahead logging"
    )
    
    args = parser.parse_args()
    
    # Create benchmark suite
    suite = BenchmarkSuite(
        num_workers=args.workers,
        enable_persistence=args.persistence,
        enable_wal=args.wal
    )
    
    # Add benchmarks
    suite.add_benchmark(WriteBenchmark(suite.router, args.operations))
    suite.add_benchmark(ReadBenchmark(suite.router, args.operations))
    suite.add_benchmark(MixedBenchmark(suite.router, args.operations, read_ratio=0.8))
    suite.add_benchmark(MixedBenchmark(suite.router, args.operations, read_ratio=0.5))
    suite.add_benchmark(ConcurrentBenchmark(suite.router, num_threads=10, operations_per_thread=1000))
    suite.add_benchmark(ConcurrentBenchmark(suite.router, num_threads=50, operations_per_thread=200))
    
    # Run all benchmarks
    suite.run_all()


if __name__ == "__main__":
    main()

