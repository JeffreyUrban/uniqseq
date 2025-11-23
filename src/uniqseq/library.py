"""Sequence library management for uniqseq.

Handles loading and saving sequences from/to library directories.
Sequences are stored in native format (file content IS the sequence).
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

# Files to skip when reading sequences from directories
SKIP_FILES = {".DS_Store", ".gitignore", "README.md", "README.txt", ".keep"}


def compute_sequence_hash(sequence: Union[str, bytes], delimiter: Union[str, bytes]) -> str:
    """Compute hash for a sequence.

    Args:
        sequence: The sequence content (with delimiters between records, no trailing delimiter)
        delimiter: The delimiter used between records

    Returns:
        Hexadecimal hash string

    Note:
        Hash is computed on the raw sequence content including internal delimiters,
        but NOT including any trailing delimiter.
    """
    if isinstance(sequence, str):
        content = sequence.encode("utf-8")
    else:
        content = sequence

    return hashlib.sha256(content).hexdigest()[:12]  # Use first 12 chars for filename


def save_sequence_file(
    sequence: Union[str, bytes],
    delimiter: Union[str, bytes],
    sequences_dir: Path,
    byte_mode: bool = False,
) -> Path:
    """Save a sequence to a file in native format.

    Args:
        sequence: The sequence content (with delimiters, no trailing delimiter)
        delimiter: The delimiter used between records
        sequences_dir: Directory to save sequences in
        byte_mode: Whether this is binary mode

    Returns:
        Path to the saved file

    Note:
        Sequence files are saved WITHOUT a trailing delimiter.
        Filename is <hash>.uniqseq where hash is computed from the sequence.
    """
    sequences_dir.mkdir(parents=True, exist_ok=True)

    # Compute hash for filename
    seq_hash = compute_sequence_hash(sequence, delimiter)
    file_path = sequences_dir / f"{seq_hash}.uniqseq"

    # Write sequence in native format (no trailing delimiter)
    if byte_mode:
        assert isinstance(sequence, bytes), "Binary mode requires bytes sequence"
        file_path.write_bytes(sequence)
    else:
        assert isinstance(sequence, str), "Text mode requires str sequence"
        file_path.write_text(sequence, encoding="utf-8")

    return file_path


def load_sequence_file(
    file_path: Path,
    delimiter: Union[str, bytes],
    byte_mode: bool = False,
) -> Union[str, bytes]:
    """Load a sequence from a file.

    Args:
        file_path: Path to sequence file
        delimiter: The delimiter used between records
        byte_mode: Whether to load in binary mode

    Returns:
        The sequence content (with delimiters, no trailing delimiter)

    Raises:
        ValueError: If file cannot be decoded in text mode
    """
    if byte_mode:
        return file_path.read_bytes()
    else:
        try:
            return file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            raise ValueError(
                f"Cannot read sequence file {file_path} in text mode (not UTF-8)"
            ) from e


def load_sequences_from_directory(
    directory: Path,
    delimiter: Union[str, bytes],
    byte_mode: bool = False,
) -> dict[str, Union[str, bytes]]:
    """Load all sequences from a directory.

    Args:
        directory: Directory containing sequence files
        delimiter: The delimiter used between records
        byte_mode: Whether to load in binary mode

    Returns:
        Dictionary mapping hash -> sequence content

    Note:
        - Skips known noise files (README.md, .DS_Store, etc.)
        - Re-hashes each sequence based on current configuration
        - If loaded filename is .uniqseq and hash doesn't match, renames the file
    """
    if not directory.exists():
        return {}

    sequences = {}

    for file_path in directory.iterdir():
        # Skip directories
        if file_path.is_dir():
            continue

        # Skip known noise files
        if file_path.name in SKIP_FILES:
            continue

        try:
            # Load sequence
            sequence = load_sequence_file(file_path, delimiter, byte_mode)

            # Compute hash based on current configuration
            seq_hash = compute_sequence_hash(sequence, delimiter)

            # If this is a .uniqseq file and hash doesn't match filename, rename it
            if file_path.suffix == ".uniqseq":
                expected_name = f"{seq_hash}.uniqseq"
                if file_path.name != expected_name:
                    new_path = file_path.parent / expected_name
                    # Only rename if target doesn't exist
                    if not new_path.exists():
                        file_path.rename(new_path)

            sequences[seq_hash] = sequence

        except ValueError as e:
            # Re-raise with context about which file failed
            raise ValueError(
                f"Error loading sequence from {file_path}: {e}"
                + "\nSuggestion: Use --byte-mode or remove incompatible sequence files"
            ) from e

    return sequences


def save_metadata(
    library_dir: Path,
    window_size: int,
    max_history: Optional[int],
    delimiter: Union[str, bytes],
    byte_mode: bool,
    sequences_discovered: int,
    sequences_preloaded: int,
    sequences_saved: int,
    total_records_processed: int,
    records_skipped: int,
) -> Path:
    """Save metadata file for a library run.

    Args:
        library_dir: Library directory
        window_size: Window size used
        max_history: Max history size (None for unlimited)
        delimiter: Delimiter used
        byte_mode: Whether binary mode was used
        sequences_discovered: Number of newly discovered sequences
        sequences_preloaded: Number of sequences loaded from library
        sequences_saved: Number of sequences saved to library
        total_records_processed: Total records processed
        records_skipped: Records skipped (duplicates)

    Returns:
        Path to metadata file
    """
    # Create timestamped metadata directory
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    metadata_dir = library_dir / f"metadata-{timestamp}"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    # Format delimiter for JSON
    if byte_mode:
        assert isinstance(delimiter, bytes)
        delimiter_str = delimiter.hex()
    else:
        assert isinstance(delimiter, str)
        # Escape special characters for readability
        delimiter_str = delimiter.replace("\n", "\\n").replace("\t", "\\t").replace("\0", "\\0")

    # Create metadata
    metadata = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "window_size": window_size,
        "mode": "binary" if byte_mode else "text",
        "delimiter": delimiter_str,
        "max_history": max_history if max_history is not None else "unlimited",
        "sequences_discovered": sequences_discovered,
        "sequences_preloaded": sequences_preloaded,
        "sequences_saved": sequences_saved,
        "total_records_processed": total_records_processed,
        "records_skipped": records_skipped,
    }

    # Write metadata
    config_path = metadata_dir / "config.json"
    config_path.write_text(json.dumps(metadata, indent=2))

    return config_path
