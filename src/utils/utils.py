from pathlib import Path
import re

def get_project_root(path: Path, levels_up) -> Path:
    for _ in range(levels_up):
        path = path.parent
    return path

# utils.py or text_utils.py
def slug(text: str) -> str:
    """Convert text to URL-safe slug format."""
    return re.sub(r'[^a-z0-9]+', '-', str(text).lower()).strip('-')

def deduplicate_preserving_order(items: list) -> list:
    """Remove duplicates while preserving order."""
    seen, ordered = set(), []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered

def remove_duplicate_prefix(full_name: str, short_name: str) -> str:
    """Remove duplicated prefix if full name starts with it.
    
    Example: 'prisoner-dilemma-prisoner-dilemma-v2' -> 'v2'
    """
    dup_prefix = f"{short_name}-{short_name}-"
    if full_name.startswith(dup_prefix):
        return full_name[len(dup_prefix):]
    return full_name