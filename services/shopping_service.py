"""Service for shopping list integration with Bring! API."""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from python_bring_api.bring import Bring
from python_bring_api.types import BringListItemDetails
from config.settings import settings

logger = logging.getLogger(__name__)

class ShoppingListError(Exception):
    """Exception for shopping list operations."""
    pass

class ShoppingListService:
    """Service for managing shopping list integration."""
    
    def __init__(self, settings=None):
        """Initialize shopping list service.
        
        Args:
            settings: Application settings
        """
        self.settings = settings or globals()['settings']
        self.bring_client = None
        self._authenticated = False
        self._lists_cache = None
        self._cache_time = None
        self._cache_duration = 300  # 5 minutes cache
    
    async def authenticate(self) -> bool:
        """Authenticate with Bring API.
        
        Returns:
            True if authentication successful
        """
        if not self.settings.enable_shopping_list:
            logger.info("Shopping list feature is disabled")
            return False
        
        if not self.settings.bring_email or not self.settings.bring_password:
            logger.error("Bring credentials not configured")
            return False
        
        if self._authenticated:
            return True
        
        try:
            self.bring_client = Bring(
                self.settings.bring_email,
                self.settings.bring_password
            )
            
            # Run login in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.bring_client.login)
            
            self._authenticated = True
            logger.info("Successfully authenticated with Bring")
            return True
            
        except Exception as e:
            logger.error(f"Bring authentication failed: {e}")
            self._authenticated = False
            return False
    
    def authenticate_sync(self) -> bool:
        """Synchronous version of authenticate.
        
        Returns:
            True if authentication successful
        """
        if not self.settings.enable_shopping_list:
            return False
        
        if not self.settings.bring_email or not self.settings.bring_password:
            return False
        
        if self._authenticated:
            return True
        
        try:
            self.bring_client = Bring(
                self.settings.bring_email,
                self.settings.bring_password
            )
            self.bring_client.login()
            self._authenticated = True
            logger.info("Successfully authenticated with Bring (sync)")
            return True
            
        except Exception as e:
            logger.error(f"Bring authentication failed (sync): {e}")
            self._authenticated = False
            return False
    
    async def add_item(self, item_name: str, quantity: int = 1) -> bool:
        """Add item to shopping list.
        
        Args:
            item_name: Name of the item
            quantity: Quantity to add
            
        Returns:
            True if successful
            
        Raises:
            ShoppingListError: If operation fails
        """
        if not item_name:
            raise ValueError("Item name cannot be empty")
        
        if not self._authenticated:
            if not await self.authenticate():
                raise ShoppingListError("Failed to authenticate with shopping list service")
        
        try:
            # Get lists
            lists = await self.get_lists()
            if not lists:
                raise ShoppingListError("No shopping lists found")
            
            # Add to first list
            list_uuid = lists[0]['listUuid']
            
            # Create item details
            item_details = BringListItemDetails(item_name, str(quantity))
            
            # Add item in executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.bring_client.saveItem(list_uuid, item_name, item_details)
            )
            
            logger.info(f"Added '{item_name}' (×{quantity}) to shopping list")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add item to shopping list: {e}")
            raise ShoppingListError(f"Failed to add item: {e}")
    
    def add_item_sync(self, item_name: str, quantity: int = 1) -> bool:
        """Synchronous version of add_item.
        
        Args:
            item_name: Name of the item
            quantity: Quantity to add
            
        Returns:
            True if successful
        """
        if not item_name:
            return False
        
        if not self._authenticated:
            if not self.authenticate_sync():
                return False
        
        try:
            lists = self.bring_client.loadLists()
            if not lists or not lists.get('lists'):
                return False
            
            list_uuid = lists['lists'][0]['listUuid']
            self.bring_client.saveItem(list_uuid, item_name)
            
            logger.info(f"Added '{item_name}' to shopping list (sync)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add item (sync): {e}")
            return False
    
    async def get_lists(self) -> List[Dict[str, Any]]:
        """Get all shopping lists.
        
        Returns:
            List of shopping lists
        """
        if not self._authenticated:
            if not await self.authenticate():
                return []
        
        try:
            # Check cache
            import time
            current_time = time.time()
            if self._lists_cache and self._cache_time:
                if current_time - self._cache_time < self._cache_duration:
                    return self._lists_cache
            
            # Load lists in executor
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self.bring_client.loadLists
            )
            
            lists = result.get('lists', [])
            
            # Update cache
            self._lists_cache = lists
            self._cache_time = current_time
            
            return lists
            
        except Exception as e:
            logger.error(f"Failed to get shopping lists: {e}")
            return []
    
    async def get_list_items(self, list_uuid: str = None) -> List[Dict[str, Any]]:
        """Get items from a shopping list.
        
        Args:
            list_uuid: List UUID (uses first list if not provided)
            
        Returns:
            List of items in the shopping list
        """
        if not self._authenticated:
            if not await self.authenticate():
                return []
        
        try:
            if not list_uuid:
                lists = await self.get_lists()
                if not lists:
                    return []
                list_uuid = lists[0]['listUuid']
            
            # Get items in executor
            loop = asyncio.get_event_loop()
            items = await loop.run_in_executor(
                None,
                lambda: self.bring_client.getItems(list_uuid)
            )
            
            return items.get('purchase', [])
            
        except Exception as e:
            logger.error(f"Failed to get list items: {e}")
            return []
    
    async def remove_item(self, item_name: str, list_uuid: str = None) -> bool:
        """Remove item from shopping list.
        
        Args:
            item_name: Name of the item to remove
            list_uuid: List UUID (uses first list if not provided)
            
        Returns:
            True if successful
        """
        if not self._authenticated:
            if not await self.authenticate():
                return False
        
        try:
            if not list_uuid:
                lists = await self.get_lists()
                if not lists:
                    return False
                list_uuid = lists[0]['listUuid']
            
            # Remove item in executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.bring_client.removeItem(list_uuid, item_name)
            )
            
            logger.info(f"Removed '{item_name}' from shopping list")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove item: {e}")
            return False
    
    def is_available(self) -> bool:
        """Check if shopping list service is available.
        
        Returns:
            True if service is configured and available
        """
        return (
            self.settings.enable_shopping_list and
            bool(self.settings.bring_email) and
            bool(self.settings.bring_password)
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status.
        
        Returns:
            Dictionary with service status
        """
        return {
            "enabled": self.settings.enable_shopping_list,
            "configured": bool(self.settings.bring_email and self.settings.bring_password),
            "authenticated": self._authenticated,
            "available": self.is_available()
        }