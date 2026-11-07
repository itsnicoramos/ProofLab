from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from prooflab.content import load_registry
from prooflab.main import Settings, create_app
from prooflab.reader import ReaderError, capabilities, detect, read_document

REGISTRY = load_registry(courses=["calc1"])


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app(Settings(isolate=False), REGISTRY))


def test_detects_file_kinds():
    assert detect(b"%PDF-1.7 ...") == "pdf"
    assert detect(b"\x89PNG\r\n\x1a\n....") == "image"
    assert detect(b"\xff\xd8\xff\xe0....") == "image"
    assert detect(b"{\\rtf1\\ansi ...}") == "document"
    assert detect(b"PK\x03\x04....", "work.docx") == "document"
    assert detect(b"n = 2k + 1\n") == "text"
    with pytest.raises(ReaderError):
        detect(b"\x00\xff\xfe\x80\x81 binary", "x.bin")


def test_plain_text_is_split_into_lines():
    result = read_document(b"Let n = 2k + 1\n\n n^2 = 4k^2 + 4k + 1 \n")
    assert [line.text for line in result.lines] == ["Let n = 2k + 1", " n^2 = 4k^2 + 4k + 1"]
    assert result.kind == "text" and result.engine == "text"


def test_empty_and_huge_files_are_refused():
    with pytest.raises(ReaderError):
        read_document(b"")
    with pytest.raises(ReaderError) as exc:
        read_document(b"x" * (16 * 1024 * 1024))
    assert exc.value.status == 413


def test_read_endpoint_text(client):
    r = client.post("/read", content=b"a = 1\nb = 2\n", headers={"content-type": "text/plain"})
    assert r.status_code == 200
    body = r.json()
    assert body["text"] == "a = 1\nb = 2" and len(body["lines"]) == 2


def test_capabilities_endpoint(client):
    caps = client.get("/read").json()
    assert caps == capabilities() and caps["text"] is True


@pytest.mark.skipif(not capabilities()["images"], reason="needs macOS Vision")
def test_reads_a_rendered_image():
    from AppKit import (
        NSBitmapImageRep,
        NSColor,
        NSDeviceRGBColorSpace,
        NSFont,
        NSFontAttributeName,
        NSGraphicsContext,
        NSMakeRect,
        NSPNGFileType,
        NSRectFill,
        NSString,
    )

    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(  # noqa: E501
        None, 900, 200, 8, 4, True, False, NSDeviceRGBColorSpace, 0, 0
    )
    ctx = NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(ctx)
    NSColor.whiteColor().set()
    NSRectFill(NSMakeRect(0, 0, 900, 200))
    attrs = {NSFontAttributeName: NSFont.fontWithName_size_("Helvetica", 56)}
    NSString.stringWithString_("x = 2k + 1").drawAtPoint_withAttributes_((40, 70), attrs)
    ctx.flushGraphics()
    NSGraphicsContext.restoreGraphicsState()
    png = bytes(rep.representationUsingType_properties_(NSPNGFileType, {}))
    result = read_document(png, "work.png")
    assert result.kind == "image" and result.engine == "apple-vision"
    assert "".join(result.text.split()) == "x=2k+1"
