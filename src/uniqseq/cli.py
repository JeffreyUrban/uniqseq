"""Command-line interface for uniqseq."""

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
):
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
    # Disable progress if outputting to a pipe
    show_progress = progress and sys.stdout.isatty()

    # Create deduplicator
    dedup = StreamingDeduplicator(
        window_size=window_size,
        max_history=max_history,
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

                def update_progress(line_num, lines_skipped, seq_count):
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
                    with open(input_file, "r") as f:
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

                with open(input_file, "r") as f:
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
            print_stats(dedup)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        # Flush what we have
        dedup.flush(sys.stdout)
        if not quiet:
            console.print("[dim]Partial statistics:[/dim]")
            print_stats(dedup)
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


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
    table.add_row("Max history", f"{dedup.max_history:,}")

    console.print()
    console.print(table)
    console.print()


if __name__ == "__main__":
    app()
