from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExecutionResult:
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    status: str


class LocalSandbox:
    IGNORED_DIRECTORIES = {
        ".git",
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

    def __init__(self, docker_image: str = "python:3.11"):
        self.docker_image = docker_image

    def run_pytest(self, repository_root: Path, test_target: str = "tests") -> ExecutionResult:
        return self.run_validation(repository_root, "python", test_target=test_target)

    def run_validation(
        self,
        repository_root: Path,
        primary_language: str,
        test_target: str = "tests",
    ) -> ExecutionResult:
        normalized_language = (primary_language or "").lower()
        if normalized_language in {"typescript", "javascript"}:
            return self._run_node_validation(repository_root)

        if not self._has_tests(repository_root, test_target):
            return ExecutionResult(
                command=["python", "-m", "pytest", test_target],
                exit_code=0,
                stdout="No tests found; validation skipped.",
                stderr="",
                status="skipped",
            )

        if self._docker_available():
            command = self._build_docker_command(repository_root, test_target)
        else:
            command = ["python", "-m", "pytest", test_target]

        completed = subprocess.run(
            command,
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=False,
        )
        status = "passed" if completed.returncode == 0 else "failed"
        return ExecutionResult(
            command=command,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            status=status,
        )

    def _run_node_validation(self, repository_root: Path) -> ExecutionResult:
        package_json = repository_root / "package.json"
        if not package_json.exists():
            return ExecutionResult(
                command=["npm", "test"],
                exit_code=0,
                stdout="No package.json found; Node validation skipped.",
                stderr="",
                status="skipped",
            )

        command = self._build_node_command(repository_root)
        completed = subprocess.run(
            command,
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=False,
        )
        status = "passed" if completed.returncode == 0 else "failed"
        return ExecutionResult(
            command=command,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            status=status,
        )

    def _docker_available(self) -> bool:
        return shutil.which("docker") is not None

    def _build_docker_command(self, repository_root: Path, test_target: str) -> list[str]:
        script_parts = ["python -m pip install --quiet pytest"]
        requirements_file = repository_root / "requirements.txt"
        if requirements_file.exists():
            script_parts.append("python -m pip install --quiet -r requirements.txt")
        script_parts.append(f"python -m pytest {shlex.quote(test_target)}")
        script = " && ".join(script_parts)

        return [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{repository_root.resolve()}:/workspace",
            "-w",
            "/workspace",
            self.docker_image,
            "sh",
            "-lc",
            script,
        ]

    def _build_node_command(self, repository_root: Path) -> list[str]:
        package_json = repository_root / "package.json"
        scripts = self._read_package_scripts(package_json)
        install_cmd = "npm ci --no-fund --no-audit" if (repository_root / "package-lock.json").exists() else "npm install --no-fund --no-audit"

        script_parts = [install_cmd]
        if scripts.get("test"):
            script_parts.append("npm test --if-present")
        if scripts.get("build"):
            script_parts.append("npm run build --if-present")

        if not scripts.get("test") and not scripts.get("build"):
            if self._has_node_test_files(repository_root):
                script_parts.append("node --test")
            else:
                script_parts.append("echo 'No JS/TS test command found; validation skipped.'")

        script = " && ".join(script_parts)

        if self._docker_available():
            return [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{repository_root.resolve()}:/workspace",
                "-w",
                "/workspace",
                "node:20",
                "sh",
                "-lc",
                script,
            ]

        return ["sh", "-lc", script]

    def _has_tests(self, repository_root: Path, test_target: str) -> bool:
        target_path = repository_root / test_target
        if target_path.exists():
            return self._contains_python_tests(target_path)

        return any(self._iter_python_test_files(repository_root))

    def _iter_python_test_files(self, base_path: Path):
        for root, dirs, files in os.walk(base_path):
            dirs[:] = [
                directory
                for directory in dirs
                if directory not in self.IGNORED_DIRECTORIES and not directory.startswith(".")
            ]
            for file_name in files:
                if file_name.startswith("test_") or file_name.endswith("_test.py"):
                    yield Path(root) / file_name

    def _contains_python_tests(self, path: Path) -> bool:
        if path.is_file():
            return path.name.startswith("test_") or path.name.endswith("_test.py")

        return any(self._iter_python_test_files(path))

    def _read_package_scripts(self, package_json: Path) -> dict:
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except Exception:
            return {}

        scripts = data.get("scripts")
        return scripts if isinstance(scripts, dict) else {}

    def _has_node_test_files(self, repository_root: Path) -> bool:
        for root, dirs, files in os.walk(repository_root):
            dirs[:] = [
                directory
                for directory in dirs
                if directory not in self.IGNORED_DIRECTORIES and not directory.startswith(".")
            ]
            for file_name in files:
                lowered = file_name.lower()
                if lowered.startswith("test_") or lowered.endswith(".test.js") or lowered.endswith(".spec.js"):
                    return True
                if lowered.startswith("test_") or lowered.endswith(".test.ts") or lowered.endswith(".spec.ts"):
                    return True
        return False