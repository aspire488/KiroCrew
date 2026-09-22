from kiro_crew import pdf_extract
import json

class Proc:
    returncode = 0
    def __init__(self):
        self.inputs = None
    def communicate(self, input=None, timeout=None):
        self.inputs = input
        return json.dumps({
            "segments": [{"label": "page 1", "text": "hello PDF"}],
            "page_count": 1,
            "truncated": False,
        }).encode(), b""

def test_oversize_input_is_refused_before_spawn(monkeypatch):
    called = False
    def spawn(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("oversize input must not spawn")
    monkeypatch.setattr(pdf_extract, "popen_limited", spawn)
    result = pdf_extract.extract_pdf_segments(b"x" * (pdf_extract.PDF_MAX_BYTES + 1))
    assert result == ((), False, 0)
    assert called is False

def test_child_result_is_parsed_and_bounded(monkeypatch):
    proc = Proc()
    monkeypatch.setattr(pdf_extract, "popen_limited", lambda *a, **kw: proc)
    segments, complete, pages = pdf_extract.extract_pdf_segments(b"%PDF", max_chars=5)
    assert segments == (("page 1", "hello"),)
    assert complete is False
    assert pages == 1
    assert proc.inputs == b"%PDF"
