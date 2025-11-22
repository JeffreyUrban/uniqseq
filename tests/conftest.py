"""Pytest configuration and shared fixtures."""

import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Temporary directory for test files."""
    dirpath = Path(tempfile.mkdtemp())
    yield dirpath
    shutil.rmtree(dirpath)


@pytest.fixture
def sample_log_file(temp_dir):
    """Sample log file with repeated patterns."""
    log_file = temp_dir / "sample.log"

    lines = [
        "INFO: Starting application",
        "ERROR: Connection failed",
        "  at line 10",
        "  retry in 5s",
        "INFO: Retrying",
        "ERROR: Connection failed",  # Duplicate
        "  at line 10",
        "  retry in 5s",
        "INFO: Success",
    ]

    log_file.write_text("\n".join(lines))
    return log_file


@pytest.fixture(params=[2, 5, 10, 26])
def alphabet_size(request):
    """Parametrized alphabet sizes for random testing."""
    return request.param


@pytest.fixture(params=[100, 1000, 10000])
def sequence_length(request):
    """Parametrized sequence lengths for random testing."""
    return request.param
