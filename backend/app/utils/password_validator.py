"""
Password Validation Utility
Validates password strength and complexity requirements.
"""
import re
from typing import Tuple


def validate_password_strength(password: str) -> Tuple[bool, str, int]:
    """
    Validate password meets complexity requirements.
    
    Requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    
    Args:
        password: The password to validate
        
    Returns:
        Tuple of (is_valid, error_message, strength_score)
        strength_score: 0-4 (0=very weak, 4=strong)
    """
    errors = []
    strength = 0
    
    # Check minimum length
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    else:
        strength += 1
        # Bonus for longer passwords
        if len(password) >= 12:
            strength += 1
    
    # Check for uppercase letter
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")
    else:
        strength += 1
    
    # Check for lowercase letter
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")
    else:
        strength += 1
    
    # Check for number
    if not re.search(r'\d', password):
        errors.append("Password must contain at least one number")
    else:
        strength += 1
    
    # Optional: Check for special characters (bonus points)
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        strength = min(strength + 1, 4)  # Cap at 4
    
    if errors:
        return False, "; ".join(errors), max(0, strength - len(errors))
    
    return True, "", min(strength, 4)


def get_password_strength_label(score: int) -> str:
    """
    Get human-readable label for password strength score.
    
    Args:
        score: Strength score (0-4)
        
    Returns:
        Label: "Very Weak", "Weak", "Medium", "Strong", "Very Strong"
    """
    labels = {
        0: "Very Weak",
        1: "Weak",
        2: "Medium",
        3: "Strong",
        4: "Very Strong"
    }
    return labels.get(score, "Unknown")
