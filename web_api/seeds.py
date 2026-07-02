"""Default starter library for a fresh install.

The actual content lives in the top-level ``starter_library/`` folder, split
into **one human-readable file per item** across three subfolders:

* ``starter_library/game_types/*.json``      — one game type per file
* ``starter_library/configurations/*.json``  — one configuration per file
* ``starter_library/templates/*.md``         — one template per file, as YAML
  frontmatter (the metadata) followed by the raw, un-escaped prompt body

Files are loaded in filename order (they carry a ``NN-`` numeric prefix so the
shipped order is preserved and obvious). This module exposes
``SEED_GAME_TYPES`` / ``SEED_TEMPLATES`` / ``SEED_CONFIGURATIONS``, which
``web_api.storage`` uses to seed the on-disk store on a fresh install (and to
top up any missing entries).

Edit the files in ``starter_library/`` to change what ships — or regenerate the
whole folder from the canonical presets with
``python tools/build_seed_library.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

_LIBRARY_DIR = Path(__file__).resolve().parent.parent / "starter_library"


# YAML implicitly parses ISO-8601 scalars into ``datetime`` objects, which would
# turn ``created_at`` fields into non-JSON-serializable values downstream. Use a
# loader with the timestamp resolver stripped so every scalar stays a string.
class _StrTimestampLoader(yaml.SafeLoader):
    pass


for _ch, _resolvers in list(_StrTimestampLoader.yaml_implicit_resolvers.items()):
    _StrTimestampLoader.yaml_implicit_resolvers[_ch] = [
        (tag, regexp) for tag, regexp in _resolvers if tag != "tag:yaml.org,2002:timestamp"
    ]


def _load_json_dir(subdir: str) -> list[dict[str, Any]]:
    """Load every ``*.json`` file in ``starter_library/<subdir>/`` (sorted)."""
    directory = _LIBRARY_DIR / subdir
    if not directory.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except (ValueError, OSError):
            # A malformed/unreadable starter file must never break startup —
            # skip it and keep loading the rest.
            continue
        if isinstance(data, dict):
            items.append(data)
    return items


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split a Markdown file into ``(frontmatter dict, body)``.

    Expects the canonical form::

        ---
        key: value
        ---
        <raw body...>

    Returns ``({}, text)`` if there is no well-formed frontmatter block.
    """
    if not text.startswith("---"):
        return {}, text
    lines = text.split("\n")
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            meta = yaml.load("\n".join(lines[1:i]), Loader=_StrTimestampLoader) or {}
            body = "\n".join(lines[i + 1 :])
            return (meta if isinstance(meta, dict) else {}), body
    return {}, text


def _load_templates() -> list[dict[str, Any]]:
    """Load every ``*.md`` template in ``starter_library/templates/`` (sorted)."""
    directory = _LIBRARY_DIR / "templates"
    if not directory.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.md")):
        try:
            meta, body = _split_frontmatter(path.read_text())
        except (ValueError, OSError):
            continue
        if not meta:
            continue
        record = dict(meta)
        record["body"] = body
        items.append(record)
    return items


SEED_GAME_TYPES: list[dict[str, Any]] = _load_json_dir("game_types")
SEED_TEMPLATES: list[dict[str, Any]] = _load_templates()
SEED_CONFIGURATIONS: list[dict[str, Any]] = _load_json_dir("configurations")
