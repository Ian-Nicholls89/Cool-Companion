"""Item model with validation and business logic."""
from dataclasses import dataclass
from datetime import date
from typing import Optional, Dict, Any
import re

@dataclass
class Item:
    """Item model with proper typing and validation"""
    name: str
    expiry_date: date
    id: Optional[int] = None
    barcode: Optional[str] = None
    quantity: int = 1
    is_opened: bool = False
    opened_date: Optional[date] = None
    
    def __post_init__(self):
        """Validate item data after initialization"""
        self._validate_name()
        self._validate_quantity()
        self._validate_dates()
        self._sanitize_barcode()
    
    def _validate_name(self):
        """Validate item name"""
        if not self.name or not self.name.strip():
            raise ValueError("Item name cannot be empty")
        
        self.name = self.name.strip()
        
        if len(self.name) > 100:
            raise ValueError("Item name too long (max 100 characters)")
        
        # Allow alphanumeric, spaces, hyphens, dots, and common punctuation
        if not re.match(r'^[a-zA-Z0-9\s\-\.\,\'\&\(\)]+$', self.name):
            raise ValueError("Item name contains invalid characters")
    
    def _validate_quantity(self):
        """Validate quantity"""
        if not isinstance(self.quantity, int):
            try:
                self.quantity = int(self.quantity)
            except (ValueError, TypeError):
                raise ValueError("Quantity must be a valid integer")
        
        if self.quantity < 1:
            raise ValueError("Quantity must be at least 1")
        
        if self.quantity > 999:
            raise ValueError("Quantity too large (max 999)")
    
    def _validate_dates(self):
        """Validate and convert dates"""
        # Convert expiry_date if string
        if isinstance(self.expiry_date, str):
            try:
                self.expiry_date = date.fromisoformat(self.expiry_date)
            except ValueError:
                raise ValueError("Invalid expiry date format (use YYYY-MM-DD)")
        
        # Convert opened_date if string
        if self.opened_date and isinstance(self.opened_date, str):
            try:
                self.opened_date = date.fromisoformat(self.opened_date)
            except ValueError:
                raise ValueError("Invalid opened date format (use YYYY-MM-DD)")
        
        # Validate opened_date logic
        if self.is_opened and not self.opened_date:
            self.opened_date = date.today()
        elif not self.is_opened:
            self.opened_date = None
        
        # Validate opened_date is not in future
        if self.opened_date and self.opened_date > date.today():
            raise ValueError("Opened date cannot be in the future")
    
    def _sanitize_barcode(self):
        """Sanitize barcode to prevent injection attacks"""
        if self.barcode:
            # Remove any potentially harmful characters
            self.barcode = re.sub(r'[^\w\-]', '', self.barcode)
            
            if len(self.barcode) > 50:
                raise ValueError("Barcode too long (max 50 characters)")
    
    @property
    def is_expired(self) -> bool:
        """Check if item is expired"""
        return self.expiry_date < date.today()
    
    @property
    def days_until_expiry(self) -> int:
        """Calculate days until expiry (negative if expired)"""
        return (self.expiry_date - date.today()).days
    
    @property
    def is_expiring_soon(self) -> bool:
        """Check if item is expiring within 3 days"""
        days = self.days_until_expiry
        return 0 <= days <= 3
    
    @property
    def status(self) -> str:
        """Get item status"""
        if self.is_expired:
            return "expired"
        elif self.is_expiring_soon:
            return "expiring_soon"
        elif self.is_opened:
            return "opened"
        else:
            return "fresh"
    
    @property
    def display_name(self) -> str:
        """Get display name with quantity"""
        if self.quantity > 1:
            return f"{self.name} (×{self.quantity})"
        return self.name
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "name": self.name,
            "expiry_date": self.expiry_date.isoformat(),
            "barcode": self.barcode,
            "quantity": self.quantity,
            "is_opened": self.is_opened,
            "opened_date": self.opened_date.isoformat() if self.opened_date else None,
            "status": self.status,
            "days_until_expiry": self.days_until_expiry,
            "is_expired": self.is_expired,
            "is_expiring_soon": self.is_expiring_soon
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Item':
        """Create Item from dictionary.

        Args:
            data: Dictionary with item data

        Returns:
            Item object

        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Validate required fields
        if 'name' not in data:
            raise ValueError("Item name is required")
        if 'expiry_date' not in data:
            raise ValueError("Expiry date is required")

        # Parse expiry date
        try:
            if isinstance(data['expiry_date'], str):
                expiry_date = date.fromisoformat(data['expiry_date'])
            elif isinstance(data['expiry_date'], date):
                expiry_date = data['expiry_date']
            else:
                raise ValueError(f"Invalid expiry_date type: {type(data['expiry_date'])}")
        except ValueError as e:
            raise ValueError(f"Invalid expiry date format: {e}")

        # Parse opened date if present
        opened_date = None
        if data.get('opened_date'):
            try:
                if isinstance(data['opened_date'], str):
                    opened_date = date.fromisoformat(data['opened_date'])
                elif isinstance(data['opened_date'], date):
                    opened_date = data['opened_date']
            except ValueError as e:
                raise ValueError(f"Invalid opened date format: {e}")

        return cls(
            id=data.get('id'),
            name=data['name'],
            expiry_date=expiry_date,
            barcode=data.get('barcode'),
            quantity=data.get('quantity', 1),
            is_opened=data.get('is_opened', False),
            opened_date=opened_date
        )
    
    def __str__(self) -> str:
        """String representation"""
        return f"{self.display_name} (expires: {self.expiry_date})"
    
    def __repr__(self) -> str:
        """Developer representation"""
        return f"Item(id={self.id}, name='{self.name}', expiry_date={self.expiry_date}, status='{self.status}')"