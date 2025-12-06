"""Pattern-based filtering for determining what gets deduplicated."""

import re
from dataclasses import dataclass
from typing import Optional, Union


@dataclass
class FilterPattern:
    """A filter pattern with its action.

    Patterns are evaluated sequentially. First match wins.
    """

    __slots__ = ["pattern", "action", "regex"]
    pattern: str  # Original pattern string
    action: str  # "track" or "bypass"
    regex: re.Pattern[str]  # Compiled regex pattern


def evaluate_filter(
    line: Union[str, bytes], filter_patterns: list[FilterPattern]
) -> tuple[Optional[str], Optional[str]]:
    """Evaluate filter patterns against a line.

    Args:
        line: The line to evaluate (str or bytes)
        filter_patterns: List of filter patterns to evaluate

    Returns:
        Tuple of (action, pattern_string):
        - action: "bypass", "track", "no_match_allowlist", or None
        - pattern_string: The matched pattern string, or None if no match

    Note:
        Patterns are evaluated in order. First match wins.
        When track patterns exist, they act as allowlist (only tracked lines deduplicated).
        When only bypass patterns exist, they act as denylist (all but bypassed deduplicated).
        Currently only supports text mode (str lines).
    """
    if not filter_patterns:
        return (None, None)

    # Convert bytes to str for pattern matching (filters require text mode)
    line_str = line.decode("utf-8") if isinstance(line, bytes) else line

    # Evaluate patterns in order
    for filter_pattern in filter_patterns:
        if filter_pattern.regex.search(line_str):
            return (filter_pattern.action, filter_pattern.pattern)

    # No match - check if we have track patterns (allowlist mode)
    has_track_patterns = any(p.action == "track" for p in filter_patterns)
    if has_track_patterns:
        # Allowlist mode: only tracked lines are deduplicated
        # No match means pass through
        return ("no_match_allowlist", None)

    # No track patterns (denylist mode): deduplicate by default
    return (None, None)


def get_bypass_description(filter_action: Optional[str], matched_pattern: Optional[str]) -> str:
    """Get description for why a line was bypassed.

    Args:
        filter_action: The filter action ("bypass" or "no_match_allowlist")
        matched_pattern: The matched pattern string, if any

    Returns:
        Human-readable description of bypass reason
    """
    if filter_action == "bypass" and matched_pattern:
        return f"matched bypass pattern '{matched_pattern}'"
    elif filter_action == "no_match_allowlist":
        return "no track pattern matched (allowlist mode)"
    else:
        return "bypassed"
