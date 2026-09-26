def is_number(value) -> bool:
    """int or float, but not bool (JSON true/false must not count as 1/0)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)
