"""Repository for Item CRUD operations."""
import sqlite3
from typing import List, Optional, Dict, Any
from datetime import date
import logging
from models.item import Item
from models.database import DatabasePool

logger = logging.getLogger(__name__)

class ItemRepository:
    """Repository pattern for Item CRUD operations with error handling."""

    # Safe mapping for ORDER BY columns to prevent SQL injection
    ORDER_BY_COLUMNS = {
        'expiry_date': 'expiry_date',
        'name': 'name',
        'quantity': 'quantity',
        'created_at': 'created_at',
        'updated_at': 'updated_at'
    }

    def __init__(self, pool: DatabasePool):
        """Initialize repository with database pool.

        Args:
            pool: Database connection pool
        """
        self.pool = pool

    def get_all(self, order_by: str = "expiry_date") -> List[Item]:
        """Get all items from database.

        Args:
            order_by: Column to order by (default: expiry_date)

        Returns:
            List of Item objects
        """
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()

                # Use safe mapping to prevent SQL injection
                order_column = self.ORDER_BY_COLUMNS.get(order_by, 'expiry_date')

                cursor.execute(f"SELECT * FROM items ORDER BY {order_column}")
                rows = cursor.fetchall()

                items = []
                for row in rows:
                    try:
                        items.append(self._row_to_item(row))
                    except Exception as e:
                        logger.error(f"Error converting row to Item: {e}")
                        continue

                return items

        except sqlite3.Error as e:
            logger.error(f"Database error getting all items: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting all items: {e}")
            return []
    
    def get_by_id(self, item_id: int) -> Optional[Item]:
        """Get item by ID.
        
        Args:
            item_id: Item ID
            
        Returns:
            Item object or None if not found
        """
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
                row = cursor.fetchone()
                
                if row:
                    return self._row_to_item(row)
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Database error getting item {item_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting item {item_id}: {e}")
            return None
    
    def get_expiring_soon(self, days: int = 3) -> List[Item]:
        """Get items expiring within specified days.

        Args:
            days: Number of days to check (default: 3)

        Returns:
            List of Item objects expiring soon
        """
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM items
                    WHERE expiry_date <= date('now', '+? days')
                    AND expiry_date >= date('now')
                    ORDER BY expiry_date
                """, (days,))

                rows = cursor.fetchall()
                items = []
                for row in rows:
                    try:
                        items.append(self._row_to_item(row))
                    except Exception as e:
                        logger.error(f"Error converting row to Item: {e}")
                        continue
                return items

        except sqlite3.Error as e:
            logger.error(f"Database error getting expiring items: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting expiring items: {e}")
            return []
    
    def get_expired(self) -> List[Item]:
        """Get expired items.

        Returns:
            List of expired Item objects
        """
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM items
                    WHERE expiry_date < date('now')
                    ORDER BY expiry_date DESC
                """)

                rows = cursor.fetchall()
                items = []
                for row in rows:
                    try:
                        items.append(self._row_to_item(row))
                    except Exception as e:
                        logger.error(f"Error converting row to Item: {e}")
                        continue
                return items

        except sqlite3.Error as e:
            logger.error(f"Database error getting expired items: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting expired items: {e}")
            return []
    
    def get_opened(self) -> List[Item]:
        """Get opened items.

        Returns:
            List of opened Item objects
        """
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM items
                    WHERE is_opened = 1
                    ORDER BY opened_date DESC
                """)

                rows = cursor.fetchall()
                items = []
                for row in rows:
                    try:
                        items.append(self._row_to_item(row))
                    except Exception as e:
                        logger.error(f"Error converting row to Item: {e}")
                        continue
                return items

        except sqlite3.Error as e:
            logger.error(f"Database error getting opened items: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting opened items: {e}")
            return []
    
    def search(self, query: str) -> List[Item]:
        """Search items by name.

        Args:
            query: Search query

        Returns:
            List of matching Item objects
        """
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM items
                    WHERE name LIKE ?
                    ORDER BY name
                """, (f"%{query}%",))

                rows = cursor.fetchall()
                items = []
                for row in rows:
                    try:
                        items.append(self._row_to_item(row))
                    except Exception as e:
                        logger.error(f"Error converting row to Item: {e}")
                        continue
                return items

        except sqlite3.Error as e:
            logger.error(f"Database error searching items: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error searching items: {e}")
            return []
    
    def create(self, item: Item) -> Optional[Item]:
        """Create new item.
        
        Args:
            item: Item object to create
            
        Returns:
            Created Item with ID or None on error
        """
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO items (name, expiry_date, barcode, quantity, is_opened, opened_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    item.name,
                    item.expiry_date.isoformat(),
                    item.barcode,
                    item.quantity,
                    int(item.is_opened),
                    item.opened_date.isoformat() if item.opened_date else None
                ))
                conn.commit()
                
                item.id = cursor.lastrowid
                logger.info(f"Created item: {item.name} (ID: {item.id})")
                return item
                
        except sqlite3.IntegrityError as e:
            logger.error(f"Integrity error creating item: {e}")
            return None
        except sqlite3.Error as e:
            logger.error(f"Database error creating item: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating item: {e}")
            return None
    
    def update(self, item: Item) -> bool:
        """Update existing item.
        
        Args:
            item: Item object with updated data
            
        Returns:
            True if successful, False otherwise
        """
        if not item.id:
            logger.error("Cannot update item without ID")
            return False
        
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE items 
                    SET name = ?, expiry_date = ?, barcode = ?, 
                        quantity = ?, is_opened = ?, opened_date = ?
                    WHERE id = ?
                """, (
                    item.name,
                    item.expiry_date.isoformat(),
                    item.barcode,
                    item.quantity,
                    int(item.is_opened),
                    item.opened_date.isoformat() if item.opened_date else None,
                    item.id
                ))
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"Updated item: {item.name} (ID: {item.id})")
                    return True
                else:
                    logger.warning(f"No item found with ID: {item.id}")
                    return False
                    
        except sqlite3.IntegrityError as e:
            logger.error(f"Integrity error updating item {item.id}: {e}")
            return False
        except sqlite3.Error as e:
            logger.error(f"Database error updating item {item.id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error updating item {item.id}: {e}")
            return False
    
    def delete(self, item_id: int) -> bool:
        """Delete item by ID.
        
        Args:
            item_id: Item ID to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"Deleted item with ID: {item_id}")
                    return True
                else:
                    logger.warning(f"No item found with ID: {item_id}")
                    return False
                    
        except sqlite3.IntegrityError as e:
            logger.error(f"Integrity error deleting item {item_id}: {e}")
            return False
        except sqlite3.Error as e:
            logger.error(f"Database error deleting item {item_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting item {item_id}: {e}")
            return False
    
    def toggle_opened_status(self, item_id: int) -> bool:
        """Toggle opened status of an item.
        
        Args:
            item_id: Item ID
            
        Returns:
            True if successful, False otherwise
        """
        item = self.get_by_id(item_id)
        if not item:
            logger.warning(f"Item not found with ID: {item_id}")
            return False
        
        # Toggle status
        item.is_opened = not item.is_opened
        if item.is_opened and not item.opened_date:
            item.opened_date = date.today()
        elif not item.is_opened:
            item.opened_date = None
        
        return self.update(item)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get inventory statistics.
        
        Returns:
            Dictionary with statistics
        """
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                
                # Total items and quantity
                cursor.execute("SELECT COUNT(*), SUM(quantity) FROM items")
                total_items, total_quantity = cursor.fetchone()
                
                # Expired items
                cursor.execute("SELECT COUNT(*) FROM items WHERE expiry_date < date('now')")
                expired_count = cursor.fetchone()[0]
                
                # Expiring soon (within 3 days)
                cursor.execute("""
                    SELECT COUNT(*) FROM items 
                    WHERE expiry_date <= date('now', '+3 days')
                    AND expiry_date >= date('now')
                """)
                expiring_soon_count = cursor.fetchone()[0]
                
                # Opened items
                cursor.execute("SELECT COUNT(*) FROM items WHERE is_opened = 1")
                opened_count = cursor.fetchone()[0]
                
                return {
                    "total_items": total_items or 0,
                    "total_quantity": total_quantity or 0,
                    "expired_count": expired_count or 0,
                    "expiring_soon_count": expiring_soon_count or 0,
                    "opened_count": opened_count or 0,
                    "fresh_count": (total_items or 0) - (expired_count or 0) - (expiring_soon_count or 0)
                }
                
        except sqlite3.Error as e:
            logger.error(f"Database error getting statistics: {e}")
            return {
                "total_items": 0,
                "total_quantity": 0,
                "expired_count": 0,
                "expiring_soon_count": 0,
                "opened_count": 0,
                "fresh_count": 0
            }
    
    def _row_to_item(self, row: sqlite3.Row) -> Item:
        """Convert database row to Item object.

        Args:
            row: Database row

        Returns:
            Item object

        Raises:
            ValueError: If row data is corrupted or invalid
        """
        # Parse expiry date with error handling
        try:
            expiry_date = date.fromisoformat(row['expiry_date'])
        except (ValueError, TypeError) as e:
            logger.error(f"Corrupted expiry date for item {row['id']}: {row['expiry_date']}")
            # Use today as fallback for corrupted data
            expiry_date = date.today()

        # Parse opened date with error handling
        opened_date = None
        if row['opened_date']:
            try:
                opened_date = date.fromisoformat(row['opened_date'])
            except (ValueError, TypeError) as e:
                logger.error(f"Corrupted opened date for item {row['id']}: {row['opened_date']}")
                # Leave as None for corrupted data

        return Item(
            id=row['id'],
            name=row['name'],
            expiry_date=expiry_date,
            barcode=row['barcode'],
            quantity=row['quantity'] or 1,
            is_opened=bool(row['is_opened']),
            opened_date=opened_date
        )