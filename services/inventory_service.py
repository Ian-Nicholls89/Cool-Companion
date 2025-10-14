"""High-level service for inventory management."""
import logging
from typing import Dict, Any, List, Optional
from datetime import date
from models.item import Item
from repositories.item_repository import ItemRepository
from services.barcode_service import BarcodeService, BarcodeNotFoundError
from services.shopping_service import ShoppingListService

logger = logging.getLogger(__name__)

class InventoryError(Exception):
    """Exception for inventory operations."""
    pass

class InventoryService:
    """High-level service for inventory management operations."""
    
    def __init__(
        self,
        item_repository: ItemRepository,
        barcode_service: BarcodeService,
        shopping_service: ShoppingListService
    ):
        """Initialize inventory service.
        
        Args:
            item_repository: Repository for item operations
            barcode_service: Service for barcode operations
            shopping_service: Service for shopping list operations
        """
        self.item_repository = item_repository
        self.barcode_service = barcode_service
        self.shopping_service = shopping_service
    
    async def add_item_with_barcode(
        self,
        barcode: str,
        expiry_date: date,
        quantity: int = 1
    ) -> Dict[str, Any]:
        """Add item using barcode lookup.
        
        Args:
            barcode: Product barcode
            expiry_date: Expiry date
            quantity: Quantity to add
            
        Returns:
            Dictionary with operation result
        """
        try:
            # Lookup product info
            product_info = await self.barcode_service.lookup_product(barcode)
            
            # Create item
            item = Item(
                name=product_info['name'],
                expiry_date=expiry_date,
                barcode=barcode,
                quantity=quantity
            )
            
            # Save to database
            saved_item = self.item_repository.create(item)
            
            if saved_item:
                logger.info(f"Added item with barcode {barcode}: {product_info['name']}")
                return {
                    "success": True,
                    "item": saved_item.to_dict(),
                    "product_info": product_info
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to save item to database"
                }
                
        except BarcodeNotFoundError:
            logger.warning(f"Product not found for barcode: {barcode}")
            return {
                "success": False,
                "error": "Product not found. Please enter details manually.",
                "barcode": barcode
            }
        except ValueError as e:
            return {
                "success": False,
                "error": f"Invalid data: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Failed to add item with barcode: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def add_item_with_barcode_sync(
        self,
        barcode: str,
        expiry_date: date,
        quantity: int = 1
    ) -> Dict[str, Any]:
        """Synchronous version of add_item_with_barcode.
        
        Args:
            barcode: Product barcode
            expiry_date: Expiry date
            quantity: Quantity to add
            
        Returns:
            Dictionary with operation result
        """
        try:
            # Lookup product info
            product_info = self.barcode_service.lookup_product_sync(barcode)
            
            if not product_info:
                return {
                    "success": False,
                    "error": "Product not found. Please enter details manually.",
                    "barcode": barcode
                }
            
            # Create item
            item = Item(
                name=product_info['name'],
                expiry_date=expiry_date,
                barcode=barcode,
                quantity=quantity
            )
            
            # Save to database
            saved_item = self.item_repository.create(item)
            
            if saved_item:
                return {
                    "success": True,
                    "item": saved_item.to_dict(),
                    "product_info": product_info
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to save item to database"
                }
                
        except Exception as e:
            logger.error(f"Failed to add item with barcode (sync): {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def add_item(self, item: Item) -> Optional[Item]:
        """Add new item to inventory.
        
        Args:
            item: Item to add
            
        Returns:
            Created item or None on error
        """
        try:
            return self.item_repository.create(item)
        except Exception as e:
            logger.error(f"Failed to add item: {e}")
            return None
    
    def update_item(self, item: Item) -> bool:
        """Update existing item.
        
        Args:
            item: Item with updated data
            
        Returns:
            True if successful
        """
        try:
            return self.item_repository.update(item)
        except Exception as e:
            logger.error(f"Failed to update item: {e}")
            return False
    
    def delete_item(self, item_id: int) -> bool:
        """Delete item from inventory.
        
        Args:
            item_id: Item ID to delete
            
        Returns:
            True if successful
        """
        try:
            return self.item_repository.delete(item_id)
        except Exception as e:
            logger.error(f"Failed to delete item: {e}")
            return False
    
    async def delete_and_restock(
        self,
        item_id: int,
        add_to_shopping: bool = False
    ) -> Dict[str, Any]:
        """Delete item and optionally add to shopping list.
        
        Args:
            item_id: Item ID to delete
            add_to_shopping: Whether to add to shopping list
            
        Returns:
            Dictionary with operation result
        """
        try:
            # Get item details
            item = self.item_repository.get_by_id(item_id)
            if not item:
                return {
                    "success": False,
                    "error": "Item not found"
                }
            
            # Delete from inventory
            if not self.item_repository.delete(item_id):
                return {
                    "success": False,
                    "error": "Failed to delete item"
                }
            
            # Add to shopping list if requested
            if add_to_shopping and self.shopping_service.is_available():
                try:
                    await self.shopping_service.add_item(item.name, item.quantity)
                    logger.info(f"Added {item.name} to shopping list")
                    return {
                        "success": True,
                        "message": f"Item deleted and added to shopping list",
                        "item": item.to_dict()
                    }
                except Exception as e:
                    logger.error(f"Failed to add to shopping list: {e}")
                    return {
                        "success": True,
                        "message": "Item deleted but failed to add to shopping list",
                        "warning": str(e),
                        "item": item.to_dict()
                    }
            
            return {
                "success": True,
                "message": "Item deleted successfully",
                "item": item.to_dict()
            }
            
        except Exception as e:
            logger.error(f"Failed to delete and restock item: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def delete_and_restock_sync(
        self,
        item_id: int,
        add_to_shopping: bool = False
    ) -> bool:
        """Synchronous version of delete_and_restock.
        
        Args:
            item_id: Item ID to delete
            add_to_shopping: Whether to add to shopping list
            
        Returns:
            True if successful
        """
        try:
            # Get item details
            item = self.item_repository.get_by_id(item_id)
            if not item:
                return False
            
            # Delete from inventory
            if not self.item_repository.delete(item_id):
                return False
            
            # Add to shopping list if requested
            if add_to_shopping and self.shopping_service.is_available():
                self.shopping_service.add_item_sync(item.name, item.quantity)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete and restock (sync): {e}")
            return False
    
    def toggle_opened_status(self, item_id: int) -> bool:
        """Toggle opened status of an item.
        
        Args:
            item_id: Item ID
            
        Returns:
            True if successful
        """
        try:
            return self.item_repository.toggle_opened_status(item_id)
        except Exception as e:
            logger.error(f"Failed to toggle opened status: {e}")
            return False
    
    def get_all_items(self, order_by: str = "expiry_date") -> List[Item]:
        """Get all items from inventory.
        
        Args:
            order_by: Column to order by
            
        Returns:
            List of items
        """
        return self.item_repository.get_all(order_by)
    
    def get_item_by_id(self, item_id: int) -> Optional[Item]:
        """Get item by ID.
        
        Args:
            item_id: Item ID
            
        Returns:
            Item or None if not found
        """
        return self.item_repository.get_by_id(item_id)
    
    def get_expiring_items(self, days: int = 3) -> List[Item]:
        """Get items expiring within specified days.
        
        Args:
            days: Number of days to check
            
        Returns:
            List of expiring items
        """
        return self.item_repository.get_expiring_soon(days)
    
    def get_expired_items(self) -> List[Item]:
        """Get expired items.
        
        Returns:
            List of expired items
        """
        return self.item_repository.get_expired()
    
    def get_opened_items(self) -> List[Item]:
        """Get opened items.
        
        Returns:
            List of opened items
        """
        return self.item_repository.get_opened()
    
    def search_items(self, query: str) -> List[Item]:
        """Search items by name.
        
        Args:
            query: Search query
            
        Returns:
            List of matching items
        """
        return self.item_repository.search(query)
    
    def get_inventory_stats(self) -> Dict[str, Any]:
        """Get comprehensive inventory statistics.
        
        Returns:
            Dictionary with statistics
        """
        try:
            # Get basic stats from repository
            stats = self.item_repository.get_statistics()
            
            # Add additional calculations
            all_items = self.item_repository.get_all()
            
            # Calculate value categories
            categories = {
                "Fresh": 0,
                "Expiring Soon": 0,
                "Expired": 0,
                "Opened": 0
            }
            
            for item in all_items:
                if item.is_expired:
                    categories["Expired"] += 1
                elif item.is_expiring_soon:
                    categories["Expiring Soon"] += 1
                elif item.is_opened:
                    categories["Opened"] += 1
                else:
                    categories["Fresh"] += 1
            
            # Calculate waste metrics
            waste_percentage = 0
            if stats["total_items"] > 0:
                waste_percentage = (stats["expired_count"] / stats["total_items"]) * 100
            
            return {
                **stats,
                "categories": categories,
                "waste_percentage": round(waste_percentage, 1),
                "average_quantity": round(stats["total_quantity"] / max(stats["total_items"], 1), 1)
            }
            
        except Exception as e:
            logger.error(f"Failed to get inventory stats: {e}")
            return {
                "total_items": 0,
                "total_quantity": 0,
                "expired_count": 0,
                "expiring_soon_count": 0,
                "opened_count": 0,
                "fresh_count": 0,
                "categories": {},
                "waste_percentage": 0,
                "average_quantity": 0
            }
    
    def get_produce_items(self) -> List[tuple[str, str]]:
        """Get available produce items.
        
        Returns:
            List of tuples (barcode, name)
        """
        return self.barcode_service.get_produce_items()
    
    def validate_item_data(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate item data before creating.
        
        Args:
            item_data: Dictionary with item data
            
        Returns:
            Dictionary with validation result
        """
        errors = []
        
        # Validate name
        if not item_data.get('name'):
            errors.append("Item name is required")
        elif len(item_data['name']) > 100:
            errors.append("Item name too long (max 100 characters)")
        
        # Validate expiry date
        if not item_data.get('expiry_date'):
            errors.append("Expiry date is required")
        else:
            try:
                if isinstance(item_data['expiry_date'], str):
                    expiry = date.fromisoformat(item_data['expiry_date'])
                else:
                    expiry = item_data['expiry_date']
                
                # Warning for past dates
                if expiry < date.today():
                    errors.append("Warning: Expiry date is in the past")
            except (ValueError, TypeError):
                errors.append("Invalid expiry date format")
        
        # Validate quantity
        if 'quantity' in item_data:
            try:
                quantity = int(item_data['quantity'])
                if quantity < 1:
                    errors.append("Quantity must be at least 1")
                elif quantity > 999:
                    errors.append("Quantity too large (max 999)")
            except (ValueError, TypeError):
                errors.append("Invalid quantity")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }