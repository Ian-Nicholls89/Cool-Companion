"""Data formatting utilities."""
from datetime import date, datetime, timedelta
from typing import Optional, Union

class DateFormatter:
    """Formatter for date values."""
    
    @staticmethod
    def format_date(
        date_value: Union[date, datetime, str],
        format_string: str = "%Y-%m-%d"
    ) -> str:
        """Format date to string.
        
        Args:
            date_value: Date to format
            format_string: Format string
            
        Returns:
            Formatted date string
        """
        if isinstance(date_value, str):
            try:
                date_value = date.fromisoformat(date_value)
            except ValueError:
                return date_value
        
        if isinstance(date_value, datetime):
            date_value = date_value.date()
        
        if isinstance(date_value, date):
            return date_value.strftime(format_string)
        
        return str(date_value)
    
    @staticmethod
    def format_date_friendly(date_value: Union[date, datetime]) -> str:
        """Format date in a user-friendly way.
        
        Args:
            date_value: Date to format
            
        Returns:
            Friendly formatted date (e.g., "Today", "Tomorrow", "In 3 days")
        """
        if isinstance(date_value, datetime):
            date_value = date_value.date()
        
        if not isinstance(date_value, date):
            return str(date_value)
        
        today = date.today()
        delta = (date_value - today).days
        
        if delta == 0:
            return "Today"
        elif delta == 1:
            return "Tomorrow"
        elif delta == -1:
            return "Yesterday"
        elif delta > 1 and delta <= 7:
            return f"In {delta} days"
        elif delta < -1 and delta >= -7:
            return f"{abs(delta)} days ago"
        elif delta > 7 and delta <= 30:
            weeks = delta // 7
            return f"In {weeks} week{'s' if weeks > 1 else ''}"
        elif delta < -7 and delta >= -30:
            weeks = abs(delta) // 7
            return f"{weeks} week{'s' if weeks > 1 else ''} ago"
        else:
            return date_value.strftime("%B %d, %Y")
    
    @staticmethod
    def format_date_short(date_value: Union[date, datetime]) -> str:
        """Format date in short format.
        
        Args:
            date_value: Date to format
            
        Returns:
            Short formatted date (e.g., "Jan 15")
        """
        if isinstance(date_value, datetime):
            date_value = date_value.date()
        
        if isinstance(date_value, date):
            return date_value.strftime("%b %d")
        
        return str(date_value)
    
    @staticmethod
    def format_expiry_status(expiry_date: Union[date, datetime]) -> str:
        """Format expiry date with status.
        
        Args:
            expiry_date: Expiry date
            
        Returns:
            Formatted expiry status
        """
        if isinstance(expiry_date, datetime):
            expiry_date = expiry_date.date()
        
        if not isinstance(expiry_date, date):
            return "Unknown"
        
        today = date.today()
        delta = (expiry_date - today).days
        
        if delta < 0:
            return f"Expired {abs(delta)} day{'s' if abs(delta) != 1 else ''} ago"
        elif delta == 0:
            return "Expires today"
        elif delta == 1:
            return "Expires tomorrow"
        elif delta <= 3:
            return f"Expires in {delta} days"
        elif delta <= 7:
            return f"Expires this week"
        elif delta <= 30:
            return f"Expires in {delta} days"
        else:
            return f"Expires {DateFormatter.format_date_short(expiry_date)}"
    
    @staticmethod
    def parse_date(
        date_string: str,
        formats: Optional[list] = None
    ) -> Optional[date]:
        """Parse date from string trying multiple formats.
        
        Args:
            date_string: Date string to parse
            formats: List of format strings to try
            
        Returns:
            Parsed date or None
        """
        if not date_string:
            return None
        
        # Default formats to try
        if not formats:
            formats = [
                "%Y-%m-%d",
                "%d/%m/%Y",
                "%m/%d/%Y",
                "%Y/%m/%d",
                "%d-%m-%Y",
                "%m-%d-%Y",
                "%d.%m.%Y",
                "%Y.%m.%d",
            ]
        
        # Try ISO format first
        try:
            return date.fromisoformat(date_string)
        except ValueError:
            pass
        
        # Try each format
        for fmt in formats:
            try:
                return datetime.strptime(date_string, fmt).date()
            except ValueError:
                continue
        
        return None

class QuantityFormatter:
    """Formatter for quantity values."""
    
    @staticmethod
    def format_quantity(quantity: int, unit: Optional[str] = None) -> str:
        """Format quantity with optional unit.
        
        Args:
            quantity: Quantity value
            unit: Optional unit
            
        Returns:
            Formatted quantity
        """
        if quantity == 1:
            return f"1 {unit}" if unit else "1"
        
        # Format with unit
        if unit:
            # Pluralize common units
            if unit.lower() in ['item', 'piece', 'unit']:
                unit = f"{unit}s"
            return f"{quantity} {unit}"
        
        # Just the number with multiplication sign
        return f"×{quantity}"
    
    @staticmethod
    def format_quantity_badge(quantity: int) -> str:
        """Format quantity for badge display.
        
        Args:
            quantity: Quantity value
            
        Returns:
            Badge-formatted quantity
        """
        if quantity <= 1:
            return ""
        elif quantity > 99:
            return "99+"
        else:
            return str(quantity)
    
    @staticmethod
    def format_quantity_change(old_qty: int, new_qty: int) -> str:
        """Format quantity change.
        
        Args:
            old_qty: Old quantity
            new_qty: New quantity
            
        Returns:
            Formatted change (e.g., "+3", "-2")
        """
        diff = new_qty - old_qty
        if diff > 0:
            return f"+{diff}"
        elif diff < 0:
            return str(diff)
        else:
            return "0"

class TextFormatter:
    """General text formatting utilities."""
    
    @staticmethod
    def truncate(text: str, max_length: int, suffix: str = "...") -> str:
        """Truncate text to maximum length.
        
        Args:
            text: Text to truncate
            max_length: Maximum length
            suffix: Suffix to add when truncated
            
        Returns:
            Truncated text
        """
        if not text or len(text) <= max_length:
            return text
        
        return text[:max_length - len(suffix)] + suffix
    
    @staticmethod
    def capitalize_words(text: str) -> str:
        """Capitalize first letter of each word.
        
        Args:
            text: Text to capitalize
            
        Returns:
            Capitalized text
        """
        if not text:
            return ""
        
        return " ".join(word.capitalize() for word in text.split())
    
    @staticmethod
    def format_list(items: list, separator: str = ", ", last_separator: str = " and ") -> str:
        """Format list of items as string.
        
        Args:
            items: List of items
            separator: Separator between items
            last_separator: Separator before last item
            
        Returns:
            Formatted string
        """
        if not items:
            return ""
        
        if len(items) == 1:
            return str(items[0])
        
        if len(items) == 2:
            return f"{items[0]}{last_separator}{items[1]}"
        
        return separator.join(str(item) for item in items[:-1]) + last_separator + str(items[-1])
    
    @staticmethod
    def format_percentage(value: float, decimals: int = 1) -> str:
        """Format value as percentage.
        
        Args:
            value: Value (0-100 or 0-1)
            decimals: Number of decimal places
            
        Returns:
            Formatted percentage
        """
        # Convert to percentage if needed
        if value <= 1:
            value = value * 100
        
        if decimals == 0:
            return f"{int(value)}%"
        else:
            return f"{value:.{decimals}f}%"
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Format file size in human-readable format.
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            Formatted size (e.g., "1.5 MB")
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                if unit == 'B':
                    return f"{size_bytes} {unit}"
                else:
                    return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        
        return f"{size_bytes:.1f} PB"

class StatusFormatter:
    """Formatter for status values."""
    
    STATUS_ICONS = {
        "expired": "🔴",
        "expiring_soon": "🟠",
        "fresh": "🟢",
        "opened": "🔵",
        "unknown": "⚪"
    }
    
    STATUS_LABELS = {
        "expired": "Expired",
        "expiring_soon": "Expiring Soon",
        "fresh": "Fresh",
        "opened": "Opened",
        "unknown": "Unknown"
    }
    
    @staticmethod
    def format_status(status: str, with_icon: bool = False) -> str:
        """Format status with optional icon.
        
        Args:
            status: Status value
            with_icon: Whether to include icon
            
        Returns:
            Formatted status
        """
        label = StatusFormatter.STATUS_LABELS.get(status, status.title())
        
        if with_icon:
            icon = StatusFormatter.STATUS_ICONS.get(status, "")
            return f"{icon} {label}" if icon else label
        
        return label
    
    @staticmethod
    def get_status_color(status: str) -> str:
        """Get color for status.
        
        Args:
            status: Status value
            
        Returns:
            Color hex code
        """
        color_map = {
            "expired": "#DC2626",  # Red
            "expiring_soon": "#EA580C",  # Orange
            "fresh": "#16A34A",  # Green
            "opened": "#2563EB",  # Blue
            "unknown": "#6B7280"  # Gray
        }
        
        return color_map.get(status, "#6B7280")