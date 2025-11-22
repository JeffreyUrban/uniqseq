"""Random sequence generation for property-based testing."""

import random


def generate_random_sequence(num_lines: int, alphabet_size: int, seed: int = None) -> list[str]:
    """Generate random sequence from limited alphabet.

    Args:
        num_lines: Number of lines to generate
        alphabet_size: Size of character set (e.g., 10 for digits 0-9)
        seed: Random seed for reproducibility

    Returns:
        List of single-character lines
    """
    if seed is not None:
        random.seed(seed)

    alphabet = [str(i) for i in range(alphabet_size)]
    return [random.choice(alphabet) for _ in range(num_lines)]


def generate_alphabet(size: int) -> list[str]:
    """Generate alphabet of given size.

    Args:
        size: Number of characters

    Returns:
        List of single characters
    """
    if size <= 10:
        # Digits: 0-9
        return [str(i) for i in range(size)]
    elif size <= 26:
        # Letters: A-Z
        return [chr(ord("A") + i) for i in range(size)]
    else:
        # Alphanumeric: 0-9, A-Z, a-z
        chars = []
        chars.extend([str(i) for i in range(10)])  # 0-9
        chars.extend([chr(ord("A") + i) for i in range(26)])  # A-Z
        chars.extend([chr(ord("a") + i) for i in range(min(size - 36, 26))])  # a-z
        return chars[:size]
