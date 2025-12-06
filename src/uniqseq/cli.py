"""Command-line interface for uniqseq."""

import json
import re
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO, Callable, Optional, TextIO, Union

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table

from . import __version__
from .uniqseq import (
    DEFAULT_MAX_CANDIDATES,
    DEFAULT_MAX_HISTORY,
    DEFAULT_MAX_UNIQUE_SEQUENCES,
    MIN_SEQUENCE_LENGTH,
    FilterPattern,
    UniqSeq,
)

app = typer.Typer(
    name="uniqseq",
    help="Stream-based deduplication for repeating sequences",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
)

console = Console(stderr=True)  # All output to stderr to preserve stdout for data


def version_callback(value: bool) -> None:
    """Print version and exit if --version flag is provided."""
    if value:
        typer.echo(f"uniqseq version {__version__}")
        raise typer.Exit()


def read_records(stream: TextIO, delimiter: str = "\n") -> Iterator[str]:
    """Read records from stream using custom delimiter (text mode).

    Args:
        stream: Input stream (file or stdin)
        delimiter: Record delimiter (default: newline)

    Yields:
        Individual records (without trailing delimiter)
    """
    if delimiter == "\n":
        # Fast path for default newline delimiter
        for line in stream:
            yield line.rstrip("\n")
    else:
        # Custom delimiter: read all content and split
        content = stream.read()
        if not content:
            return

        # Handle escape sequences
        delimiter = delimiter.replace("\\n", "\n").replace("\\t", "\t").replace("\\0", "\0")

        # Split by delimiter
        records = content.split(delimiter)

        # Emit all records except last if empty (trailing delimiter case)
        for i, record in enumerate(records):
            if i == len(records) - 1 and not record:
                # Last record is empty - was a trailing delimiter
                continue
            yield record


def read_records_binary(stream: BinaryIO, delimiter: bytes = b"\n") -> Iterator[bytes]:
    """Read records from stream using custom delimiter (binary mode).

    Args:
        stream: Input stream (file or stdin in binary mode)
        delimiter: Record delimiter (default: newline bytes)

    Yields:
        Individual records (without trailing delimiter)
    """
    if delimiter == b"\n":
        # Fast path for default newline delimiter
        for line in stream:
            yield line.rstrip(b"\n")
    else:
        # Custom delimiter: read all content and split
        content = stream.read()
        if not content:
            return

        # Split by delimiter
        records = content.split(delimiter)

        # Emit all records except last if empty (trailing delimiter case)
        for i, record in enumerate(records):
            if i == len(records) - 1 and not record:
                # Last record is empty - was a trailing delimiter
                continue
            yield record


def parse_hex_delimiter(hex_string: str) -> bytes:
    """Parse hex string delimiter to bytes.

    Args:
        hex_string: Hex string like "0x00", "00", or "0a0d"

    Returns:
        Bytes delimiter

    Raises:
        ValueError: If hex string is invalid
    """
    # Remove 0x prefix if present
    if hex_string.startswith("0x") or hex_string.startswith("0X"):
        hex_string = hex_string[2:]

    # Validate hex string
    if not hex_string:
        raise ValueError("Empty hex delimiter")

    if len(hex_string) % 2 != 0:
        raise ValueError(
            f"Hex delimiter must have even number of characters, got {len(hex_string)}"
        )

    try:
        return bytes.fromhex(hex_string)
    except ValueError as e:
        raise ValueError(f"Invalid hex delimiter '{hex_string}': {e}") from e


def convert_delimiter_escapes(delimiter: str) -> str:
    """Convert escape sequences in delimiter string for text mode.

    Args:
        delimiter: String delimiter with possible escape sequences

    Returns:
        String with escape sequences converted
    """
    # Handle common escape sequences
    return delimiter.replace("\\n", "\n").replace("\\t", "\t").replace("\\0", "\0")


def convert_delimiter_to_bytes(delimiter: str) -> bytes:
    """Convert string delimiter to bytes for binary mode.

    Args:
        delimiter: String delimiter with possible escape sequences

    Returns:
        Bytes delimiter
    """
    # Handle escape sequences then convert to bytes
    delimiter = convert_delimiter_escapes(delimiter)
    return delimiter.encode("latin1")  # Use latin1 to preserve byte values


def load_patterns_from_file(file_path: Path) -> list[str]:
    """Load regex patterns from file.

    File format:
    - One pattern per line
    - Lines starting with # are comments (ignored)
    - Blank lines are ignored
    - Leading/trailing whitespace is stripped

    Args:
        file_path: Path to pattern file

    Returns:
        List of pattern strings

    Raises:
        typer.Exit: If file cannot be read
    """
    patterns = []
    try:
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                # Strip whitespace
                line = line.strip()

                # Skip blank lines and comments
                if not line or line.startswith("#"):
                    continue

                patterns.append(line)

    except OSError as e:
        console.print(
            f"[red]Error:[/red] Could not read pattern file '{file_path}': {e}",
            style="red",
        )
        raise typer.Exit(code=1) from e

    return patterns


def create_hash_transform(
    command: str, byte_mode: bool = False, delimiter: Union[str, bytes] = "\n"
) -> Callable[[Union[str, bytes]], Union[str, bytes]]:
    """Create a hash transform function from a shell command.

    Args:
        command: Shell command to pipe each line through
        byte_mode: If True, operates on bytes instead of text
        delimiter: Delimiter to use (str for text mode, bytes for byte mode)

    Returns:
        Function that transforms a line using the command

    Raises:
        RuntimeError: If transform produces no output or multiple lines
    """

    def transform_line(line: Union[str, bytes]) -> Union[str, bytes]:
        """Transform line through shell command."""
        try:
            # Prepare input based on mode
            input_data: Union[str, bytes]
            if byte_mode:
                # Binary mode: pass bytes directly
                assert isinstance(line, bytes)
                assert isinstance(delimiter, bytes)
                input_data = line + delimiter
                text_mode = False
            else:
                # Text mode: pass string
                assert isinstance(line, str)
                input_data = line + "\n"
                text_mode = True

            # Run command with line as stdin
            result = subprocess.run(
                command,
                input=input_data,
                capture_output=True,
                text=text_mode,
                shell=True,
                timeout=5,  # 5 second timeout per line
            )

            # Note: We don't check return code - many commands (like grep) return non-zero
            # for "no match", which is valid (empty output hashes as empty)

            # Get output and strip delimiter
            output: Union[str, bytes]
            if byte_mode:
                # Binary mode: strip delimiter bytes
                assert isinstance(delimiter, bytes)
                output_bytes: bytes = result.stdout
                if output_bytes.endswith(delimiter):
                    output_bytes = output_bytes[: -len(delimiter)]

                # Validate: no embedded delimiters (would create multiple records)
                if delimiter in output_bytes:
                    raise RuntimeError(
                        f"Hash transform produced multiple records (embedded delimiter found).\n\n"
                        f"The --hash-transform command must output exactly one record per input.\n"
                        f"Empty output is valid, but the transform cannot split records.\n\n"
                        f"Transform: {command}\n"
                        f"Delimiter: {delimiter!r}\n\n"
                        f"For splitting records, preprocess the input before piping to uniqseq."
                    )
                output = output_bytes
            else:
                # Text mode: strip trailing newline
                output_str: str = result.stdout.rstrip("\n")

                # Validate: must produce exactly one line
                if "\n" in output_str:
                    output_line_count = output_str.count("\n") + 1
                    raise RuntimeError(
                        f"Hash transform produced multiple lines (expected exactly one).\n\n"
                        f"The --hash-transform command must output exactly one line per input "
                        f"line.\nEmpty output lines are valid, but the transform cannot split "
                        f"lines.\n\nInput line: {line!r}\nTransform: {command}\n"
                        f"Output lines: {output_line_count}\n\n"
                        f"For splitting lines, preprocess the input before piping to uniqseq."
                    )
                output = output_str

            return output

        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                f"Hash transform command timed out after 5 seconds: {command}\nInput: {line!r}"
            ) from e

    return transform_line


def validate_arguments(
    window_size: int,
    max_history: Optional[int],
    unlimited_history: bool,
    max_unique_sequences: int,
    unlimited_unique_sequences: bool,
    max_candidates: int,
    unlimited_candidates: bool,
    stats_format: str,
    byte_mode: bool,
    delimiter: Optional[str],
    delimiter_hex: Optional[str],
    hash_transform: Optional[str],
    annotate: bool,
    annotation_format: Optional[str],
) -> None:
    """Validate argument combinations and constraints.

    Args:
        window_size: Minimum sequence length to detect
        max_history: Maximum depth of history (or None if unlimited)
        unlimited_history: Whether unlimited history mode is enabled
        max_unique_sequences: Maximum number of unique sequences to track
        unlimited_unique_sequences: Whether unlimited unique sequence tracking is enabled
        max_candidates: Maximum concurrent candidates to track
        unlimited_candidates: Whether unlimited candidate tracking is enabled
        stats_format: Statistics output format
        byte_mode: Whether binary mode is enabled
        delimiter: Text delimiter (or None)
        delimiter_hex: Hex delimiter (or None)
        hash_transform: Hash transform command (or None)

    Raises:
        typer.BadParameter: If validation fails with clear message
    """
    # Semantic validation: unlimited and max_history are mutually exclusive
    if unlimited_history and max_history != DEFAULT_MAX_HISTORY:
        raise typer.BadParameter(
            "--unlimited-history and --max-history are mutually exclusive. "
            "Use --unlimited-history for unbounded history, or --max-history with a specific limit."
        )

    # Semantic validation: unlimited and max_unique_sequences are mutually exclusive
    if unlimited_unique_sequences and max_unique_sequences != DEFAULT_MAX_UNIQUE_SEQUENCES:
        raise typer.BadParameter(
            "--unlimited-unique-sequences and --max-unique-sequences are mutually exclusive. "
            "Use --unlimited-unique-sequences for unbounded tracking, "
            "or --max-unique-sequences with a specific limit."
        )

    # Semantic validation: unlimited and max_candidates are mutually exclusive
    if unlimited_candidates and max_candidates != DEFAULT_MAX_CANDIDATES:
        raise typer.BadParameter(
            "--unlimited-candidates and --max-candidates are mutually exclusive. "
            "Use --unlimited-candidates for unbounded candidate tracking, "
            "or --max-candidates with a specific limit."
        )

    # Semantic validation: window must fit within history (if limited)
    if max_history is not None and window_size > max_history:
        raise typer.BadParameter(
            f"--window-size ({window_size}) cannot exceed --max-history ({max_history}). "
            f"The window must fit within the history buffer."
        )

    # Validate stats format
    valid_formats = {"table", "json"}
    if stats_format not in valid_formats:
        raise typer.BadParameter(
            f"--stats-format must be one of {valid_formats}, got '{stats_format}'"
        )

    # Validate delimiter combinations
    if delimiter_hex is not None and delimiter != "\n":
        raise typer.BadParameter(
            "--delimiter and --delimiter-hex are mutually exclusive. "
            "Specify only one delimiter type."
        )

    # Validate delimiter-hex requires byte mode
    if delimiter_hex is not None and not byte_mode:
        raise typer.BadParameter(
            "--delimiter-hex requires --byte-mode. Use --byte-mode for binary delimiter processing."
        )

    # Validate delimiter (non-default) incompatible with byte mode
    if byte_mode and delimiter != "\n":
        raise typer.BadParameter(
            "--delimiter is incompatible with --byte-mode. Use --delimiter-hex for binary mode."
        )

    # Note: hash-transform now works with byte mode (no validation needed)

    # Validate annotation-format requires annotate
    if annotation_format is not None and not annotate:
        raise typer.BadParameter(
            "--annotation-format requires --annotate. "
            "Use --annotate to enable annotations with custom format."
        )


@app.command()
def main(
    input_file: Optional[Path] = typer.Argument(
        None,
        help="Input file to deduplicate (reads from stdin if not specified)",
        exists=True,
        dir_okay=False,
    ),
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
    # Core Deduplication
    window_size: int = typer.Option(
        MIN_SEQUENCE_LENGTH,
        "--window-size",
        "-w",
        help="Minimum number of consecutive records to detect a duplicate sequence"
        " (records are lines by default, or custom delimited units)",
        min=1,
        rich_help_panel="Core Deduplication",
    ),
    max_history: int = typer.Option(
        DEFAULT_MAX_HISTORY,
        "--max-history",
        "-m",
        help="Maximum depth of history (lines matched against)",
        min=0,
        rich_help_panel="Core Deduplication",
    ),
    unlimited_history: bool = typer.Option(
        False,
        "--unlimited-history",
        "-M",
        help=("Unlimited history depth (suitable for file processing, use caution with streaming)"),
        rich_help_panel="Core Deduplication",
    ),
    max_unique_sequences: int = typer.Option(
        DEFAULT_MAX_UNIQUE_SEQUENCES,
        "--max-unique-sequences",
        "-u",
        help="Maximum number of unique sequences to track (LRU-evicted when exceeded)",
        min=1,
        rich_help_panel="Core Deduplication",
    ),
    unlimited_unique_sequences: bool = typer.Option(
        False,
        "--unlimited-unique-sequences",
        "-U",
        help=(
            "Unlimited unique sequence tracking "
            "(suitable for file processing, use caution with streaming)"
        ),
        rich_help_panel="Core Deduplication",
    ),
    max_candidates: int = typer.Option(
        DEFAULT_MAX_CANDIDATES,
        "--max-candidates",
        "-c",
        help="Maximum concurrent candidates to track (lower = faster, may miss patterns)",
        min=1,
        rich_help_panel="Core Deduplication",
    ),
    unlimited_candidates: bool = typer.Option(
        False,
        "--unlimited-candidates",
        "-C",
        help=(
            "Unlimited candidate tracking "
            "(more accurate but slower, suitable for comprehensive analysis)"
        ),
        rich_help_panel="Core Deduplication",
    ),
    skip_chars: int = typer.Option(
        0,
        "--skip-chars",
        "-s",
        help="Skip N characters from start of each line when hashing (e.g., timestamps)",
        min=0,
        rich_help_panel="Core Deduplication",
    ),
    hash_transform: Optional[str] = typer.Option(
        None,
        "--hash-transform",
        "-t",
        help="Pipe each line through command for hashing (preserves original). Empty output OK.",
        rich_help_panel="Core Deduplication",
    ),
    # Input Format
    byte_mode: bool = typer.Option(
        False,
        "--byte-mode",
        "-b",
        help="Process files in binary mode (for binary data, mixed encodings)",
        rich_help_panel="Input Format",
    ),
    delimiter: str = typer.Option(
        "\n",
        "--delimiter",
        "-d",
        help="Record delimiter (default: newline). Supports escape sequences: \\n, \\t, \\0",
        rich_help_panel="Input Format",
        show_default="\\n",
    ),
    delimiter_hex: Optional[str] = typer.Option(
        None,
        "--delimiter-hex",
        "-x",
        help="Hex delimiter (e.g., '00' or '0x0a0d'). Requires --byte-mode.",
        rich_help_panel="Input Format",
    ),
    # StdOut Control
    inverse: bool = typer.Option(
        False,
        "--inverse",
        "-i",
        help="Inverse mode: keep duplicates, remove unique sequences. "
        "Outputs only lines that appear in duplicate sequences (2+ times).",
        rich_help_panel="StdOut Control",
    ),
    annotate: bool = typer.Option(
        False,
        "--annotate",
        "-a",
        help="Add inline markers showing where duplicates were skipped. "
        "Format: [DUPLICATE: Lines X-Y matched lines A-B (sequence seen N times)].",
        rich_help_panel="StdOut Control",
    ),
    annotation_format: Optional[str] = typer.Option(
        None,
        "--annotation-format",
        help="Custom annotation template. Variables: {start}, {end}, {match_start}, "
        "{match_end}, {count}, {window_size}. "
        "Example: 'SKIP|{start}|{end}|{count}'",
        rich_help_panel="StdOut Control",
    ),
    # StdErr Control
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress statistics output to stderr",
        rich_help_panel="StdErr Control",
    ),
    progress: bool = typer.Option(
        False,
        "--progress",
        "-p",
        help="Show progress indicator (auto-disabled for pipes)",
        rich_help_panel="StdErr Control",
    ),
    stats_format: str = typer.Option(
        "table",
        "--stats-format",
        help="Statistics output format: 'table' (default, Rich table) or 'json' (machine-readable)",
        rich_help_panel="StdErr Control",
    ),
    explain: bool = typer.Option(
        False,
        "--explain",
        "-e",
        help="Show explanations to stderr for why lines were kept or skipped",
        rich_help_panel="StdErr Control",
    ),
    # Sequence Libraries
    read_sequences: Optional[list[Path]] = typer.Option(
        None,
        "--read-sequences",
        "-r",
        help="Load sequences from directory (can specify multiple times). "
        "Treats loaded sequences as 'already seen'.",
        exists=True,
        dir_okay=True,
        file_okay=False,
        rich_help_panel="Sequence Libraries",
    ),
    library_dir: Optional[Path] = typer.Option(
        None,
        "--library-dir",
        "-l",
        help="Library directory: load existing sequences and save observed sequences",
        dir_okay=True,
        file_okay=False,
        rich_help_panel="Sequence Libraries",
    ),
    # Pattern Filtering
    track: Optional[list[str]] = typer.Option(
        None,
        "--track",
        help="Include lines matching regex pattern for deduplication (can specify multiple times). "
        "First matching pattern wins.",
        rich_help_panel="Pattern Filtering",
    ),
    track_file: Optional[list[Path]] = typer.Option(
        None,
        "--track-file",
        help="Load track patterns from file (one regex per line, # for comments). "
        "Can specify multiple times. Evaluated in command-line order.",
        exists=True,
        dir_okay=False,
        rich_help_panel="Pattern Filtering",
    ),
    bypass: Optional[list[str]] = typer.Option(
        None,
        "--bypass",
        help="Bypass deduplication for lines matching regex pattern (pass through unchanged). "
        "First matching pattern wins.",
        rich_help_panel="Pattern Filtering",
    ),
    bypass_file: Optional[list[Path]] = typer.Option(
        None,
        "--bypass-file",
        help="Load bypass patterns from file (one regex per line, # for comments). "
        "Can specify multiple times. Evaluated in command-line order.",
        exists=True,
        dir_okay=False,
        rich_help_panel="Pattern Filtering",
    ),
) -> None:
    """
    Remove duplicate record sequences from streaming input.

    This tool detects and removes repeated sequences of records (minimum 10 records by default)
    while preserving all unique content. Designed for reducing redundancy in logs where
    content is frequently re-displayed.

    \b
    Quick Start:
        uniqseq input.log > output.log              # Deduplicate a file
        cat verbose.log | uniqseq                   # Use in pipeline
        uniqseq --window-size 5 input.log           # Detect 5-line patterns

    \b
    More Examples:
        uniqseq --progress large.log > clean.log    # Show live progress
        uniqseq --quiet input.log > output.log      # No statistics
        uniqseq --inverse input.log                 # Show only duplicates
        uniqseq --annotate input.log                # Mark where duplicates removed

    \b
    Documentation:
        https://github.com/JeffreyUrban/uniqseq

    \b
    Report Issues:
        https://github.com/JeffreyUrban/uniqseq/issues
    """
    # Check if running interactively with no input
    if input_file is None and sys.stdin.isatty():
        console.print("[yellow]No input provided.[/yellow]")
        console.print("\n[bold]Usage:[/bold] uniqseq [FILE] or pipe data via stdin")
        console.print("\n[bold]Examples:[/bold]")
        console.print("  uniqseq input.log > output.log")
        console.print("  cat input.log | uniqseq")
        console.print("  tail -f app.log | uniqseq")
        console.print("\n[dim]For full help: uniqseq --help[/dim]")
        raise typer.Exit(0)

    # Validate arguments
    validate_arguments(
        window_size,
        max_history,
        unlimited_history,
        max_unique_sequences,
        unlimited_unique_sequences,
        max_candidates,
        unlimited_candidates,
        stats_format,
        byte_mode,
        delimiter,
        delimiter_hex,
        hash_transform,
        annotate,
        annotation_format,
    )

    # Disable progress if outputting to a pipe
    show_progress = progress and sys.stdout.isatty()

    # Auto-detect streaming vs file mode
    # If user hasn't explicitly set history mode, use smart defaults:
    # - File input: unlimited history (can process entire file)
    # - Stdin/pipe: limited history (memory-bounded streaming)
    user_set_history = unlimited_history or max_history != DEFAULT_MAX_HISTORY

    if unlimited_history:
        effective_max_history = None
    elif user_set_history:
        # User explicitly set max_history
        effective_max_history = max_history
    elif input_file is not None:
        # File mode: auto-enable unlimited history
        effective_max_history = None
        if not quiet:
            console.print(
                "[dim]Auto-detected file input: using unlimited history "
                "(override with --max-history)[/dim]"
            )
    else:
        # Streaming mode: use limited history
        effective_max_history = max_history

    # Handle unlimited unique sequences
    if unlimited_unique_sequences:
        effective_max_unique_sequences: Optional[int] = None
    else:
        effective_max_unique_sequences = max_unique_sequences

    # Handle unlimited candidates
    if unlimited_candidates:
        effective_max_candidates: Optional[int] = None
    else:
        effective_max_candidates = max_candidates

    # Prepare delimiter based on mode
    if byte_mode:
        # Determine delimiter for binary mode
        if delimiter_hex is not None:
            try:
                delimiter_bytes = parse_hex_delimiter(delimiter_hex)
            except ValueError as e:
                console.print(f"[red]Error:[/red] {e}")
                raise typer.Exit(1) from e
        else:
            delimiter_bytes = convert_delimiter_to_bytes(delimiter)
        output_stream: Union[TextIO, BinaryIO] = sys.stdout.buffer
        effective_delimiter: Union[str, bytes] = delimiter_bytes
    else:
        # Text mode: convert escape sequences in delimiter
        delimiter_bytes = b""  # Placeholder, won't be used in text mode
        output_stream = sys.stdout
        effective_delimiter = convert_delimiter_escapes(delimiter)

    # Create hash transform callable if specified
    transform_fn = None
    if hash_transform is not None:
        try:
            transform_fn = create_hash_transform(hash_transform, byte_mode, effective_delimiter)
        except Exception as e:
            console.print(f"[red]Error creating hash transform:[/red] {e}")
            raise typer.Exit(1) from e

    # Load pre-loaded sequences from --read-sequences and --library-dir
    preloaded_sequences: set[Union[str, bytes]] = set()
    sequences_dir: Optional[Path] = None

    # Import library functions
    from .library import load_sequences_from_directory

    # Load from --read-sequences directories
    if read_sequences:
        for seq_dir in read_sequences:
            try:
                sequences = load_sequences_from_directory(
                    seq_dir, effective_delimiter, window_size, byte_mode
                )
                preloaded_sequences.update(sequences)
            except ValueError as e:
                console.print(f"[red]Error loading sequences from {seq_dir}:[/red] {e}")
                raise typer.Exit(1) from e

    # Load from --library-dir
    if library_dir:
        sequences_dir = library_dir / "sequences"
        if sequences_dir.exists():
            try:
                sequences = load_sequences_from_directory(
                    sequences_dir, effective_delimiter, window_size, byte_mode
                )
                preloaded_sequences.update(sequences)
            except ValueError as e:
                console.print(f"[red]Error loading library from {library_dir}:[/red] {e}")
                raise typer.Exit(1) from e

    # Create save callback for library mode
    save_callback = None
    saved_sequences: set[str] = set()

    if library_dir:
        from .library import compute_sequence_hash, save_sequence_file

        sequences_dir = library_dir / "sequences"

        def save_sequence_callback(file_content: Union[str, bytes]) -> None:
            """Save sequence to library directory."""
            # Compute hash from file content
            seq_hash = compute_sequence_hash(file_content)

            if seq_hash in saved_sequences:
                return  # Already saved

            try:
                save_sequence_file(file_content, sequences_dir, byte_mode)
                saved_sequences.add(seq_hash)
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to save sequence {seq_hash}:[/yellow] {e}")

        save_callback = save_sequence_callback

        # Create metadata directory for progress tracking
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y%m%d-%H%M%S")
        microseconds = now.strftime("%f")
        metadata_dir = library_dir / f"metadata-{timestamp}-{microseconds}"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        progress_file = metadata_dir / "progress.json"
    else:
        metadata_dir = None
        progress_file = None

    # Compile filter patterns (sequential evaluation: first match wins)
    # Order: inline track, track files, inline bypass, bypass files
    filter_patterns: list[FilterPattern] = []
    if track or bypass or track_file or bypass_file:
        # Track patterns (include for deduplication)
        # Process inline track patterns first
        if track:
            for pattern_str in track:
                try:
                    compiled = re.compile(pattern_str)
                    filter_patterns.append(
                        FilterPattern(pattern=pattern_str, action="track", regex=compiled)
                    )
                except re.error as e:
                    console.print(
                        f"[red]Error:[/red] Invalid track pattern '{pattern_str}': {e}",
                        style="red",
                    )
                    raise typer.Exit(code=1) from e

        # Process track pattern files
        if track_file:
            for file_path in track_file:
                patterns_from_file = load_patterns_from_file(file_path)
                for pattern_str in patterns_from_file:
                    try:
                        compiled = re.compile(pattern_str)
                        filter_patterns.append(
                            FilterPattern(pattern=pattern_str, action="track", regex=compiled)
                        )
                    except re.error as e:
                        console.print(
                            f"[red]Error:[/red] Invalid track pattern '{pattern_str}' "
                            f"from file '{file_path}': {e}",
                            style="red",
                        )
                        raise typer.Exit(code=1) from e

        # Bypass patterns (exclude from deduplication)
        # Process inline bypass patterns
        if bypass:
            for pattern_str in bypass:
                try:
                    compiled = re.compile(pattern_str)
                    filter_patterns.append(
                        FilterPattern(pattern=pattern_str, action="bypass", regex=compiled)
                    )
                except re.error as e:
                    console.print(
                        f"[red]Error:[/red] Invalid bypass pattern '{pattern_str}': {e}",
                        style="red",
                    )
                    raise typer.Exit(code=1) from e

        # Process bypass pattern files
        if bypass_file:
            for file_path in bypass_file:
                patterns_from_file = load_patterns_from_file(file_path)
                for pattern_str in patterns_from_file:
                    try:
                        compiled = re.compile(pattern_str)
                        filter_patterns.append(
                            FilterPattern(pattern=pattern_str, action="bypass", regex=compiled)
                        )
                    except re.error as e:
                        console.print(
                            f"[red]Error:[/red] Invalid bypass pattern '{pattern_str}' "
                            f"from file '{file_path}': {e}",
                            style="red",
                        )
                        raise typer.Exit(code=1) from e

    # Validate: filters require text mode
    if filter_patterns and byte_mode:
        console.print(
            "[red]Error:[/red] Filter patterns (--track, --bypass, --track-file, --bypass-file) "
            "require text mode (incompatible with --byte-mode)",
            style="red",
        )
        raise typer.Exit(code=1)

    # Create uniqseq
    uniqseq = UniqSeq(
        window_size=window_size,
        max_history=effective_max_history,
        max_unique_sequences=effective_max_unique_sequences,
        max_candidates=effective_max_candidates,
        skip_chars=skip_chars,
        hash_transform=transform_fn,
        delimiter=effective_delimiter,
        preloaded_sequences=preloaded_sequences if preloaded_sequences else None,
        save_sequence_callback=save_callback,
        filter_patterns=filter_patterns if filter_patterns else None,
        inverse=inverse,
        annotate=annotate,
        annotation_format=annotation_format,
        explain=explain,
    )

    try:
        # Create progress callback for library monitoring (independent of visual progress)
        progress_callback = None
        if progress_file:

            def library_progress_callback(
                line_num: int, lines_skipped: int, seq_count: int
            ) -> None:
                """Update progress.json for library mode monitoring."""
                from .library import save_progress

                num_preloaded = len(preloaded_sequences)
                num_saved = len(saved_sequences)

                try:
                    save_progress(
                        progress_file=progress_file,
                        total_sequences=seq_count,
                        sequences_preloaded=num_preloaded,
                        sequences_discovered=seq_count,
                        sequences_saved=num_saved,
                        total_records_processed=line_num,
                        records_skipped=lines_skipped,
                    )
                except Exception:
                    pass  # Silent failure to avoid spamming console

            progress_callback = library_progress_callback

        if show_progress:
            # Create progress display
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TextColumn("• Skipped: {task.fields[skipped]:,}"),
                TextColumn("• Redundancy: {task.fields[redundancy]:.1f}%"),
                TextColumn("• Sequences: {task.fields[sequences]:,}"),
                console=console,
                transient=True,
            ) as progress_bar:
                task = progress_bar.add_task(
                    "Processing lines...",
                    total=None,
                    skipped=0,
                    redundancy=0.0,
                    sequences=0,
                )

                def update_progress(line_num: int, lines_skipped: int, seq_count: int) -> None:
                    redundancy = 100 * lines_skipped / line_num if line_num > 0 else 0
                    progress_bar.update(
                        task,
                        completed=line_num,
                        skipped=lines_skipped,
                        redundancy=redundancy,
                        sequences=seq_count,
                    )

                    # Chain to library progress callback if it exists
                    if progress_callback:
                        progress_callback(line_num, lines_skipped, seq_count)

                # Read input with progress
                if input_file:
                    if byte_mode:
                        with open(input_file, "rb") as f:
                            for record in read_records_binary(f, delimiter_bytes):
                                uniqseq.process_line(
                                    record, output_stream, progress_callback=update_progress
                                )
                    else:
                        with open(input_file) as f:  # type: ignore[assignment]
                            for record in read_records(f, delimiter):  # type: ignore[arg-type,assignment]
                                uniqseq.process_line(
                                    record, output_stream, progress_callback=update_progress
                                )
                else:
                    if byte_mode:
                        for record in read_records_binary(sys.stdin.buffer, delimiter_bytes):
                            uniqseq.process_line(
                                record, output_stream, progress_callback=update_progress
                            )
                    else:
                        for record in read_records(sys.stdin, delimiter):  # type: ignore[assignment]
                            uniqseq.process_line(
                                record, output_stream, progress_callback=update_progress
                            )

                # Flush remaining buffer
                uniqseq.flush(output_stream)
        else:
            # Read input without visual progress (but may still have library progress callback)
            if input_file:
                if not quiet:
                    console.print(f"[cyan]Processing:[/cyan] {input_file}", style="dim")

                if byte_mode:
                    with open(input_file, "rb") as f:
                        for record in read_records_binary(f, delimiter_bytes):
                            uniqseq.process_line(
                                record, output_stream, progress_callback=progress_callback
                            )
                else:
                    with open(input_file) as f:  # type: ignore[assignment]
                        for record in read_records(f, delimiter):  # type: ignore[arg-type,assignment]
                            uniqseq.process_line(
                                record, output_stream, progress_callback=progress_callback
                            )
            else:
                # Reading from stdin - check if it's a pipe
                if not sys.stdin.isatty():
                    if not quiet:
                        console.print("[cyan]Reading from stdin...[/cyan]", style="dim")

                if byte_mode:
                    for record in read_records_binary(sys.stdin.buffer, delimiter_bytes):
                        uniqseq.process_line(
                            record, output_stream, progress_callback=progress_callback
                        )
                else:
                    for record in read_records(sys.stdin, delimiter):  # type: ignore[assignment]
                        uniqseq.process_line(
                            record, output_stream, progress_callback=progress_callback
                        )

            # Flush remaining buffer
            uniqseq.flush(output_stream)

        # Print stats to stderr unless quiet
        if not quiet:
            if stats_format == "json":
                print_stats_json(uniqseq)
            else:
                print_stats(uniqseq)

        # Save metadata if using library mode
        if library_dir:
            from .library import save_metadata

            num_preloaded = len(preloaded_sequences)
            num_saved = len(saved_sequences)
            num_discovered = len(uniqseq.sequence_records)

            try:
                save_metadata(
                    library_dir=library_dir,
                    window_size=window_size,
                    max_history=effective_max_history,
                    max_unique_sequences=effective_max_unique_sequences,
                    delimiter=effective_delimiter,
                    byte_mode=byte_mode,
                    sequences_discovered=num_discovered,
                    sequences_preloaded=num_preloaded,
                    sequences_saved=num_saved,
                    total_records_processed=uniqseq.line_num_input,
                    records_skipped=uniqseq.lines_skipped,
                    metadata_dir=metadata_dir,  # Use existing metadata_dir from progress tracking
                )
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to save metadata:[/yellow] {e}")

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        # Flush what we have
        if byte_mode:
            uniqseq.flush(sys.stdout.buffer)
        else:
            uniqseq.flush(sys.stdout)
        if not quiet:
            if stats_format == "json":
                print_stats_json(uniqseq)
            else:
                console.print("[dim]Partial statistics:[/dim]")
                print_stats(uniqseq)
        raise typer.Exit(1) from None
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


def print_stats(uniqseq: UniqSeq) -> None:
    """Print deduplication statistics using rich."""
    stats = uniqseq.get_stats()

    if stats["total"] == 0:
        console.print("[yellow]No lines processed[/yellow]")
        return

    # Create stats table
    table = Table(title="Deduplication Statistics", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", justify="right", style="green")

    table.add_row("Total lines processed", f"{stats['total']:,}")
    table.add_row("Lines emitted", f"{stats['emitted']:,}")
    table.add_row("Lines skipped", f"{stats['skipped']:,}")
    table.add_row("Redundancy", f"{stats['redundancy_pct']:.1f}%")
    table.add_row("Unique sequences tracked", f"{stats['unique_sequences']:,}")
    table.add_row("Window size", f"{uniqseq.window_size}")
    max_hist_str = "unlimited" if uniqseq.max_history is None else f"{uniqseq.max_history:,}"
    table.add_row("Max history", max_hist_str)
    max_uniq_seqs_str = (
        "unlimited" if uniqseq.max_unique_sequences is None else f"{uniqseq.max_unique_sequences:,}"
    )
    table.add_row("Max unique sequences", max_uniq_seqs_str)
    max_cand_str = "unlimited" if uniqseq.max_candidates is None else f"{uniqseq.max_candidates:,}"
    table.add_row("Max candidates", max_cand_str)
    if uniqseq.skip_chars > 0:
        table.add_row("Skip chars", f"{uniqseq.skip_chars}")
    # Note: delimiter info shown in function parameter, not tracked in uniqseq

    console.print()
    console.print(table)
    console.print()


def print_stats_json(uniqseq: UniqSeq) -> None:
    """Print deduplication statistics as JSON to stderr."""
    stats = uniqseq.get_stats()

    output = {
        "statistics": {
            "lines": {
                "total": stats["total"],
                "emitted": stats["emitted"],
                "skipped": stats["skipped"],
            },
            "redundancy_pct": round(stats["redundancy_pct"], 1),
            "sequences": {"unique_tracked": stats["unique_sequences"]},
        },
        "configuration": {
            "window_size": uniqseq.window_size,
            "max_history": uniqseq.max_history if uniqseq.max_history is not None else "unlimited",
            "max_unique_sequences": uniqseq.max_unique_sequences
            if uniqseq.max_unique_sequences is not None
            else "unlimited",
            "max_candidates": uniqseq.max_candidates
            if uniqseq.max_candidates is not None
            else "unlimited",
            "skip_chars": uniqseq.skip_chars,
        },
    }

    # Print to stderr (console already configured for stderr)
    print(json.dumps(output, indent=2), file=sys.stderr)


if __name__ == "__main__":
    app()
