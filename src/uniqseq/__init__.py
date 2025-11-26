"""uniqseq - Deduplicate repeated sequences of lines in text streams and files."""

from .uniqseq import UniqSeq

# Version is managed by hatch-vcs and set during build
try:
    from ._version import __version__
except ImportError:
    # Fallback for development installs without build
    __version__ = "0.0.0.dev0+unknown"

__all__ = ["UniqSeq", "__version__"]
