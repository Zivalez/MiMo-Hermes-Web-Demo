from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections import Counter
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


DEFAULT_IGNORES = {
    ".git",
    ".env",
    ".venv",
    "venv",
    "workspace",
    "artifacts",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    ".ruff_cache",
}


class RepositoryLanguage(str, Enum):
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    KOTLIN = "kotlin"
    CPP = "c++"
    C = "c"
    UNKNOWN = "unknown"


@dataclass
class FileSnapshot:
    path: str
    size: int
    content: str


@dataclass
class RepositoryContext:
    source_ref: str
    repository_root: str
    primary_language: str
    files: list[FileSnapshot]

    def to_dict(self) -> dict:
        return {
            "source_ref": self.source_ref,
            "repository_root": self.repository_root,
            "primary_language": self.primary_language,
            "files": [asdict(snapshot) for snapshot in self.files],
        }


class RepositoryLoader:
    def __init__(
        self,
        source_ref: str,
        workspace_dir: Path,
        max_files: int = 200,
        ignore_dirs: Iterable[str] | None = None,
        max_file_size: int = 250_000,
    ):
        self.source_ref = source_ref
        self.workspace_dir = workspace_dir
        self.max_files = max_files
        self.max_file_size = max_file_size
        self.ignore_dirs = set(ignore_dirs or DEFAULT_IGNORES)
        self.repo_dir = self.workspace_dir / "source"

    def prepare(self) -> Path:
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        if self.repo_dir.exists() and any(self.repo_dir.iterdir()):
            return self.repo_dir

        if self._looks_like_url(self.source_ref):
            self._clone_repository()
            return self.repo_dir

        source_path = Path(self.source_ref).expanduser().resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Source repo not found: {self.source_ref}")
        return source_path

    def load_context(self) -> RepositoryContext:
        repository_root = self.prepare()
        primary_language = self._detect_primary_language(repository_root)
        files: list[FileSnapshot] = []

        for file_path in self._iter_files(repository_root):
            if len(files) >= self.max_files:
                break

            try:
                if file_path.stat().st_size > self.max_file_size:
                    continue
            except OSError:
                continue

            content = self._read_text(file_path)
            if content is None:
                continue

            files.append(
                FileSnapshot(
                    path=str(file_path.relative_to(repository_root)),
                    size=file_path.stat().st_size,
                    content=content,
                )
            )

        return RepositoryContext(
            source_ref=self.source_ref,
            repository_root=str(repository_root),
            primary_language=primary_language.value,
            files=files,
        )

    def save_context_manifest(self, context: RepositoryContext, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(context.to_dict(), indent=2), encoding="utf-8")

    def _iter_files(self, repository_root: Path) -> Iterable[Path]:
        for root, dirs, files in os.walk(repository_root):
            dirs[:] = [directory for directory in dirs if directory not in self.ignore_dirs]
            for file_name in files:
                file_path = Path(root) / file_name
                if file_path.name in self.ignore_dirs:
                    continue
                yield file_path

    def _read_text(self, file_path: Path) -> str | None:
        try:
            raw = file_path.read_bytes()
        except OSError:
            return None

        if b"\x00" in raw:
            return None

        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="ignore")

    def _clone_repository(self) -> None:
        if self.repo_dir.exists():
            shutil.rmtree(self.repo_dir)

        command = ["git", "clone", "--depth", "1", self.source_ref, str(self.repo_dir)]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to clone repository: {result.stderr.strip()}")

    @staticmethod
    def _looks_like_url(source_ref: str) -> bool:
        lowered = source_ref.lower()
        return lowered.startswith("http://") or lowered.startswith("https://") or lowered.endswith(".git")

    def _detect_primary_language(self, repository_root: Path) -> RepositoryLanguage:
        counts: Counter[str] = Counter()
        has_package_json = False
        has_tsconfig = False
        has_gradle_kts = False

        for file_path in self._iter_files(repository_root):
            name = file_path.name.lower()
            suffix = file_path.suffix.lower()

            if name == "package.json":
                has_package_json = True
            elif name == "tsconfig.json":
                has_tsconfig = True
            elif name in {"build.gradle.kts", "settings.gradle.kts"} or suffix == ".kt":
                has_gradle_kts = True

            if suffix in {".py", ".pyw"}:
                counts[RepositoryLanguage.PYTHON.value] += 1
            elif suffix in {".ts", ".tsx"}:
                counts[RepositoryLanguage.TYPESCRIPT.value] += 1
            elif suffix in {".js", ".jsx", ".mjs", ".cjs"}:
                counts[RepositoryLanguage.JAVASCRIPT.value] += 1
            elif suffix == ".kt":
                counts[RepositoryLanguage.KOTLIN.value] += 1
            elif suffix in {".cpp", ".hpp", ".cc", ".cxx"}:
                counts[RepositoryLanguage.CPP.value] += 1
            elif suffix == ".c":
                counts[RepositoryLanguage.C.value] += 1
            elif suffix == ".h":
                # .h is ambiguous; count it toward both C and C++
                counts[RepositoryLanguage.CPP.value] += 1
                counts[RepositoryLanguage.C.value] += 1

        # Config-based hints when no source files were counted
        total = sum(counts.values())
        if total == 0:
            if has_package_json and has_tsconfig:
                return RepositoryLanguage.TYPESCRIPT
            if has_package_json:
                return RepositoryLanguage.JAVASCRIPT
            if has_gradle_kts:
                return RepositoryLanguage.KOTLIN
            return RepositoryLanguage.UNKNOWN

        # Return the language with the highest file count
        top_lang = max(counts, key=counts.get, default=RepositoryLanguage.UNKNOWN.value)
        return RepositoryLanguage(top_lang)