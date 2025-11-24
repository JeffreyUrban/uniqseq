"""Sybil configuration for testing code examples in documentation."""

from sybil import Sybil
from sybil.parsers.markdown import PythonCodeBlockParser, SkipParser

pytest_collect_file = Sybil(
    parsers=[
        PythonCodeBlockParser(),
        SkipParser(),
    ],
    patterns=["*.md"],
    fixtures=["tmp_path"],
).pytest()
