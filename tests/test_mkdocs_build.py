"""Test that MkDocs documentation builds successfully."""

import subprocess


def test_mkdocs_build():
    """Test that mkdocs build completes without errors."""
    result = subprocess.run(
        ["mkdocs", "build", "--strict"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, (
        f"mkdocs build failed with exit code {result.returncode}\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )
