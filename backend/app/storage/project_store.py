import json
from pathlib import Path
from shutil import rmtree
from typing import Any


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

    def source_root(self, project_id: str) -> Path:
        path = self.ensure_project_root(project_id) / "source"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def source_text_path(self, project_id: str, file_name: str) -> Path:
        safe_name = Path(file_name).name or "novel.txt"
        if not safe_name.endswith(".txt"):
            safe_name = f"{safe_name}.txt"
        return self.source_root(project_id) / safe_name

    def write_source_text(self, project_id: str, file_name: str, content: str) -> Path:
        path = self.source_text_path(project_id, file_name)
        path.write_text(content, encoding="utf-8")
        return path

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

    def book_index_path(self, project_id: str) -> Path:
        return self.ensure_project_root(project_id) / "book_index.json"

    def script_path(self, project_id: str) -> Path:
        return self.ensure_project_root(project_id) / "script.yaml"

    def versions_root(self, project_id: str) -> Path:
        path = self.ensure_project_root(project_id) / "versions"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def script_version_path(self, project_id: str, version_id: str) -> Path:
        return self.versions_root(project_id) / f"{version_id}.yaml"

    def export_root(self, project_id: str) -> Path:
        path = self.ensure_project_root(project_id) / "exports"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_json(self, path: str | Path, data: dict[str, Any]) -> None:
        Path(path).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def read_json(self, path: str | Path) -> dict[str, Any]:
        return json.loads(Path(path).read_text(encoding="utf-8"))
