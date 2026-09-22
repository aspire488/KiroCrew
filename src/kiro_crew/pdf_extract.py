"""Memory-bounded PDF extraction shared by file-grep and knowledge ingestion."""
from __future__ import annotations
import json
import subprocess
import sys
import time
from typing import Any
from kiro_crew.sandbox import RLIMIT_PROFILE_EXTRACTOR, popen_limited

PDF_MAX_BYTES = 25 * 1024 * 1024
PDF_MAX_CHARS = 400_000
PDF_MAX_PAGES = 1000
Segments = tuple[tuple[str, str], ...]

def extract_pdf_segments(data: bytes, *, max_chars: int = PDF_MAX_CHARS, deadline: float | None = None) -> tuple[Segments, bool, int]:
    """Return (segments, complete, page_count) for already-authorized bytes."""
    if len(data) > PDF_MAX_BYTES or max_chars <= 0:
        return (), False, 0
    remaining = None if deadline is None else max(0.01, deadline - time.monotonic())
    try:
        proc = popen_limited(
            [sys.executable, "-m", "kiro_crew.pdf_extract_child"],
            profile=RLIMIT_PROFILE_EXTRACTOR,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except OSError:
        return (), False, 0
    try:
        stdout, _ = proc.communicate(input=data, timeout=remaining)
    except subprocess.TimeoutExpired:
        proc.kill(); proc.communicate()
        return (), False, 0
    except (BrokenPipeError, OSError):
        try:
            proc.kill(); proc.communicate()
        except OSError:
            pass
        return (), False, 0
    if proc.returncode != 0:
        return (), False, 0
    try:
        payload: Any = json.loads(stdout.decode("utf-8"))
        page_count = int(payload["page_count"])
        truncated = bool(payload["truncated"])
        segments: list[tuple[str, str]] = []
        used = 0
        for item in payload["segments"]:
            label = str(item["label"])
            text = str(item["text"])
            if used >= max_chars:
                truncated = True
                break
            remaining_chars = max_chars - used
            if len(text) > remaining_chars:
                text = text[:remaining_chars]
                truncated = True
            used += len(text)
            segments.append((label, text))
        return tuple(segments), not truncated, page_count
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return (), False, 0
