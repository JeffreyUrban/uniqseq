"""Sequence library management for uniqseq.

Handles loading and saving sequences from/to library directories.
Sequences are stored in native format (file content IS the sequence).
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

# Files to skip when reading sequences from directories
SKIP_FILES = {".DS_Store", ".gitignore", "README.md", "README.txt", ".keep"}


def compute_sequence_hash(sequence: Union[str, bytes]) -> str:
    """Compute hash for a sequence based on its content.

    Args:
        sequence: The sequence content

    Returns:
        Hexadecimal hash string (32 characters from blake2b digest_size=16)

    Note:
        This is a simple content-based hash, independent of algorithm parameters
        like window_size, delimiter, or the deduplication algorithm's hash function.
    """
    import hashlib

    if isinstance(sequence, bytes):
        content = sequence
    else:
        content = sequence.encode("utf-8")

    return hashlib.blake2b(content, digest_size=16).hexdigest()


def save_sequence_file(
    sequence: Union[str, bytes], sequences_dir: Path, byte_mode: bool = False
) -> Path:
    """Save a sequence to a file in native format.

    Args:
        sequence: The sequence content (with delimiters, no trailing delimiter)
        sequences_dir: Directory to save sequences in
        byte_mode: Whether this is binary mode

    Returns:
        Path to the saved file

    Note:
        Sequence files are saved WITHOUT a trailing delimiter.
        Filename is <hash>.uniqseq where hash is computed from the sequence content.
    """
    sequences_dir.mkdir(parents=True, exist_ok=True)

    # Compute hash for filename based on content only
    seq_hash = compute_sequence_hash(sequence)
    file_path = sequences_dir / f"{seq_hash}.uniqseq"

    # Write sequence in native format (no trailing delimiter)
    if byte_mode:
        assert isinstance(sequence, bytes), "Binary mode requires bytes sequence"
        file_path.write_bytes(sequence)
    else:
        assert isinstance(sequence, str), "Text mode requires str sequence"
        file_path.write_text(sequence, encoding="utf-8")

    return file_path


def load_sequence_file(file_path: Path, byte_mode: bool = False) -> Union[str, bytes]:
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
    window_size: int,
    byte_mode: bool = False,
) -> set[Union[str, bytes]]:
    """Load all sequences from a directory.

    Args:
        directory: Directory containing sequence files
        delimiter: The delimiter used between records
        window_size: The window size used for hashing
        byte_mode: Whether to load in binary mode

    Returns:
        Set of sequence content strings/bytes

    Note:
        - Skips known noise files (README.md, .DS_Store, etc.)
        - Re-hashes each sequence based on current configuration
        - If loaded filename is .uniqseq and hash doesn't match, renames the file
    """
    if not directory.exists():
        return set()

    sequences = set()

    for file_path in directory.iterdir():
        # Skip directories
        if file_path.is_dir():
            continue

        # Skip known noise files
        if file_path.name in SKIP_FILES:
            continue

        try:
            # Load sequence
            sequence = load_sequence_file(file_path, byte_mode)

            # Compute hash based on content
            seq_hash = compute_sequence_hash(sequence)

            # If this is a .uniqseq file and hash doesn't match filename, rename it
            if file_path.suffix == ".uniqseq":
                expected_name = f"{seq_hash}.uniqseq"
                if file_path.name != expected_name:
                    new_path = file_path.parent / expected_name
                    # Only rename if target doesn't exist
                    if not new_path.exists():
                        file_path.rename(new_path)

            sequences.add(sequence)

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
    max_unique_sequences: Optional[int],
    delimiter: Union[str, bytes],
    byte_mode: bool,
    sequences_discovered: int,
    sequences_preloaded: int,
    sequences_saved: int,
    total_records_processed: int,
    records_skipped: int,
    metadata_dir: Optional[Path] = None,
) -> Path:
    """Save metadata file for a library run.

    Args:
        library_dir: Library directory
        window_size: Window size used
        max_history: Max history size (None for unlimited)
        max_unique_sequences: Max unique sequences to track
        delimiter: Delimiter used
        byte_mode: Whether binary mode was used
        sequences_discovered: Number of newly discovered sequences
        sequences_preloaded: Number of sequences loaded from library
        sequences_saved: Number of sequences saved to library
        total_records_processed: Total records processed
        records_skipped: Records skipped (duplicates)
        metadata_dir: Optional existing metadata directory to use (if None, creates new one)

    Returns:
        Path to metadata file
    """
    # Create or use existing timestamped metadata directory
    if metadata_dir is None:
        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y%m%d-%H%M%S")
        microseconds = now.strftime("%f")
        metadata_dir = library_dir / f"metadata-{timestamp}-{microseconds}"
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
        "max_unique_sequences": max_unique_sequences
        if max_unique_sequences is not None
        else "unlimited",
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


def save_progress(
    progress_file: Path,
    total_sequences: int,
    sequences_preloaded: int,
    sequences_discovered: int,
    sequences_saved: int,
    total_records_processed: int,
    records_skipped: int,
) -> None:
    """Save progress file for monitoring long-running jobs.

    Uses atomic write (temp file + rename) to prevent partial reads.

    Args:
        progress_file: Path to progress.json file
        total_sequences: Total unique sequences tracked
        sequences_preloaded: Number of sequences loaded from library
        sequences_discovered: Number of newly discovered sequences
        sequences_saved: Number of sequences saved to library
        total_records_processed: Total records processed so far
        records_skipped: Records skipped (duplicates) so far
    """
    progress_data = {
        "last_update": datetime.now(timezone.utc).isoformat(),
        "total_sequences": total_sequences,
        "sequences_preloaded": sequences_preloaded,
        "sequences_discovered": sequences_discovered,
        "sequences_saved": sequences_saved,
        "total_records_processed": total_records_processed,
        "records_skipped": records_skipped,
    }

    # Atomic write: write to temp file, then rename
    temp_file = progress_file.parent / f".{progress_file.name}.tmp"
    temp_file.write_text(json.dumps(progress_data, indent=2))
    temp_file.replace(progress_file)  # Atomic rename
