"""
Persistence layer for durable storage using SQLite or PostgreSQL.
Provides optional persistence to survive crashes and restarts.
"""

import json
import sqlite3
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod


class PersistenceBackend(ABC):
    """Abstract base class for persistence backends."""
    
    @abstractmethod
    def connect(self):
        """Establish connection to the database."""
        pass
    
    @abstractmethod
    def disconnect(self):
        """Close connection to the database."""
        pass
    
    @abstractmethod
    def save(self, key: str, value: Any):
        """Save a key-value pair."""
        pass
    
    @abstractmethod
    def load(self, key: str) -> Optional[Any]:
        """Load a value by key."""
        pass
    
    @abstractmethod
    def delete(self, key: str):
        """Delete a key-value pair."""
        pass
    
    @abstractmethod
    def load_all(self) -> Dict[str, Any]:
        """Load all key-value pairs."""
        pass
    
    @abstractmethod
    def clear(self):
        """Clear all data."""
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if a key exists."""
        pass


class SQLitePersistence(PersistenceBackend):
    """
    SQLite-based persistence backend.
    Suitable for single-node deployments.
    """
    
    def __init__(self, db_path: str = "minikv.db"):
        """
        Initialize SQLite persistence.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.connect()
        self._create_table()
    
    def connect(self):
        """Establish connection to SQLite database."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
    
    def disconnect(self):
        """Close SQLite connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def _create_table(self):
        """Create the key-value table if it doesn't exist."""
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            # Create index for faster lookups
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_key ON kv_store(key)
            """)
    
    def save(self, key: str, value: Any):
        """
        Save a key-value pair to SQLite.
        
        Args:
            key: The key to save
            value: The value to save (will be JSON-serialized)
        """
        value_json = json.dumps(value)
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
                (key, value_json)
            )
    
    def load(self, key: str) -> Optional[Any]:
        """
        Load a value by key from SQLite.
        
        Args:
            key: The key to load
            
        Returns:
            The value if found, None otherwise
        """
        cursor = self.conn.execute(
            "SELECT value FROM kv_store WHERE key = ?",
            (key,)
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
        return None
    
    def delete(self, key: str):
        """
        Delete a key-value pair from SQLite.
        
        Args:
            key: The key to delete
        """
        with self.conn:
            self.conn.execute("DELETE FROM kv_store WHERE key = ?", (key,))
    
    def load_all(self) -> Dict[str, Any]:
        """
        Load all key-value pairs from SQLite.
        
        Returns:
            Dictionary containing all key-value pairs
        """
        cursor = self.conn.execute("SELECT key, value FROM kv_store")
        result = {}
        for row in cursor:
            key = row[0]
            value = json.loads(row[1])
            result[key] = value
        return result
    
    def clear(self):
        """Clear all data from SQLite."""
        with self.conn:
            self.conn.execute("DELETE FROM kv_store")
    
    def exists(self, key: str) -> bool:
        """
        Check if a key exists in SQLite.
        
        Args:
            key: The key to check
            
        Returns:
            True if the key exists, False otherwise
        """
        cursor = self.conn.execute(
            "SELECT 1 FROM kv_store WHERE key = ? LIMIT 1",
            (key,)
        )
        return cursor.fetchone() is not None
    
    def get_size(self) -> int:
        """Get the number of key-value pairs stored."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM kv_store")
        return cursor.fetchone()[0]


class PostgreSQLPersistence(PersistenceBackend):
    """
    PostgreSQL-based persistence backend.
    Suitable for distributed deployments (requires psycopg2).
    """
    
    def __init__(self, connection_string: str):
        """
        Initialize PostgreSQL persistence.
        
        Args:
            connection_string: PostgreSQL connection string
                e.g., "host=localhost dbname=minikv user=postgres password=pass"
        """
        self.connection_string = connection_string
        self.conn = None
        
        try:
            import psycopg2
            self.psycopg2 = psycopg2
        except ImportError:
            raise ImportError(
                "PostgreSQL support requires psycopg2. "
                "Install it with: pip install psycopg2-binary"
            )
        
        self.connect()
        self._create_table()
    
    def connect(self):
        """Establish connection to PostgreSQL."""
        self.conn = self.psycopg2.connect(self.connection_string)
    
    def disconnect(self):
        """Close PostgreSQL connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def _create_table(self):
        """Create the key-value table if it doesn't exist."""
        with self.conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_key ON kv_store(key)
            """)
            self.conn.commit()
    
    def save(self, key: str, value: Any):
        """Save a key-value pair to PostgreSQL."""
        value_json = json.dumps(value)
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO kv_store (key, value) VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """,
                (key, value_json)
            )
            self.conn.commit()
    
    def load(self, key: str) -> Optional[Any]:
        """Load a value by key from PostgreSQL."""
        with self.conn.cursor() as cursor:
            cursor.execute(
                "SELECT value FROM kv_store WHERE key = %s",
                (key,)
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
        return None
    
    def delete(self, key: str):
        """Delete a key-value pair from PostgreSQL."""
        with self.conn.cursor() as cursor:
            cursor.execute("DELETE FROM kv_store WHERE key = %s", (key,))
            self.conn.commit()
    
    def load_all(self) -> Dict[str, Any]:
        """Load all key-value pairs from PostgreSQL."""
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT key, value FROM kv_store")
            result = {}
            for row in cursor:
                key = row[0]
                value = json.loads(row[1])
                result[key] = value
        return result
    
    def clear(self):
        """Clear all data from PostgreSQL."""
        with self.conn.cursor() as cursor:
            cursor.execute("DELETE FROM kv_store")
            self.conn.commit()
    
    def exists(self, key: str) -> bool:
        """Check if a key exists in PostgreSQL."""
        with self.conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM kv_store WHERE key = %s LIMIT 1",
                (key,)
            )
            return cursor.fetchone() is not None
    
    def get_size(self) -> int:
        """Get the number of key-value pairs stored."""
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM kv_store")
            return cursor.fetchone()[0]

