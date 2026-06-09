"""
Phone number utilities for normalizing mixed word/digit phone inputs.
Handles voice-based input where numbers may be spoken as words.
"""
import re
import logging

logger = logging.getLogger(__name__)

# Word to digit mapping
WORD_TO_DIGIT = {
    'zero': '0', 'oh': '0', 'o': '0',
    'one': '1', 'won': '1',
    'two': '2', 'to': '2', 'too': '2',
    'three': '3',
    'four': '4', 'for': '4',
    'five': '5',
    'six': '6',
    'seven': '7',
    'eight': '8', 'ate': '8',
    'nine': '9', 'niner': '9',
}

# Multiplier words
MULTIPLIERS = {
    'double': 2,
    'triple': 3,
    'quadruple': 4,
}


def normalize_phone_number(raw_input: str) -> str:
    """
    Convert mixed word/digit phone input to digits only.
    
    Handles:
    - Number words: "one", "two", "three", etc.
    - Multipliers: "double 8" -> "88", "triple 5" -> "555"
    - Mixed formats: "8 one 7 double 8 0 9 1 2 3" -> "8178809123"
    
    Args:
        raw_input: The raw phone number input (may contain words)
        
    Returns:
        Normalized phone number as digits only
    """
    if not raw_input:
        return ""
    
    # If already clean digits, return as-is
    clean = re.sub(r'[^\d]', '', raw_input)
    if len(clean) >= 10:
        return clean[-10:]  # Return last 10 digits
    
    # Process word-based input
    # Normalize input: lowercase, remove punctuation except spaces
    normalized = raw_input.lower()
    normalized = re.sub(r'[^\w\s]', ' ', normalized)
    tokens = normalized.split()
    
    result = []
    i = 0
    
    while i < len(tokens):
        token = tokens[i]
        
        # Handle multipliers (double, triple, etc.)
        if token in MULTIPLIERS and i + 1 < len(tokens):
            multiplier = MULTIPLIERS[token]
            next_token = tokens[i + 1]
            
            # Get the digit to multiply
            if next_token in WORD_TO_DIGIT:
                digit = WORD_TO_DIGIT[next_token]
                result.append(digit * multiplier)
                i += 2
                continue
            elif next_token.isdigit() and len(next_token) == 1:
                result.append(next_token * multiplier)
                i += 2
                continue
        
        # Handle word-to-digit conversion
        if token in WORD_TO_DIGIT:
            result.append(WORD_TO_DIGIT[token])
            i += 1
            continue
        
        # Handle raw digits
        if token.isdigit():
            result.append(token)
            i += 1
            continue
        
        # Handle mixed alphanumeric (extract digits)
        digits_only = re.sub(r'[^\d]', '', token)
        if digits_only:
            result.append(digits_only)
        
        i += 1
    
    normalized_number = ''.join(result)
    
    # Log the conversion if it was meaningful
    if normalized_number != clean and normalized_number:
        logger.info("Phone normalized: '%s' -> '%s'", raw_input[:50], normalized_number)
    
    return normalized_number


def extract_phone_from_text(text: str) -> str | None:
    """
    Extract and normalize a phone number from free-form text.
    
    Args:
        text: Text that may contain a phone number
        
    Returns:
        Normalized phone number if found, None otherwise
    """
    if not text:
        return None
    
    # First, try to find a clear 10-digit number
    digit_match = re.search(r'\b(\d{10,11})\b', text)
    if digit_match:
        return digit_match.group(1)[-10:]
    
    # Try to find formatted phone number (with dashes, spaces, etc.)
    formatted_match = re.search(r'\b(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})\b', text)
    if formatted_match:
        return re.sub(r'[^\d]', '', formatted_match.group(1))
    
    # Otherwise, try to normalize the whole text
    normalized = normalize_phone_number(text)
    if len(normalized) >= 10:
        return normalized[-10:]
    
    return None


def is_valid_phone_number(phone: str) -> bool:
    """
    Check if a string is a valid 10-digit phone number.
    
    Args:
        phone: The phone number to validate
        
    Returns:
        True if valid 10-digit number, False otherwise
    """
    if not phone:
        return False
    
    digits_only = re.sub(r'[^\d]', '', phone)
    return len(digits_only) == 10


def format_phone_for_speech(phone: str, last_n: int = 0) -> str:
    """
    Format a phone number for speech output.
    
    Args:
        phone: The phone number to format
        last_n: If > 0, only return last N digits
        
    Returns:
        Phone number formatted with spaces between digits
    """
    digits_only = re.sub(r'[^\d]', '', phone)
    
    if last_n > 0:
        digits_only = digits_only[-last_n:]
    
    return ' '.join(digits_only)
