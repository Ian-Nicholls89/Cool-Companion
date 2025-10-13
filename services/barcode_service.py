"""Service for barcode operations with fallback strategy."""
import asyncio
import logging
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
from functools import lru_cache
import requests
from concurrent.futures import ThreadPoolExecutor
from repositories.barcode_repository import BarcodeRepository
from config.settings import settings

logger = logging.getLogger(__name__)

class ServiceError(Exception):
    """Base exception for service layer."""
    pass

class BarcodeNotFoundError(ServiceError):
    """Raised when barcode is not found."""
    pass

# Strategy pattern for barcode lookup
class BarcodeLookupStrategy(ABC):
    """Abstract strategy for barcode lookup."""
    
    @abstractmethod
    async def lookup(self, barcode: str) -> Optional[Dict[str, Any]]:
        """Lookup product information by barcode."""
        pass

class LocalBarcodeLookup(BarcodeLookupStrategy):
    """Local database barcode lookup strategy."""
    
    def __init__(self, repository: BarcodeRepository):
        self.repository = repository
    
    async def lookup(self, barcode: str) -> Optional[Dict[str, Any]]:
        """Lookup in local database."""
        try:
            result = self.repository.lookup(barcode)
            if result:
                logger.info(f"Found barcode {barcode} in local cache")
                return result
            return None
        except Exception as e:
            logger.error(f"Local barcode lookup failed: {e}")
            return None

class OpenFoodFactsLookup(BarcodeLookupStrategy):
    """OpenFoodFacts API barcode lookup strategy."""
    
    def __init__(self, api_url: str = None, timeout: int = 5, verify_ssl: bool = True):
        self.api_url = api_url or settings.openfoodfacts_url
        self.timeout = timeout
        self.verify_ssl = verify_ssl
    
    @lru_cache(maxsize=128)
    async def lookup(self, barcode: str) -> Optional[Dict[str, Any]]:
        """Lookup in OpenFoodFacts API with caching."""
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                response = await loop.run_in_executor(
                    executor,
                    lambda: requests.get(
                        f"{self.api_url}{barcode}.json",
                        timeout=self.timeout,
                        verify=self.verify_ssl
                    )
                )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == 1:
                    product = data.get("product", {})
                    product_name = product.get("product_name") or product.get("product_name_en")
                    if product_name:
                        logger.info(f"Found barcode {barcode} in OpenFoodFacts")
                        return {
                            "name": product_name,
                            "source": "openfoodfacts",
                            "brand": product.get("brands"),
                            "category": product.get("categories"),
                            "barcode": barcode
                        }
            return None
        except Exception as e:
            logger.error(f"OpenFoodFacts lookup failed for {barcode}: {e}")
            return None

class BarcodeService:
    """Service for barcode operations with fallback strategy."""
    
    def __init__(self, barcode_repository: BarcodeRepository, settings=None):
        """Initialize barcode service.
        
        Args:
            barcode_repository: Repository for barcode operations
            settings: Application settings
        """
        self.repository = barcode_repository
        self.settings = settings or globals()['settings']
        
        # Initialize lookup strategies
        self.strategies = [
            LocalBarcodeLookup(barcode_repository),
            OpenFoodFactsLookup(
                self.settings.openfoodfacts_url,
                self.settings.api_timeout,
                self.settings.api_verify_ssl
            )
        ]
    
    async def lookup_product(self, barcode: str) -> Dict[str, Any]:
        """Lookup product with fallback strategy.
        
        Args:
            barcode: Barcode to lookup
            
        Returns:
            Product info dictionary
            
        Raises:
            BarcodeNotFoundError: If product not found
        """
        if not barcode:
            raise ValueError("Barcode cannot be empty")
        
        # Try each strategy in order
        for strategy in self.strategies:
            result = await strategy.lookup(barcode)
            if result:
                # Cache to local if from external source
                if result.get("source") != "local":
                    self.repository.save(
                        barcode=barcode,
                        name=result["name"],
                        brand=result.get("brand"),
                        category=result.get("category")
                    )
                return result
        
        raise BarcodeNotFoundError(f"Product not found for barcode: {barcode}")
    
    def lookup_product_sync(self, barcode: str) -> Optional[Dict[str, Any]]:
        """Synchronous version of lookup_product.
        
        Args:
            barcode: Barcode to lookup
            
        Returns:
            Product info or None
        """
        try:
            # First try local
            result = self.repository.lookup(barcode)
            if result:
                return result
            
            # Then try API
            response = requests.get(
                f"{self.settings.openfoodfacts_url}{barcode}.json",
                timeout=self.settings.api_timeout,
                verify=self.settings.api_verify_ssl
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == 1:
                    product = data.get("product", {})
                    product_name = product.get("product_name")
                    if product_name:
                        # Cache result
                        self.repository.save(barcode, product_name)
                        return {
                            "name": product_name,
                            "source": "openfoodfacts",
                            "barcode": barcode
                        }
            return None
        except Exception as e:
            logger.error(f"Sync barcode lookup failed: {e}")
            return None
    
    def get_produce_items(self) -> List[tuple[str, str]]:
        """Get all produce items (non-barcoded items).
        
        Returns:
            List of tuples (barcode, name)
        """
        return self.repository.get_produce_items()
    
    def search_cached_products(self, query: str) -> List[Dict[str, Any]]:
        """Search cached products by name.
        
        Args:
            query: Search query
            
        Returns:
            List of matching products
        """
        return self.repository.search(query)
    
    def get_frequently_used(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get frequently used products.
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of frequently used products
        """
        return self.repository.get_frequently_used(limit)
    
    def get_statistics(self) -> Dict[str, int]:
        """Get barcode cache statistics.
        
        Returns:
            Dictionary with statistics
        """
        return self.repository.get_statistics()