"""Centralized theme configuration for the application."""
import flet
from flet import Page, Colors, TextStyle, FontWeight, Theme, ColorScheme, Icons
import os

class UITheme:
    """Centralized theme configuration with Material Design 3."""
    
    # Color scheme
    PRIMARY = Colors.BLUE_700
    PRIMARY_VARIANT = Colors.BLUE_900
    PRIMARY_LIGHT = Colors.BLUE_100
    SECONDARY = Colors.TEAL_600
    SECONDARY_VARIANT = Colors.TEAL_800
    BACKGROUND = Colors.GREY_50
    SURFACE = Colors.WHITE
    ERROR = Colors.RED_700
    WARNING = Colors.ORANGE_700
    SUCCESS = Colors.GREEN_700
    INFO = Colors.BLUE_600
    
    # Text colors
    TEXT_PRIMARY = Colors.GREY_900
    TEXT_SECONDARY = Colors.GREY_700
    TEXT_DISABLED = Colors.GREY_400
    TEXT_ON_PRIMARY = Colors.WHITE
    TEXT_ON_ERROR = Colors.WHITE
    
    # Status colors for items
    EXPIRED_BG = Colors.RED_50
    EXPIRED_TEXT = Colors.RED_700
    EXPIRING_BG = Colors.ORANGE_50
    EXPIRING_TEXT = Colors.ORANGE_700
    FRESH_BG = Colors.GREEN_50
    FRESH_TEXT = Colors.GREEN_700
    OPENED_BG = Colors.BLUE_50
    OPENED_TEXT = Colors.BLUE_700
    
    # Text styles
    HEADLINE_LARGE = TextStyle(size=32, weight=FontWeight.BOLD)
    HEADLINE_MEDIUM = TextStyle(size=24, weight=FontWeight.W_600)
    HEADLINE_SMALL = TextStyle(size=20, weight=FontWeight.W_500)
    BODY_LARGE = TextStyle(size=16, weight=FontWeight.NORMAL)
    BODY_MEDIUM = TextStyle(size=14, weight=FontWeight.NORMAL)
    BODY_SMALL = TextStyle(size=12, weight=FontWeight.NORMAL)
    CAPTION = TextStyle(size=11, color=Colors.GREY_600)
    BUTTON = TextStyle(size=14, weight=FontWeight.W_500)
    
    # Spacing constants
    SPACING_XS = 4
    SPACING_SM = 8
    SPACING_MD = 16
    SPACING_LG = 24
    SPACING_XL = 32
    SPACING_XXL = 48
    
    # Border radius
    RADIUS_SM = 4
    RADIUS_MD = 8
    RADIUS_LG = 16
    RADIUS_XL = 24
    RADIUS_ROUND = 999
    
    # Elevation levels
    ELEVATION_NONE = 0
    ELEVATION_LOW = 2
    ELEVATION_MEDIUM = 4
    ELEVATION_HIGH = 8
    ELEVATION_VERY_HIGH = 12
    
    # Animation durations (milliseconds)
    ANIMATION_FAST = 200
    ANIMATION_NORMAL = 300
    ANIMATION_SLOW = 500
    
    # Component sizes
    BUTTON_HEIGHT = 48
    ICON_SIZE_SM = 16
    ICON_SIZE_MD = 24
    ICON_SIZE_LG = 32
    ICON_SIZE_XL = 48
    
    @classmethod
    def apply_to_page(cls, page: Page):
        """Apply theme to a Flet page.
        
        Args:
            page: Flet page object
        """
        page.theme = Theme(
            color_scheme=ColorScheme(
                primary=cls.PRIMARY,
                on_primary=cls.TEXT_ON_PRIMARY,
                primary_container=cls.PRIMARY_LIGHT,
                secondary=cls.SECONDARY,
                on_secondary=cls.TEXT_ON_PRIMARY,
                secondary_container=Colors.TEAL_100,
                surface=cls.SURFACE,
                on_surface=cls.TEXT_PRIMARY,
                surface_variant=Colors.GREY_100,
                background=cls.BACKGROUND,
                on_background=cls.TEXT_PRIMARY,
                error=cls.ERROR,
                on_error=cls.TEXT_ON_ERROR,
                error_container=Colors.RED_100,
                outline=Colors.GREY_400,
                shadow=Colors.BLACK12,
            ),
            use_material3=True,
        )
        
        page.bgcolor = cls.BACKGROUND
        
        # Set default fonts
        page.fonts = {
            "Roboto": "https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap",
            "Winter-City": os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "fonts", "Winter-City.otf"),
        }
        
        # Set default transitions
        page.theme_mode = flet.ThemeMode.LIGHT
    
    @classmethod
    def get_status_colors(cls, status: str) -> tuple:
        """Get colors for item status.
        
        Args:
            status: Item status (expired, expiring_soon, fresh, opened)
            
        Returns:
            Tuple of (background_color, text_color, icon)
        """
        status_map = {
            "expired": (cls.EXPIRED_BG, cls.EXPIRED_TEXT, Icons.ERROR_OUTLINE),
            "expiring_soon": (cls.EXPIRING_BG, cls.EXPIRING_TEXT, Icons.WARNING_AMBER_OUTLINED),
            "fresh": (cls.FRESH_BG, cls.FRESH_TEXT, Icons.CHECK_CIRCLE_OUTLINE),
            "opened": (cls.OPENED_BG, cls.OPENED_TEXT, Icons.OPEN_IN_NEW),
        }
        
        return status_map.get(status, (cls.SURFACE, cls.TEXT_PRIMARY, Icons.HELP_OUTLINE))
    
    @classmethod
    def create_gradient(cls, colors: list, begin=None, end=None):
        """Create a gradient.
        
        Args:
            colors: List of colors
            begin: Gradient begin alignment
            end: Gradient end alignment
            
        Returns:
            LinearGradient object
        """
        return flet.LinearGradient(
            begin=begin or flet.alignment.top_left,
            end=end or flet.alignment.bottom_right,
            colors=colors
        )
    
    @classmethod
    def apply_hover_effect(cls, control, hover_color=None):
        """Apply hover effect to a control.
        
        Args:
            control: Flet control
            hover_color: Color on hover
        """
        original_color = control.bgcolor
        hover = hover_color or cls.PRIMARY_LIGHT
        
        def on_hover(e):
            control.bgcolor = hover if e.data == "true" else original_color
            control.update()
        
        control.on_hover = on_hover
    
    @classmethod
    def create_loading_indicator(cls, size: int = 24, color=None):
        """Create a loading indicator.
        
        Args:
            size: Size of the indicator
            color: Color of the indicator
            
        Returns:
            ProgressRing control
        """
        return flet.ProgressRing(
            width=size,
            height=size,
            stroke_width=2,
            color=color or cls.PRIMARY
        )
    
    @classmethod
    def create_badge(cls, content: str, color=None, text_color=None):
        """Create a badge component.
        
        Args:
            content: Badge content
            color: Background color
            text_color: Text color
            
        Returns:
            Container with badge styling
        """
        return flet.Container(
            content=flet.Text(
                content,
                size=10,
                color=text_color or cls.TEXT_ON_PRIMARY,
                weight=FontWeight.BOLD
            ),
            bgcolor=color or cls.PRIMARY,
            border_radius=cls.RADIUS_ROUND,
            padding=flet.padding.symmetric(horizontal=6, vertical=2),
        )
    
    @classmethod
    def create_chip(cls, label: str, icon=None, on_click=None, selected=False):
        """Create a chip component.
        
        Args:
            label: Chip label
            icon: Optional icon
            on_click: Click handler
            selected: Whether chip is selected
            
        Returns:
            Chip control
        """
        return flet.Chip(
            label=flet.Text(label, size=12),
            leading=flet.Icon(icon, size=16) if icon else None,
            on_click=on_click,
            selected=selected,
            bgcolor=cls.PRIMARY_LIGHT if selected else cls.SURFACE,
            selected_color=cls.PRIMARY,
            show_checkmark=False,
        )
    
    @classmethod
    def create_divider(cls, height: int = 1, color=None):
        """Create a divider.
        
        Args:
            height: Divider height
            color: Divider color
            
        Returns:
            Divider control
        """
        return flet.Divider(
            height=height,
            color=color or Colors.GREY_300
        )
    
    @classmethod
    def get_responsive_width(cls, page_width: float) -> str:
        """Get responsive layout type based on page width.
        
        Args:
            page_width: Current page width
            
        Returns:
            Layout type (mobile, tablet, desktop)
        """
        if page_width < 600:
            return "mobile"
        elif page_width < 1200:
            return "tablet"
        else:
            return "desktop"