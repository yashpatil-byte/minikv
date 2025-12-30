"""
Command-line interface for interacting with MiniKV.
Provides an interactive REPL and batch command support.
"""

import sys
import json
import argparse
from typing import Optional
from server.router import Router


class MiniKVCLI:
    """
    Interactive CLI for the MiniKV key-value store.
    """
    
    def __init__(self, router: Router):
        """
        Initialize the CLI with a router.
        
        Args:
            router: The router instance to use for operations
        """
        self.router = router
        self.running = True
    
    def start(self):
        """Start the interactive REPL."""
        print("=" * 60)
        print("  MiniKV - Concurrent In-Memory Key-Value Store")
        print("=" * 60)
        print("Type 'help' for available commands or 'exit' to quit.\n")
        
        while self.running:
            try:
                command = input("minikv> ").strip()
                if not command:
                    continue
                
                self.execute_command(command)
            
            except KeyboardInterrupt:
                print("\nUse 'exit' to quit.")
            except EOFError:
                break
        
        print("\nGoodbye!")
    
    def execute_command(self, command: str):
        """
        Execute a CLI command.
        
        Args:
            command: The command string to execute
        """
        parts = command.split(maxsplit=2)
        if not parts:
            return
        
        cmd = parts[0].upper()
        
        try:
            if cmd == "HELP":
                self.cmd_help()
            
            elif cmd == "EXIT" or cmd == "QUIT":
                self.running = False
            
            elif cmd == "GET":
                if len(parts) < 2:
                    print("Usage: GET <key>")
                    return
                key = parts[1]
                value = self.router.get(key)
                if value is None:
                    print(f"(nil)")
                else:
                    print(json.dumps(value, indent=2))
            
            elif cmd == "SET":
                if len(parts) < 3:
                    print("Usage: SET <key> <value>")
                    return
                key = parts[1]
                try:
                    # Try to parse as JSON
                    value = json.loads(parts[2])
                except json.JSONDecodeError:
                    # If not JSON, treat as string
                    value = parts[2]
                
                self.router.set(key, value)
                print("OK")
            
            elif cmd == "DELETE" or cmd == "DEL":
                if len(parts) < 2:
                    print("Usage: DELETE <key>")
                    return
                key = parts[1]
                deleted = self.router.delete(key)
                print("1" if deleted else "0")
            
            elif cmd == "EXISTS":
                if len(parts) < 2:
                    print("Usage: EXISTS <key>")
                    return
                key = parts[1]
                exists = self.router.exists(key)
                print("1" if exists else "0")
            
            elif cmd == "KEYS":
                keys = self.router.keys()
                for i, key in enumerate(keys, 1):
                    print(f"{i}) {key}")
                if not keys:
                    print("(empty)")
            
            elif cmd == "VALUES":
                values = self.router.values()
                for i, value in enumerate(values, 1):
                    print(f"{i}) {json.dumps(value)}")
                if not values:
                    print("(empty)")
            
            elif cmd == "ITEMS":
                items = self.router.items()
                for i, (key, value) in enumerate(items, 1):
                    print(f"{i}) {key} => {json.dumps(value)}")
                if not items:
                    print("(empty)")
            
            elif cmd == "SIZE":
                size = self.router.size()
                print(f"(integer) {size}")
            
            elif cmd == "CLEAR":
                self.router.clear()
                print("OK")
            
            elif cmd == "CHECKPOINT":
                stats = self.router.checkpoint()
                print("Checkpoint complete:")
                print(json.dumps(stats, indent=2))
            
            elif cmd == "STATS":
                stats = self.router.get_stats()
                print(json.dumps(stats, indent=2))
            
            elif cmd == "UPDATE":
                if len(parts) < 2:
                    print("Usage: UPDATE <json_object>")
                    print("Example: UPDATE {\"key1\": \"value1\", \"key2\": 42}")
                    return
                try:
                    data = json.loads(parts[1])
                    if not isinstance(data, dict):
                        print("Error: UPDATE requires a JSON object")
                        return
                    self.router.update(data)
                    print(f"OK - Updated {len(data)} key(s)")
                except json.JSONDecodeError as e:
                    print(f"Error: Invalid JSON - {e}")
            
            else:
                print(f"Unknown command: {cmd}")
                print("Type 'help' for available commands.")
        
        except Exception as e:
            print(f"Error: {e}")
    
    def cmd_help(self):
        """Display help message."""
        help_text = """
Available Commands:
-------------------
  GET <key>              - Get value for a key
  SET <key> <value>      - Set a key-value pair (value can be JSON)
  DELETE <key>           - Delete a key
  EXISTS <key>           - Check if a key exists
  KEYS                   - List all keys
  VALUES                 - List all values
  ITEMS                  - List all key-value pairs
  SIZE                   - Get number of key-value pairs
  CLEAR                  - Clear all key-value pairs
  UPDATE <json_object>   - Batch update multiple keys
  CHECKPOINT             - Force a checkpoint
  STATS                  - Display system statistics
  HELP                   - Display this help message
  EXIT / QUIT            - Exit the CLI

Examples:
---------
  SET user:1 "John Doe"
  SET user:1 {"name": "John", "age": 30}
  GET user:1
  DELETE user:1
  UPDATE {"key1": "value1", "key2": 42, "key3": [1,2,3]}
  KEYS
  STATS
"""
        print(help_text)


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="MiniKV - Concurrent In-Memory Key-Value Store"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of worker threads (default: 4)"
    )
    parser.add_argument(
        "--no-persistence",
        action="store_true",
        help="Disable persistence"
    )
    parser.add_argument(
        "--no-wal",
        action="store_true",
        help="Disable write-ahead logging"
    )
    parser.add_argument(
        "--db",
        type=str,
        default="minikv.db",
        help="Database file path (default: minikv.db)"
    )
    parser.add_argument(
        "--wal",
        type=str,
        default="minikv.wal",
        help="WAL file path (default: minikv.wal)"
    )
    parser.add_argument(
        "--command",
        "-c",
        type=str,
        help="Execute a single command and exit"
    )
    
    args = parser.parse_args()
    
    # Create and start router
    router = Router(
        num_workers=args.workers,
        enable_persistence=not args.no_persistence,
        enable_wal=not args.no_wal,
        db_path=args.db,
        wal_path=args.wal
    )
    
    try:
        router.start()
        
        cli = MiniKVCLI(router)
        
        if args.command:
            # Execute single command and exit
            cli.execute_command(args.command)
        else:
            # Start interactive mode
            cli.start()
    
    finally:
        router.stop()


if __name__ == "__main__":
    main()

