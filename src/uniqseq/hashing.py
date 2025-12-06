"""Hashing utilities for lines and windows."""

import hashlib
from dataclasses import dataclass
from typing import Union


@dataclass
class BufferedLine:
    """A line in the buffer with its metadata."""

    line: Union[str, bytes]  # The actual line content
    line_hash: str  # Hash of the line
    input_line_num: int  # Input line number (1-indexed, includes all lines)
    tracked_line_num: int  # Tracked line number (1-indexed, tracked lines only)


def hash_line(line: Union[str, bytes], skip_chars: int = 0) -> str:
    """Hash a single line to 8-byte (16 hex char) string using Blake2b.

    Args:
        line: The line to hash (str or bytes)
        skip_chars: Number of characters/bytes to skip from the beginning before hashing

    Returns:
        16-character hex string (Blake2b 8-byte digest)
    """
    # Skip prefix if requested
    content = line[skip_chars:] if skip_chars > 0 else line

    # Convert to bytes if needed
    if isinstance(content, str):
        content_bytes = content.encode("utf-8")
    else:
        content_bytes = content

    return hashlib.blake2b(content_bytes, digest_size=8).hexdigest()


def hash_window(sequence_length: int, window_hashes: list[str]) -> str:
    """Hash a window of line hashes to 16-byte (32 hex char) string.

    Args:
        sequence_length: Total length of the sequence (for hash uniqueness)
        window_hashes: List of line hashes in the window

    Returns:
        32-character hex string (Blake2b 16-byte digest)
    """
    # Include sequence length to distinguish windows of different sequence lengths
    combined = str(sequence_length) + ":" + "".join(window_hashes)
    return hashlib.blake2b(combined.encode("ascii"), digest_size=16).hexdigest()
