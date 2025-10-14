"""Repository for barcode lookup operations."""
import sqlite3
from typing import List, Optional, Dict, Any, Tuple
import logging
from datetime import datetime
from models.database import DatabasePool

logger = logging.getLogger(__name__)

class BarcodeRepository:
    """Repository for barcode lookups with caching."""
    
    def __init__(self, pool: DatabasePool):
        """Initialize repository with database pool.
        
        Args:
            pool: Database connection pool
        """
        self.pool = pool
    
    def lookup(self, barcode: str) -> Optional[Dict[str, Any]]:
        """Lookup product information by barcode.
        
        Args:
            barcode: Barcode to lookup
            
        Returns:
            Dictionary with product info or None if not found
        """
        if not barcode:
            return None
        
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                
                # Update last_used timestamp when accessed
                cursor.execute("""
                    UPDATE barcode_lookup 
                    SET last_used = CURRENT_TIMESTAMP 
                    WHERE barcode = ?
                """, (barcode,))
                
                # Get barcode info
                cursor.execute("""
                    SELECT barcode, name, brand, category 
                    FROM barcode_lookup 
                    WHERE barcode = ?
                """, (barcode,))
                
                row = cursor.fetchone()
                if row:
                    conn.commit()
                    return {
                        "barcode": row['barcode'],
                        "name": row['name'],
                        "brand": row['brand'],
                        "category": row['category'],
                        "source": "local"
                    }
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Database error looking up barcode {barcode}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error looking up barcode {barcode}: {e}")
            return None
    
    def save(self, barcode: str, name: str, brand: str = None, category: str = None) -> bool:
        """Save barcode-name mapping to cache.
        
        Args:
            barcode: Barcode to save
            name: Product name
            brand: Product brand (optional)
            category: Product category (optional)
            
        Returns:
            True if successful, False otherwise
        """
        if not barcode or not name:
            logger.error("Barcode and name are required")
            return False
        
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO barcode_lookup 
                    (barcode, name, brand, category, last_used) 
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (barcode, name, brand, category))
                conn.commit()
                
                logger.info(f"Saved barcode {barcode}: {name}")
                return cursor.rowcount > 0
                
        except sqlite3.IntegrityError as e:
            logger.error(f"Integrity error saving barcode {barcode}: {e}")
            return False
        except sqlite3.Error as e:
            logger.error(f"Database error saving barcode {barcode}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving barcode {barcode}: {e}")
            return False
    
    def delete(self, barcode: str) -> bool:
        """Delete barcode from cache.
        
        Args:
            barcode: Barcode to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM barcode_lookup WHERE barcode = ?", (barcode,))
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"Deleted barcode: {barcode}")
                    return True
                return False
                
        except sqlite3.Error as e:
            logger.error(f"Database error deleting barcode {barcode}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting barcode {barcode}: {e}")
            return False
    
    def get_produce_items(self) -> List[Tuple[str, str]]:
        """Get all produce items (non-barcoded items).
        
        Returns:
            List of tuples (barcode, name) for produce items
        """
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT barcode, name 
                    FROM barcode_lookup 
                    WHERE barcode LIKE 'PRODUCE_%' 
                    ORDER BY name
                """)
                
                rows = cursor.fetchall()
                return [(row['barcode'], row['name']) for row in rows]
                
        except sqlite3.Error as e:
            logger.error(f"Database error getting produce items: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting produce items: {e}")
            return []
    
    def get_all_cached(self) -> List[Dict[str, Any]]:
        """Get all cached barcodes.
        
        Returns:
            List of dictionaries with barcode info
        """
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT barcode, name, brand, category, created_at, last_used
                    FROM barcode_lookup 
                    ORDER BY last_used DESC
                """)
                
                rows = cursor.fetchall()
                return [
                    {
                        "barcode": row['barcode'],
                        "name": row['name'],
                        "brand": row['brand'],
                        "category": row['category'],
                        "created_at": row['created_at'],
                        "last_used": row['last_used']
                    }
                    for row in rows
                ]
                
        except sqlite3.Error as e:
            logger.error(f"Database error getting all cached barcodes: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting all cached barcodes: {e}")
            return []
    
    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search cached barcodes by name.
        
        Args:
            query: Search query
            
        Returns:
            List of matching barcode entries
        """
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT barcode, name, brand, category 
                    FROM barcode_lookup 
                    WHERE name LIKE ? OR brand LIKE ?
                    ORDER BY name
                """, (f"%{query}%", f"%{query}%"))
                
                rows = cursor.fetchall()
                return [
                    {
                        "barcode": row['barcode'],
                        "name": row['name'],
                        "brand": row['brand'],
                        "category": row['category']
                    }
                    for row in rows
                ]
                
        except sqlite3.Error as e:
            logger.error(f"Database error searching barcodes: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error searching barcodes: {e}")
            return []
    
    def get_frequently_used(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get frequently used barcodes.
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of frequently used barcode entries
        """
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT barcode, name, brand, category, 
                           COUNT(*) as usage_count
                    FROM barcode_lookup 
                    WHERE barcode NOT LIKE 'PRODUCE_%'
                    GROUP BY barcode
                    ORDER BY last_used DESC
                    LIMIT ?
                """, (limit,))
                
                rows = cursor.fetchall()
                return [
                    {
                        "barcode": row['barcode'],
                        "name": row['name'],
                        "brand": row['brand'],
                        "category": row['category']
                    }
                    for row in rows
                ]
                
        except sqlite3.Error as e:
            logger.error(f"Database error getting frequently used barcodes: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting frequently used barcodes: {e}")
            return []
    
    def cleanup_old_entries(self, days: int = 365) -> int:
        """Clean up old unused barcode entries.
        
        Args:
            days: Delete entries not used in this many days
            
        Returns:
            Number of entries deleted
        """
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM barcode_lookup 
                    WHERE last_used < datetime('now', '-? days')
                    AND barcode NOT LIKE 'PRODUCE_%'
                """, (days,))
                conn.commit()
                
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} old barcode entries")
                return deleted_count
                
        except sqlite3.Error as e:
            logger.error(f"Database error cleaning up old entries: {e}")
            return 0
        except Exception as e:
            logger.error(f"Unexpected error cleaning up old entries: {e}")
            return 0
    
    def get_statistics(self) -> Dict[str, int]:
        """Get barcode cache statistics.
        
        Returns:
            Dictionary with statistics
        """
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                
                # Total cached entries
                cursor.execute("SELECT COUNT(*) FROM barcode_lookup")
                total_count = cursor.fetchone()[0]
                
                # Produce items
                cursor.execute("SELECT COUNT(*) FROM barcode_lookup WHERE barcode LIKE 'PRODUCE_%'")
                produce_count = cursor.fetchone()[0]
                
                # Regular barcodes
                regular_count = total_count - produce_count
                
                # Recently used (last 30 days)
                cursor.execute("""
                    SELECT COUNT(*) FROM barcode_lookup 
                    WHERE last_used > datetime('now', '-30 days')
                """)
                recent_count = cursor.fetchone()[0]
                
                return {
                    "total_cached": total_count,
                    "produce_items": produce_count,
                    "regular_barcodes": regular_count,
                    "recently_used": recent_count
                }
                
        except sqlite3.Error as e:
            logger.error(f"Database error getting barcode statistics: {e}")
            return {
                "total_cached": 0,
                "produce_items": 0,
                "regular_barcodes": 0,
                "recently_used": 0
            }