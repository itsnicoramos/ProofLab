"""Read a photo, PDF or document into lines of text (SPEC §14), so students can scan their work.

This only *transcribes*: the student reviews and edits the text before anything is checked, and
every verdict still comes from the deterministic checkers. Everything runs on this computer:

- photos and scans (handwriting or print): Apple Vision's on-device text recognizer, the engine
  behind Live Text (macOS only);
- PDFs: the text layer when there is one (Quartz/PDFKit), otherwise each page is rendered and
  read with Vision;
- Word, RTF, ODT, HTML and similar documents: macOS's built-in ``textutil``;
- plain text: decoded directly (works everywhere).

On other systems (for example the Docker image) only plain text is available, and the API says
so, so the website can explain instead of failing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Literal

MAX_BYTES = 15 * 1024 * 1024
MAX_PDF_PAGES = 10
PDF_RENDER_SCALE = 2.0  # 144 dpi: enough for Vision, small enough to stay fast
MIN_TEXT_LAYER_CHARS = 20

DocKind = Literal["image", "pdf", "document", "text"]


class ReaderError(Exception):
    """The file can't be read. ``status`` is the HTTP status the API should use."""

    def __init__(self, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


@dataclass
class Line:
    text: str
    confidence: float | None = None
    page: int = 1


@dataclass
class ReadResult:
    kind: DocKind
    engine: str
    pages: int = 1
    lines: list[Line] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)


# --------------------------------------------------------------------------- capabilities


def _vision_available() -> bool:
    if sys.platform != "darwin":
        return False
    try:
        import Quartz  # noqa: F401
        import Vision  # noqa: F401
    except ImportError:
        return False
    return True


def capabilities() -> dict[str, bool]:
    vision = _vision_available()
    return {
        "images": vision,
        "pdf": vision,
        "documents": sys.platform == "darwin" and shutil.which("textutil") is not None,
        "text": True,
    }


# --------------------------------------------------------------------------- detection

_DOC_SUFFIXES = {".docx", ".doc", ".rtf", ".rtfd", ".odt", ".html", ".htm", ".webarchive"}
_TEXT_SUFFIXES = {".txt", ".md", ".tex", ".csv"}


def detect(data: bytes, filename: str | None = None, content_type: str | None = None) -> DocKind:
    head = data[:16]
    suffix = os.path.splitext(filename or "")[1].lower()
    if head.startswith(b"%PDF"):
        return "pdf"
    if (
        head.startswith(b"\x89PNG")
        or head.startswith(b"\xff\xd8\xff")
        or head[:4] in (b"GIF8", b"II*\x00", b"MM\x00*")
        or (head[:4] == b"RIFF" and data[8:12] == b"WEBP")
        or (data[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"mif1", b"heif", b"avif"))
    ):
        return "image"
    if suffix in _DOC_SUFFIXES or head.startswith(b"{\\rtf") or head.startswith(b"PK\x03\x04"):
        return "document"
    if suffix in _TEXT_SUFFIXES or (content_type or "").startswith("text/"):
        return "text"
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReaderError(
            "ProofLab can't read this kind of file. Try a photo, a PDF, a Word document or a "
            "text file.",
            415,
        ) from exc
    return "text"


# --------------------------------------------------------------------------- Apple Vision


def _recognize(handler: object) -> list[Line]:
    import Vision

    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    # Language correction "fixes" math into English words (x2 → x2 is fine, but n=2k+1 isn't
    # a word), so it stays off.
    request.setUsesLanguageCorrection_(False)
    request.setRecognitionLanguages_(["en-US"])
    ok, error = handler.performRequests_error_([request], None)  # type: ignore[attr-defined]
    if not ok:
        raise ReaderError(f"The text recognizer failed: {error}", 500)
    found: list[tuple[float, float, Line]] = []
    for obs in request.results() or []:
        candidates = obs.topCandidates_(1)
        if not candidates:
            continue
        best = candidates[0]
        box = obs.boundingBox()  # normalized, origin at the bottom left
        top = box.origin.y + box.size.height
        found.append(
            (-round(top, 2), box.origin.x, Line(str(best.string()), float(best.confidence())))
        )
    found.sort(key=lambda t: (t[0], t[1]))
    return [line for _, _, line in found]


def _read_image(data: bytes) -> list[Line]:
    import Vision
    from Foundation import NSData

    if not _vision_available():
        raise ReaderError(_NO_VISION, 503)
    nsdata = NSData.dataWithBytes_length_(data, len(data))
    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(nsdata, None)
    return _recognize(handler)


def _read_pdf(data: bytes) -> tuple[list[Line], int, str]:
    if not _vision_available():
        raise ReaderError(_NO_VISION, 503)
    import Quartz
    import Vision
    from Foundation import NSData

    nsdata = NSData.dataWithBytes_length_(data, len(data))
    document = Quartz.PDFDocument.alloc().initWithData_(nsdata)
    if document is None:
        raise ReaderError("That PDF couldn't be opened. It may be damaged or password protected.")
    pages = min(document.pageCount(), MAX_PDF_PAGES)
    lines: list[Line] = []
    used_vision = False
    for index in range(pages):
        page = document.pageAtIndex_(index)
        layer = str(page.string() or "")
        if len("".join(layer.split())) >= MIN_TEXT_LAYER_CHARS:
            lines.extend(Line(t.strip(), None, index + 1) for t in layer.splitlines() if t.strip())
            continue
        used_vision = True
        image = _render_pdf_page(page.pageRef())
        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(image, None)
        for line in _recognize(handler):
            line.page = index + 1
            lines.append(line)
    engine = "pdf-text+apple-vision" if used_vision else "pdf-text"
    return lines, pages, engine


def _render_pdf_page(page: object) -> object:
    import Quartz

    box = Quartz.CGPDFPageGetBoxRect(page, Quartz.kCGPDFMediaBox)
    width = int(box.size.width * PDF_RENDER_SCALE)
    height = int(box.size.height * PDF_RENDER_SCALE)
    space = Quartz.CGColorSpaceCreateDeviceRGB()
    ctx = Quartz.CGBitmapContextCreate(
        None, width, height, 8, 0, space, Quartz.kCGImageAlphaNoneSkipLast
    )
    Quartz.CGContextSetRGBFillColor(ctx, 1, 1, 1, 1)
    Quartz.CGContextFillRect(ctx, Quartz.CGRectMake(0, 0, width, height))
    Quartz.CGContextScaleCTM(ctx, PDF_RENDER_SCALE, PDF_RENDER_SCALE)
    Quartz.CGContextDrawPDFPage(ctx, page)
    return Quartz.CGBitmapContextCreateImage(ctx)


# --------------------------------------------------------------------------- documents and text


def _read_document(data: bytes, filename: str | None) -> list[Line]:
    tool = shutil.which("textutil") if sys.platform == "darwin" else None
    if tool is None:
        raise ReaderError("Reading Word and other documents needs macOS's textutil.", 503)
    suffix = os.path.splitext(filename or "")[1].lower()
    if suffix not in _DOC_SUFFIXES:
        suffix = ".rtf" if data.startswith(b"{\\rtf") else ".docx"
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, f"upload{suffix}")
        with open(path, "wb") as fh:
            fh.write(data)
        try:
            out = subprocess.run(
                [tool, "-convert", "txt", "-stdout", path],
                capture_output=True,
                timeout=20,
                check=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise ReaderError("That document couldn't be read.") from exc
    text = out.stdout.decode("utf-8", errors="replace")
    return [Line(t.strip()) for t in text.splitlines() if t.strip()]


def _read_text(data: bytes) -> list[Line]:
    text = data.decode("utf-8", errors="replace")
    return [Line(t.rstrip()) for t in text.splitlines() if t.strip()]


_NO_VISION = (
    "Reading photos and scanned PDFs uses Apple's on-device text recognizer, which needs the "
    "ProofLab backend running on a Mac."
)


def read_document(
    data: bytes, filename: str | None = None, content_type: str | None = None
) -> ReadResult:
    if not data:
        raise ReaderError("The file is empty.")
    if len(data) > MAX_BYTES:
        raise ReaderError("That file is too big (the limit is 15 MB).", 413)
    kind = detect(data, filename, content_type)
    if kind == "image":
        return ReadResult(kind, "apple-vision", 1, _read_image(data))
    if kind == "pdf":
        lines, pages, engine = _read_pdf(data)
        return ReadResult(kind, engine, pages, lines)
    if kind == "document":
        return ReadResult(kind, "textutil", 1, _read_document(data, filename))
    return ReadResult(kind, "text", 1, _read_text(data))
