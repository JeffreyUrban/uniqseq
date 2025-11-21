"""uniqseq - Deduplicate repeated sequences of lines in text streams and files."""

__version__ = "0.1.0"

from .deduplicator import StreamingDeduplicator

__all__ = ["StreamingDeduplicator", "__version__"]
