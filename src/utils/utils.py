from pathlib import Path

def get_project_root(path: Path, levels_up) -> Path:
    for _ in range(levels_up):
        path = path.parent
    return path