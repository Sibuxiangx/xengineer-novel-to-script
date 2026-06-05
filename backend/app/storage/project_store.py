from pathlib import Path


class ProjectStore:
    """File-system helper for project artifacts."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def project_root(self, project_id: str) -> Path:
        return self.root / project_id

    def ensure_project_root(self, project_id: str) -> Path:
        path = self.project_root(project_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

