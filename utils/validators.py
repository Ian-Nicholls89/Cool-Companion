"""Input validation utilities."""
import re
from datetime import date, datetime
from typing import Optional, Tuple, List

class ValidationResult:
    """Result of a validation operation."""
    
    def __init__(self, is_valid: bool, error_message: Optional[str] = None):
        self.is_valid = is_valid
        self.error_message = error_message
    
    @classmethod
    def success(cls):
        """Create a successful validation result."""
        return cls(True)
    
    @classmethod
    def error(cls, message: str):
        """Create a failed validation result."""
        return cls(False, message)

class ItemValidator:
    """Validator for item data."""
    
    @staticmethod
    def validate_name(name: str) -> ValidationResult:
        """Validate item name.
        
        Args:
            name: Item name to validate
            
        Returns:
            ValidationResult
        """
        if not name or not name.strip():
            return ValidationResult.error("Item name cannot be empty")
        
        name = name.strip()
        
        if len(name) < 2:
            return ValidationResult.error("Item name must be at least 2 characters")
        
        if len(name) > 100:
            return ValidationResult.error("Item name too long (max 100 characters)")
        
        # Allow alphanumeric, spaces, and common punctuation
        if not re.match(r'^[a-zA-Z0-9\s\-\.\,\'\&\(\)\/]+$', name):
            return ValidationResult.error("Item name contains invalid characters")
        
        return ValidationResult.success()
    
    @staticmethod
    def validate_quantity(quantity: any) -> ValidationResult:
        """Validate quantity.
        
        Args:
            quantity: Quantity to validate
            
        Returns:
            ValidationResult
        """
        try:
            qty = int(quantity)
        except (ValueError, TypeError):
            return ValidationResult.error("Quantity must be a valid number")
        
        if qty < 1:
            return ValidationResult.error("Quantity must be at least 1")
        
        if qty > 999:
            return ValidationResult.error("Quantity too large (max 999)")
        
        return ValidationResult.success()
    
    @staticmethod
    def validate_expiry_date(expiry_date: any, allow_past: bool = False) -> ValidationResult:
        """Validate expiry date.
        
        Args:
            expiry_date: Date to validate
            allow_past: Whether to allow past dates
            
        Returns:
            ValidationResult
        """
        if not expiry_date:
            return ValidationResult.error("Expiry date is required")
        
        # Convert string to date if needed
        if isinstance(expiry_date, str):
            try:
                expiry = date.fromisoformat(expiry_date)
            except ValueError:
                try:
                    # Try alternative formats
                    expiry = datetime.strptime(expiry_date, "%d/%m/%Y").date()
                except ValueError:
                    return ValidationResult.error("Invalid date format (use YYYY-MM-DD)")
        elif isinstance(expiry_date, datetime):
            expiry = expiry_date.date()
        elif isinstance(expiry_date, date):
            expiry = expiry_date
        else:
            return ValidationResult.error("Invalid date type")
        
        # Check if date is in the past
        if not allow_past and expiry < date.today():
            return ValidationResult.error("Expiry date cannot be in the past")
        
        # Check if date is too far in the future (5 years)
        max_future_date = date.today().replace(year=date.today().year + 5)
        if expiry > max_future_date:
            return ValidationResult.error("Expiry date is too far in the future")
        
        return ValidationResult.success()
    
    @staticmethod
    def validate_all(
        name: str,
        expiry_date: any,
        quantity: any = 1,
        allow_past_dates: bool = False
    ) -> Tuple[bool, List[str]]:
        """Validate all item fields.
        
        Args:
            name: Item name
            expiry_date: Expiry date
            quantity: Quantity
            allow_past_dates: Whether to allow past expiry dates
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Validate name
        name_result = ItemValidator.validate_name(name)
        if not name_result.is_valid:
            errors.append(name_result.error_message)
        
        # Validate expiry date
        date_result = ItemValidator.validate_expiry_date(expiry_date, allow_past_dates)
        if not date_result.is_valid:
            errors.append(date_result.error_message)
        
        # Validate quantity
        qty_result = ItemValidator.validate_quantity(quantity)
        if not qty_result.is_valid:
            errors.append(qty_result.error_message)
        
        return (len(errors) == 0, errors)

class BarcodeValidator:
    """Validator for barcode data."""
    
    # Common barcode patterns
    EAN13_PATTERN = re.compile(r'^\d{13}$')
    EAN8_PATTERN = re.compile(r'^\d{8}$')
    UPC_PATTERN = re.compile(r'^\d{12}$')
    CODE128_PATTERN = re.compile(r'^[A-Za-z0-9\-\.\ \$\/\+\%]+$')
    
    @staticmethod
    def validate_barcode(barcode: str) -> ValidationResult:
        """Validate barcode format.
        
        Args:
            barcode: Barcode to validate
            
        Returns:
            ValidationResult
        """
        if not barcode:
            return ValidationResult.error("Barcode cannot be empty")
        
        barcode = barcode.strip()
        
        if len(barcode) > 50:
            return ValidationResult.error("Barcode too long (max 50 characters)")
        
        # Check for SQL injection attempts
        if any(char in barcode for char in [';', '--', '/*', '*/', 'DROP', 'DELETE']):
            return ValidationResult.error("Barcode contains invalid characters")
        
        # Allow produce codes
        if barcode.startswith('PRODUCE_'):
            return ValidationResult.success()
        
        # Check common barcode formats
        if (BarcodeValidator.EAN13_PATTERN.match(barcode) or
            BarcodeValidator.EAN8_PATTERN.match(barcode) or
            BarcodeValidator.UPC_PATTERN.match(barcode) or
            BarcodeValidator.CODE128_PATTERN.match(barcode)):
            return ValidationResult.success()
        
        # Generic validation for other formats
        if re.match(r'^[A-Za-z0-9\-]+$', barcode):
            return ValidationResult.success()
        
        return ValidationResult.error("Invalid barcode format")
    
    @staticmethod
    def sanitize_barcode(barcode: str) -> str:
        """Sanitize barcode for safe storage.
        
        Args:
            barcode: Barcode to sanitize
            
        Returns:
            Sanitized barcode
        """
        if not barcode:
            return ""
        
        # Remove any potentially harmful characters
        sanitized = re.sub(r'[^\w\-]', '', barcode.strip())
        
        # Truncate if too long
        return sanitized[:50]
    
    @staticmethod
    def is_produce_code(barcode: str) -> bool:
        """Check if barcode is a produce code.
        
        Args:
            barcode: Barcode to check
            
        Returns:
            True if produce code
        """
        return barcode and barcode.startswith('PRODUCE_')

class EmailValidator:
    """Validator for email addresses."""
    
    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    @staticmethod
    def validate_email(email: str) -> ValidationResult:
        """Validate email address.
        
        Args:
            email: Email to validate
            
        Returns:
            ValidationResult
        """
        if not email:
            return ValidationResult.error("Email cannot be empty")
        
        email = email.strip().lower()
        
        if not EmailValidator.EMAIL_PATTERN.match(email):
            return ValidationResult.error("Invalid email format")
        
        if len(email) > 254:
            return ValidationResult.error("Email too long")
        
        return ValidationResult.success()

class PasswordValidator:
    """Validator for passwords."""
    
    @staticmethod
    def validate_password(password: str, min_length: int = 8) -> ValidationResult:
        """Validate password strength.
        
        Args:
            password: Password to validate
            min_length: Minimum password length
            
        Returns:
            ValidationResult
        """
        if not password:
            return ValidationResult.error("Password cannot be empty")
        
        if len(password) < min_length:
            return ValidationResult.error(f"Password must be at least {min_length} characters")
        
        if len(password) > 128:
            return ValidationResult.error("Password too long (max 128 characters)")
        
        # Check for basic complexity
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)
        
        complexity_score = sum([has_upper, has_lower, has_digit, has_special])
        
        if complexity_score < 2:
            return ValidationResult.error(
                "Password must contain at least 2 of: uppercase, lowercase, digit, special character"
            )
        
        return ValidationResult.success()