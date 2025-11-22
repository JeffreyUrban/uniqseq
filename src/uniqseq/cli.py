"""Command-line interface for uniqseq."""

import json
import sys
from pathlib import Path
from typing import Optional

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

from .deduplicator import DEFAULT_MAX_HISTORY, MIN_SEQUENCE_LENGTH, StreamingDeduplicator

app = typer.Typer(
    name="uniqseq",
    help="Deduplicate repeated sequences of lines in text streams and files",
    add_completion=False,
)

console = Console(stderr=True)  # All output to stderr to preserve stdout for data


def validate_arguments(
    window_size: int, max_history: Optional[int], unlimited_history: bool, stats_format: str
) -> None:
    """Validate argument combinations and constraints.

    Args:
        window_size: Minimum sequence length to detect
        max_history: Maximum depth of history (or None if unlimited)
        unlimited_history: Whether unlimited history mode is enabled
        stats_format: Statistics output format

    Raises:
        typer.BadParameter: If validation fails with clear message
    """
    # Semantic validation: unlimited and max_history are mutually exclusive
    if unlimited_history and max_history != DEFAULT_MAX_HISTORY:
        raise typer.BadParameter(
            "--unlimited-history and --max-history are mutually exclusive. "
            "Use --unlimited-history for unbounded history, or --max-history with a specific limit."
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


@app.command()
def main(
    input_file: Optional[Path] = typer.Argument(
        None,
        help="Input file to deduplicate (reads from stdin if not specified)",
        exists=True,
        dir_okay=False,
    ),
    window_size: int = typer.Option(
        MIN_SEQUENCE_LENGTH,
        "--window-size",
        "-w",
        help="Minimum sequence length to detect (lines buffered and compared before output)",
        min=2,
    ),
    max_history: int = typer.Option(
        DEFAULT_MAX_HISTORY,
        "--max-history",
        "-m",
        help="Maximum depth of history (lines matched against)",
        min=100,
    ),
    unlimited_history: bool = typer.Option(
        False,
        "--unlimited-history",
        help="Unlimited history depth (suitable for file processing, not streaming)",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress statistics output to stderr",
    ),
    progress: bool = typer.Option(
        False,
        "--progress",
        "-p",
        help="Show progress indicator (auto-disabled for pipes)",
    ),
    stats_format: str = typer.Option(
        "table",
        "--stats-format",
        help="Statistics output format: 'table' (default, Rich table) or 'json' (machine-readable)",
    ),
) -> None:
    """
    Remove duplicate line sequences from streaming input.

    This tool detects and removes repeated sequences of lines (minimum 10 lines by default)
    while preserving all unique content. Designed for reducing redundancy in logs where
    content is frequently re-displayed.

    Examples:

        \b
        # Deduplicate a file
        uniqseq session.log > deduplicated.log

        \b
        # Use in a pipeline
        cat session.log | uniqseq > deduplicated.log

        \b
        # Custom window size (detect 15+ line sequences)
        uniqseq --window-size 15 session.log > output.log

        \b
        # Larger history for very long sessions
        uniqseq --max-history 50000 session.log > output.log

        \b
        # Quiet mode (no statistics)
        uniqseq --quiet session.log > output.log

        \b
        # Show live progress (auto-disabled for pipes)
        uniqseq --progress session.log > output.log
    """
    # Validate arguments
    validate_arguments(window_size, max_history, unlimited_history, stats_format)

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

    # Create deduplicator
    dedup = StreamingDeduplicator(
        window_size=window_size,
        max_history=effective_max_history,
    )

    try:
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

                # Read input with progress
                if input_file:
                    with open(input_file) as f:
                        for line in f:
                            dedup.process_line(
                                line.rstrip("\n"), sys.stdout, progress_callback=update_progress
                            )
                else:
                    for line in sys.stdin:
                        dedup.process_line(
                            line.rstrip("\n"), sys.stdout, progress_callback=update_progress
                        )

                # Flush remaining buffer
                dedup.flush(sys.stdout)
        else:
            # Read input without progress
            if input_file:
                if not quiet:
                    console.print(f"[cyan]Processing:[/cyan] {input_file}", style="dim")

                with open(input_file) as f:
                    for line in f:
                        dedup.process_line(line.rstrip("\n"), sys.stdout)
            else:
                # Reading from stdin - check if it's a pipe
                if not sys.stdin.isatty():
                    if not quiet:
                        console.print("[cyan]Reading from stdin...[/cyan]", style="dim")

                for line in sys.stdin:
                    dedup.process_line(line.rstrip("\n"), sys.stdout)

            # Flush remaining buffer
            dedup.flush(sys.stdout)

        # Print stats to stderr unless quiet
        if not quiet:
            if stats_format == "json":
                print_stats_json(dedup)
            else:
                print_stats(dedup)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        # Flush what we have
        dedup.flush(sys.stdout)
        if not quiet:
            if stats_format == "json":
                print_stats_json(dedup)
            else:
                console.print("[dim]Partial statistics:[/dim]")
                print_stats(dedup)
        raise typer.Exit(1) from None
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


def print_stats(dedup: StreamingDeduplicator) -> None:
    """Print deduplication statistics using rich."""
    stats = dedup.get_stats()

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
    table.add_row("Window size", f"{dedup.window_size}")
    max_hist_str = "unlimited" if dedup.max_history is None else f"{dedup.max_history:,}"
    table.add_row("Max history", max_hist_str)

    console.print()
    console.print(table)
    console.print()


def print_stats_json(dedup: StreamingDeduplicator) -> None:
    """Print deduplication statistics as JSON to stderr."""
    stats = dedup.get_stats()

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
            "window_size": dedup.window_size,
            "max_history": dedup.max_history if dedup.max_history is not None else "unlimited",
        },
    }

    # Print to stderr (console already configured for stderr)
    print(json.dumps(output, indent=2), file=sys.stderr)


if __name__ == "__main__":
    app()
