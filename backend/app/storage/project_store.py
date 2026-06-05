from pathlib import Path
from shutil import rmtree


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

    def chapters_root(self, project_id: str) -> Path:
        return self.ensure_project_root(project_id) / "chapters"

    def ensure_chapters_root(self, project_id: str) -> Path:
        path = self.chapters_root(project_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def clear_chapters(self, project_id: str) -> None:
        path = self.chapters_root(project_id)
        if path.exists():
            rmtree(path)

    def chapter_path(self, project_id: str, order_index: int, chapter_id: str) -> Path:
        filename = f"{order_index + 1:03d}-{chapter_id}.txt"
        return self.ensure_chapters_root(project_id) / filename

    def write_chapter(
        self,
        project_id: str,
        order_index: int,
        chapter_id: str,
        content: str,
    ) -> Path:
        path = self.chapter_path(project_id, order_index, chapter_id)
        path.write_text(content, encoding="utf-8")
        return path

    def read_text(self, path: str | Path) -> str:
        return Path(path).read_text(encoding="utf-8")

    def write_text(self, path: str | Path, content: str) -> None:
        Path(path).write_text(content, encoding="utf-8")
