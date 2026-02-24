"""
campaign Name/Description Tag Replacement Utilities

Supports custom tags like {YEAR}, {MONTH}, {DATE}, {TIME}, {AUTO}, etc.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional

# Import will be done lazily to avoid circular dependencies
_auto_increment_counter = None
_counter_loaded = False


def _get_db_session():
    """Get database campaign (lazy import to avoid circular dependencies)."""
    from app.db import SessionLocal
    return SessionLocal()


def _load_counter_from_db() -> int:
    """Load auto-increment counter from database."""
    global _auto_increment_counter, _counter_loaded
    
    if _counter_loaded and _auto_increment_counter is not None:
        return _auto_increment_counter
    
    db = _get_db_session()
    try:
        from app.models.app_settings import AppSettings
        
        setting = db.query(AppSettings).filter(
            AppSettings.key == "campaign_auto_increment"
        ).first()
        
        if setting and setting.value:
            _auto_increment_counter = int(setting.value)
        else:
            # Initialize to 1 if not found
            _auto_increment_counter = 1
            # Create the setting
            new_setting = AppSettings(
                key="campaign_auto_increment",
                value="1",
                description="Auto-increment counter for campaign name tags"
            )
            db.add(new_setting)
            db.commit()
        
        _counter_loaded = True
        return _auto_increment_counter
    finally:
        db.close()


def _save_counter_to_db(value: int) -> None:
    """Save auto-increment counter to database."""
    db = _get_db_session()
    try:
        from app.models.app_settings import AppSettings
        
        setting = db.query(AppSettings).filter(
            AppSettings.key == "campaign_auto_increment"
        ).first()
        
        if setting:
            setting.value = str(value)
        else:
            setting = AppSettings(
                key="campaign_auto_increment",
                value=str(value),
                description="Auto-increment counter for campaign name tags"
            )
            db.add(setting)
        
        db.commit()
    finally:
        db.close()


def get_next_auto_increment() -> int:
    """Get next auto-increment number and save to database."""
    global _auto_increment_counter
    
    # Load current value from database
    current = _load_counter_from_db()
    
    # Increment and save
    _auto_increment_counter = current + 1
    _save_counter_to_db(_auto_increment_counter)
    
    return current


def reset_auto_increment(value: int = 1) -> None:
    """Reset auto-increment counter and save to database."""
    global _auto_increment_counter, _counter_loaded
    
    _auto_increment_counter = value
    _counter_loaded = True
    _save_counter_to_db(value)


def get_datetime_values() -> Dict[str, str]:
    """Get current date/time values for tag replacement."""
    now = datetime.now()
    
    return {
        "YEAR": str(now.year),
        "MONTH": str(now.month).zfill(2),
        "DAY": str(now.day).zfill(2),
        "HOUR": str(now.hour).zfill(2),
        "MINUTE": str(now.minute).zfill(2),
        "SECOND": str(now.second).zfill(2),
        "DATE": now.strftime("%Y-%m-%d"),
        "TIME": now.strftime("%H:%M:%S"),
        "TIMESTAMP": str(int(now.timestamp() * 1000)),
        "MONTH_NAME": now.strftime("%B"),
        "MONTH_SHORT": now.strftime("%b"),
        "DAY_NAME": now.strftime("%A"),
        "DAY_SHORT": now.strftime("%a"),
    }


def get_available_tags() -> Dict[str, str]:
    """Get all available tags with their current values."""
    datetime_values = get_datetime_values()
    
    # Load current counter from database
    current_counter = _load_counter_from_db()
    
    return {
        **datetime_values,
        "AUTO": str(current_counter).zfill(3),
        "AUTO_1": str(current_counter).zfill(1),
        "AUTO_2": str(current_counter).zfill(2),
        "AUTO_3": str(current_counter).zfill(3),
        "AUTO_4": str(current_counter).zfill(4),
        "AUTO_5": str(current_counter).zfill(5),
    }


def extract_tags(template: str) -> List[str]:
    """Extract tag names from a template string."""
    tag_pattern = re.compile(r'\{([A-Z_0-9]+)\}')
    tags = []
    
    for match in tag_pattern.finditer(template):
        tag_name = match.group(1)
        if tag_name not in tags:
            tags.append(tag_name)
    
    return tags


def replace_tags(template: str, custom_values: Optional[Dict[str, str]] = None) -> str:
    """
    Replace tags in a template string with actual values.
    Automatically increments the counter if AUTO tags are detected.
    
    Args:
        template: String containing tags like {YEAR}, {MONTH}, {AUTO}
        custom_values: Optional custom tag values to override defaults
        
    Returns:
        String with tags replaced by actual values
        
    Example:
        >>> replace_tags("campaign-{YEAR}-{AUTO}")
        "campaign-2025-001"
    """
    if not template:
        return template
    
    # Check if template contains any AUTO tags
    extracted_tags = extract_tags(template)
    has_auto_tag = any(tag.startswith("AUTO") for tag in extracted_tags)
    
    # Get current counter value for replacement
    available_tags = get_available_tags()
    all_tags = {**available_tags, **(custom_values or {})}
    
    result = template
    
    # Replace all tags with their values
    for tag, value in all_tags.items():
        pattern = r'\{' + tag + r'\}'
        result = re.sub(pattern, value, result)
    
    # If AUTO tag was used, increment the counter for next use
    if has_auto_tag:
        get_next_auto_increment()
    
    return result


def get_tag_description(tag: str) -> str:
    """Get tag description/help text."""
    descriptions = {
        "YEAR": "Current year (e.g., 2025)",
        "MONTH": "Current month as number (01-12)",
        "DAY": "Current day of month (01-31)",
        "HOUR": "Current hour (00-23)",
        "MINUTE": "Current minute (00-59)",
        "SECOND": "Current second (00-59)",
        "DATE": "Current date (YYYY-MM-DD)",
        "TIME": "Current time (HH:MM:SS)",
        "TIMESTAMP": "Unix timestamp in milliseconds",
        "MONTH_NAME": "Full month name (e.g., January)",
        "MONTH_SHORT": "Short month name (e.g., Jan)",
        "DAY_NAME": "Full day name (e.g., Monday)",
        "DAY_SHORT": "Short day name (e.g., Mon)",
        "AUTO": "Auto-increment number (001, 002, ...)",
        "AUTO_1": "Auto-increment with 1 digit",
        "AUTO_2": "Auto-increment with 2 digits",
        "AUTO_3": "Auto-increment with 3 digits",
        "AUTO_4": "Auto-increment with 4 digits",
        "AUTO_5": "Auto-increment with 5 digits",
    }
    
    return descriptions.get(tag, "Unknown tag")

