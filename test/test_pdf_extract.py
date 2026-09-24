from kiro_crew import pdf_extract
import json
import io
import subprocess

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


def test_extractor_child_uses_isolated_python_path(monkeypatch):
    class Proc:
        returncode = 0
        def communicate(self, input=None, timeout=None):
            return json.dumps({
                "segments": [],
                "page_count": 0,
                "truncated": False,
            }).encode(), b""

    captured = {}

    def spawn(argv, **kwargs):
        captured["argv"] = list(argv)
        return Proc()

    monkeypatch.setattr(pdf_extract, "popen_limited", spawn)
    pdf_extract.extract_pdf_segments(b"%PDF")

    assert captured["argv"][0] == pdf_extract.sys.executable
    assert captured["argv"][1:4] == ["-P", "-m", "kiro_crew.pdf_extract_child"]


def _make_pdf(text: str = "child PDF regression") -> bytes:
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
    ]
    stream = ("BT /F1 12 Tf 72 700 Td (%s) Tj ET" % text).encode()
    objs.append(b"<< /Length %d >>\\nstream\\n%s\\nendstream" % (len(stream), stream))
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = io.BytesIO()
    out.write(b"%PDF-1.4\\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\\n%s\\nendobj\\n" % (i, body))
    xref = out.tell()
    out.write(b"xref\\n0 %d\\n0000000000 65535 f \\n" % (len(objs) + 1))
    for off in offsets:
        out.write(b"%010d 00000 n \\n" % off)
    out.write(b"trailer\\n<< /Size %d /Root 1 0 R >>\\nstartxref\\n%d\\n%%%%EOF" % (len(objs) + 1, xref))
    return out.getvalue()


def test_extractor_child_protocol_end_to_end():
    result = subprocess.run(
        [pdf_extract.sys.executable, "-P", "-m", "kiro_crew.pdf_extract_child"],
        input=_make_pdf(),
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    payload = json.loads(result.stdout)
    assert payload["page_count"] == 1
    assert payload["segments"][0]["text"] == "child PDF regression"
    assert payload["truncated"] is False
