"""Gemini Enterprise Managed Agent Linux Sandbox Execution Wrapper."""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import time
from typing import Any
from pydantic import BaseModel, Field


class SandboxExecutionResult(BaseModel):
    """Execution telemetry captured from the ephemeral Linux sandbox."""

    passed: bool
    pass_rate: float
    executed_test_types: list[str] = Field(default_factory=list)
    stdout: str
    stderr: str
    duration_ms: float
    exit_code: int = 0


class ManagedAgentSandbox:
    """Ephemeral serverless execution environment for compiling code, linting SQL, and running unit tests."""

    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds

    async def execute_code_tests(
        self,
        code_files: dict[str, str],
        test_files: dict[str, str],
        test_types: list[str] | None = None,
    ) -> SandboxExecutionResult:
        """Provision ephemeral sandbox, write files, and execute test suites via pytest."""
        start_time = time.time()
        temp_dir = tempfile.mkdtemp(prefix="sdo_sandbox_")
        executed_types = test_types or ["unit", "sql_syntax_lint"]

        try:
            # 1. Write production code artifacts into sandbox
            for filename, content in code_files.items():
                filepath = os.path.join(temp_dir, filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)

            # 2. Write test suite files into sandbox
            for filename, content in test_files.items():
                filepath = os.path.join(temp_dir, filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)

            # 3. Execute pytest inside the isolated directory
            proc = await asyncio.create_subprocess_exec(
                "python3",
                "-m",
                "pytest",
                temp_dir,
                "-q",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=temp_dir,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=self.timeout_seconds
                )
                stdout = stdout_bytes.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")
                exit_code = proc.returncode or 0
                passed = exit_code == 0
                pass_rate = 100.0 if passed else 0.0
            except asyncio.TimeoutError:
                proc.kill()
                stdout = ""
                stderr = f"Sandbox execution timed out after {self.timeout_seconds}s"
                exit_code = 124
                passed = False
                pass_rate = 0.0

            duration_ms = (time.time() - start_time) * 1000.0

            return SandboxExecutionResult(
                passed=passed,
                pass_rate=pass_rate,
                executed_test_types=executed_types,
                stdout=stdout,
                stderr=stderr,
                duration_ms=duration_ms,
                exit_code=exit_code,
            )

        finally:
            # Immediately destroy ephemeral sandbox container/filesystem
            shutil.rmtree(temp_dir, ignore_errors=True)
