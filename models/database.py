"""Database connection pool and management."""
import sqlite3
from contextlib import contextmanager
from queue import Queue
import threading
import os
from typing import Generator
from config.settings import settings

class DatabasePool:
    """Connection pool for SQLite database with thread safety."""
    
    def __init__(self, database_path: str = None, pool_size: int = None):
        """Initialize database connection pool.
        
        Args:
            database_path: Path to SQLite database file
            pool_size: Number of connections in pool
        """
        self.database_path = database_path or settings.get_database_path()
        self.pool_size = pool_size or settings.connection_pool_size
        self._connections: Queue = Queue(maxsize=self.pool_size)
        self._lock = threading.Lock()
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize connection pool with configured connections."""
        # Ensure database directory exists
        db_dir = os.path.dirname(self.database_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        # Create connections
        for _ in range(self.pool_size):
            conn = sqlite3.connect(
                self.database_path,
                check_same_thread=False,
                timeout=30.0  # Increased timeout for better concurrency
            )
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode = WAL")
            # Set busy timeout
            conn.execute("PRAGMA busy_timeout = 30000")
            # Set row factory for dict-like access
            conn.row_factory = sqlite3.Row
            # Add to pool
            self._connections.put(conn)
    
    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get connection from pool with context manager.
        
        Yields:
            sqlite3.Connection: Database connection
        """
        conn = self._connections.get(block=True)
        try:
            yield conn
        except Exception as e:
            # Rollback on error
            conn.rollback()
            raise e
        finally:
            # Return connection to pool
            self._connections.put(conn)
    
    def execute_script(self, script: str):
        """Execute SQL script (for migrations/setup).
        
        Args:
            script: SQL script to execute
        """
        with self.get_connection() as conn:
            conn.executescript(script)
            conn.commit()
    
    def close_all(self):
        """Close all connections in pool."""
        with self._lock:
            while not self._connections.empty():
                conn = self._connections.get()
                conn.close()
    
    def __del__(self):
        """Cleanup connections on deletion."""
        self.close_all()

# Create global database pool instance
db_pool = DatabasePool()

def init_database():
    """Initialize database with required tables and indexes."""
    
    create_tables_sql = """
    -- Items table with all fields
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        expiry_date DATE NOT NULL,
        barcode TEXT,
        quantity INTEGER DEFAULT 1 CHECK(quantity > 0),
        is_opened INTEGER DEFAULT 0,
        opened_date DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Barcode lookup table for caching
    CREATE TABLE IF NOT EXISTS barcode_lookup (
        barcode TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        brand TEXT,
        category TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Create indexes for better performance
    CREATE INDEX IF NOT EXISTS idx_items_expiry_date 
        ON items(expiry_date);
    CREATE INDEX IF NOT EXISTS idx_items_barcode 
        ON items(barcode);
    CREATE INDEX IF NOT EXISTS idx_items_is_opened 
        ON items(is_opened);
    CREATE INDEX IF NOT EXISTS idx_items_status 
        ON items(is_opened, expiry_date);
    
    -- Trigger to update updated_at timestamp
    CREATE TRIGGER IF NOT EXISTS update_items_timestamp 
    AFTER UPDATE ON items
    BEGIN
        UPDATE items SET updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.id;
    END;
    """
    
    # Execute initialization script
    db_pool.execute_script(create_tables_sql)
    
    # Initialize produce items
    _initialize_produce_items()

def _initialize_produce_items():
    """Initialize common produce items in barcode lookup."""
    
    produce_items = [
        ('PRODUCE_APPLE', 'Apples', None, 'Produce'),
        ('PRODUCE_BANANA', 'Bananas', None, 'Produce'),
        ('PRODUCE_ORANGE', 'Oranges', None, 'Produce'),
        ('PRODUCE_TOMATO', 'Tomatoes', None, 'Produce'),
        ('PRODUCE_POTATO', 'Potatoes', None, 'Produce'),
        ('PRODUCE_CARROT', 'Carrots', None, 'Produce'),
        ('PRODUCE_ONION', 'Onions', None, 'Produce'),
        ('PRODUCE_CUCUMBER', 'Cucumber', None, 'Produce'),
        ('PRODUCE_LETTUCE', 'Lettuce', None, 'Produce'),
        ('PRODUCE_PEPPER', 'Bell Peppers', None, 'Produce'),
        ('PRODUCE_BROCCOLI', 'Broccoli', None, 'Produce'),
        ('PRODUCE_CAULIFLOWER', 'Cauliflower', None, 'Produce'),
        ('PRODUCE_MUSHROOM', 'Mushrooms', None, 'Produce'),
        ('PRODUCE_COURGETTE', 'Courgettes', None, 'Produce'),
        ('PRODUCE_AUBERGINE', 'Aubergine', None, 'Produce'),
        ('PRODUCE_LEEK', 'Leeks', None, 'Produce'),
        ('PRODUCE_CELERY', 'Celery', None, 'Produce'),
        ('PRODUCE_PARSNIP', 'Parsnips', None, 'Produce'),
        ('PRODUCE_SWEDE', 'Swede', None, 'Produce'),
        ('PRODUCE_CABBAGE', 'Cabbage', None, 'Produce'),
        ('PRODUCE_SPROUTS', 'Brussels Sprouts', None, 'Produce'),
        ('PRODUCE_PEAR', 'Pears', None, 'Produce'),
        ('PRODUCE_GRAPES', 'Grapes', None, 'Produce'),
        ('PRODUCE_STRAWBERRY', 'Strawberries', None, 'Produce'),
        ('PRODUCE_BLUEBERRY', 'Blueberries', None, 'Produce'),
        ('PRODUCE_RASPBERRY', 'Raspberries', None, 'Produce'),
        ('PRODUCE_MELON', 'Melon', None, 'Produce'),
        ('PRODUCE_PINEAPPLE', 'Pineapple', None, 'Produce'),
        ('PRODUCE_MANGO', 'Mango', None, 'Produce'),
        ('PRODUCE_AVOCADO', 'Avocado', None, 'Produce'),
    ]
    
    with db_pool.get_connection() as conn:
        cursor = conn.cursor()
        
        # Check if produce items already exist
        cursor.execute("SELECT COUNT(*) FROM barcode_lookup WHERE barcode LIKE 'PRODUCE_%'")
        count = cursor.fetchone()[0]
        
        if count == 0:
            # Insert produce items
            cursor.executemany(
                """INSERT INTO barcode_lookup (barcode, name, brand, category) 
                   VALUES (?, ?, ?, ?)""",
                produce_items
            )
            conn.commit()