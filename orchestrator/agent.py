from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI

from context.loader import RepositoryContext, RepositoryLoader
from sandbox.executor import ExecutionResult, LocalSandbox


DEFAULT_MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"


@dataclass
class HermesRunResult:
    report_path: Path
    artifacts_dir: Path
    context_path: Path
    plan_path: Path


class HermesOrchestrator:
    def __init__(
        self,
        source_repo: str,
        workspace_dir: Path,
        model: str = "mimo-v2.5-pro",
        max_files: int = 200,
        dry_run: bool = False,
    ):
        self.source_repo = source_repo
        self.workspace_dir = workspace_dir
        self.model = model
        self.max_files = max_files
        self.dry_run = dry_run
        self.loader = RepositoryLoader(source_ref=source_repo, workspace_dir=workspace_dir, max_files=max_files)
        self.sandbox = LocalSandbox()
        self.artifacts_dir = workspace_dir / "artifacts"
        self.report_path = self.artifacts_dir / "hermes-report.md"
        self.context_path = self.artifacts_dir / "repository-context.json"
        self.plan_path = self.artifacts_dir / "modernization-plan.json"
        self.client = self._build_client()

    def run(self) -> Path:
        context = self.loader.load_context()
        self.loader.save_context_manifest(context, self.context_path)

        plan = self.create_modernization_plan(context)
        self.plan_path.parent.mkdir(parents=True, exist_ok=True)
        self.plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")

        if not self.dry_run:
            self._run_validation(context, plan)

        self.report_path.write_text(self._render_report(context, plan), encoding="utf-8")
        return self.report_path

    def create_modernization_plan(self, context: RepositoryContext) -> dict:
        if self.client is None:
            return self._fallback_plan(context)

        response = self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Hermes, an autonomous code modernization agent. "
                        "Analyze the repository and return a concise JSON plan that can be executed on a VPS. "
                        "Focus on architecture modernization, tests, risks, and execution order."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(context.to_dict(), indent=2),
                },
            ],
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    def _run_validation(self, context: RepositoryContext, plan: dict) -> None:
        repository_root = Path(context.repository_root)
        result = self.sandbox.run_validation(repository_root, context.primary_language)

        validation_report = {
            "primary_language": context.primary_language,
            "status": result.status,
            "exit_code": result.exit_code,
            "command": result.command,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "plan_focus": plan,
        }
        (self.artifacts_dir / "validation.json").write_text(json.dumps(validation_report, indent=2), encoding="utf-8")

        if result.exit_code != 0:
            self._write_failure_note(result)

    def _write_failure_note(self, result: ExecutionResult) -> None:
        note = "\n".join(
            [
                "# Validation Failed",
                "",
                f"Command: {result.command}",
                f"Exit code: {result.exit_code}",
                "",
                "## stderr",
                "",
                result.stderr or "<empty>",
                "",
                "## stdout",
                "",
                result.stdout or "<empty>",
            ]
        )
        (self.artifacts_dir / "validation-failure.md").write_text(note, encoding="utf-8")

    def _render_report(self, context: RepositoryContext, plan: dict) -> str:
        file_count = len(context.files)
        sample_files = "\n".join(f"- {snapshot.path}" for snapshot in context.files[:12]) or "- <no text files detected>"
        return "\n".join(
            [
                "# Hermes Modernization Report",
                "",
                f"Source: {context.source_ref}",
                f"Repository root: {context.repository_root}",
                f"Primary language: {context.primary_language}",
                f"Files ingested: {file_count}",
                "",
                "## Sample files",
                "",
                sample_files,
                "",
                "## Plan summary",
                "",
                json.dumps(plan, indent=2),
            ]
        )

    def _fallback_plan(self, context: RepositoryContext) -> dict:
        file_names = [snapshot.path for snapshot in context.files[:20]]
        return {
            "project_summary": "Offline fallback plan generated without MiMo credentials.",
            "recommended_architecture": "Hermes-driven modernization pipeline with planning, testing, and self-healing stages.",
            "execution_order": [
                "Ingest repository context",
                "Identify legacy architecture hotspots",
                "Modernize highest-value files first",
                "Run validation in sandbox",
                "Capture failures and iterate",
            ],
            "priority_files": file_names,
            "risks": [
                "Missing MiMo API credentials",
                "Repository may need cloning before execution",
                "Legacy tests may be incomplete",
            ],
            "evaluation_criteria": [
                "Modernization plan is structured and actionable",
                "Validation runs produce artifacts",
                "Failures are captured for self-healing",
            ],
        }

    def _build_client(self) -> OpenAI | None:
        api_key = os.environ.get("MIMO_API_KEY")
        if not api_key:
            return None

        return OpenAI(api_key=api_key, base_url=DEFAULT_MIMO_BASE_URL)