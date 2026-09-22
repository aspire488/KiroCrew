"""Subprocess entry point for bounded PDF text extraction."""
from __future__ import annotations
import io
import json
import sys
import pdfplumber

MAX_CHARS = 400_000
MAX_PAGES = 1000
MAX_BYTES = 25 * 1024 * 1024

def _write(segments: list[dict[str, str]], page_count: int, truncated: bool) -> int:
    sys.stdout.write(json.dumps({"segments": segments, "page_count": page_count, "truncated": truncated}, ensure_ascii=False, separators=(",", ":")))
    sys.stdout.flush()
    return 0

def main() -> int:
    data = sys.stdin.buffer.read()
    if len(data) > MAX_BYTES:
        return _write([], 0, True)
    segments: list[dict[str, str]] = []
    used = 0
    truncated = False
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            page_count = len(pdf.pages)
            for number, page in enumerate(pdf.pages[:MAX_PAGES], 1):
                try:
                    text = page.extract_text() or ""
                finally:
                    close_page = getattr(page, "close", None) or getattr(page, "flush_cache", None)
                    if close_page is not None:
                        close_page()
                remaining = MAX_CHARS - used
                if remaining <= 0:
                    truncated = True
                    break
                if len(text) > remaining:
                    text = text[:remaining]
                    truncated = True
                segments.append({"label": f"page {number}", "text": text})
                used += len(text)
                if truncated:
                    break
            else:
                truncated = page_count > MAX_PAGES
        return _write(segments, page_count, truncated)
    except Exception:
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
