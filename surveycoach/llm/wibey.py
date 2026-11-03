"""Runs the `wibey` CLI headlessly. Wibey is asked to write its JSON to a file; stdout is never parsed,
because Wibey renders Markdown there and strips underscores from keys and values (spike R2)."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from surveycoach.llm.base import ASSESSMENT_MODEL, LlmError, LlmUnavailable
from surveycoach.llm.recovery import failure_error

SETUP_HINT = "Wibey is not installed or not on PATH. Install it, run `wibey --auth`, then try again."


def _prompt(system: str, data: str, schema: type, out: Path, images: Sequence[Path]) -> str:
    images_block = "".join(f"IMAGE: {Path(p).absolute()}\n" for p in images)
    return (f"{system}\n\n"
            f"OUTPUT_FILE: {out}\n"
            "Write ONLY valid JSON matching the schema below to OUTPUT_FILE. Do not edit any other file.\n"
            f"SCHEMA: {json.dumps(schema.model_json_schema())}\n\n"
            f"{images_block}{data}\n")


class WibeyProvider:
    def __init__(self, binary: str | None = None, timeout: int = 180, attempts: int = 2):
        self.binary = binary or os.environ.get("SURVEYCOACH_WIBEY_BIN") or "wibey"
        self.timeout = timeout
        if attempts not in {1, 2}:
            raise ValueError('Wibey attempts must be 1 or 2')
        self.attempts = attempts

    def complete_json(self, system: str, data: str, schema: type, images: Sequence[Path] = ()):
        # A private temp directory is the working directory, so a coding agent cannot touch the repository.
        with tempfile.TemporaryDirectory(prefix="surveycoach-") as folder:
            work = Path(folder)
            out, prompt_file = work / "answer.json", work / "prompt.txt"
            base = _prompt(system, data, schema, out, images)
            problem = ""
            for attempt in range(self.attempts):
                retry = f"\n\nYour last output was invalid: {problem}\nWrite corrected JSON to OUTPUT_FILE." if problem else ""
                prompt_file.write_text(base + retry)
                out.unlink(missing_ok=True)
                note = self._run(prompt_file, work)
                try:
                    return schema.model_validate_json(out.read_text())
                except FileNotFoundError:
                    problem = f"no file was written. {note}".strip()
                except ValidationError as error:
                    problem = str(error)[:500]
            raise LlmError(f"Wibey gave no valid answer after {self.attempts} tries: {problem}")

    def _run(self, prompt_file: Path, work: Path) -> str:
        try:
            done = subprocess.run([self.binary, "-f", str(prompt_file), "-m", ASSESSMENT_MODEL], cwd=work,
                                  capture_output=True, text=True, timeout=self.timeout, check=False)
        except FileNotFoundError as error:
            raise LlmUnavailable(SETUP_HINT) from error
        except subprocess.TimeoutExpired as error:
            raise LlmError(f"Wibey timed out after {self.timeout} s") from error
        if done.returncode:
            raise failure_error(done.stderr, self.binary)
        return ""
