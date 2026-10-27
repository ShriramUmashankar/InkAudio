"""Container checks without API keys: python /opt/lite/smoke.py --pdf [--url URL]."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
import urllib.error
import urllib.request


def check_http(url):
    def request(path, data=None, headers=None):
        req = urllib.request.Request(url.rstrip("/") + path, data=data, headers=headers or {})
        try:
            response = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.read()

    assert request("/api/health") == (200, b'{"status":"ok"}')
    status, body = request("/api/capabilities")
    assert status == 200 and json.loads(body) == {
        "lite": True, "tts_modes": ["bodhan"], "stt_enabled": False,
    }
    for path in ("/api/job/custom_voice", "/api/job/voice_design", "/api/transcribe"):
        status, body = request(path, data=b"invalid", headers={"Content-Type": "multipart/form-data"})
        assert status == 403 and "Lite" in json.loads(body)["detail"]
    assert request("/api/job")[1] == b'{"status":"idle"}'
    for name in ("Magnetism-Tamil", "Chemistry-Hindi", "Judiciary-English-Voice-Design", "Cell-English-Custom-Voice"):
        status, body = request(f"/podcast_examples/{name}/final_podcast.mp3", headers={"Range": "bytes=0-127"})
        assert status == 206 and len(body) == 128
    print("Lite HTTP and all example audio range checks passed.")


def check_pdfs():
    import torch
    from PIL import Image, ImageDraw, ImageFont
    sys.path.insert(0, str(Path.cwd()))
    from src.ingest import convert_pdf

    assert torch.version.cuda is None and not torch.cuda.is_available()
    for module in ("faster_whisper", "qwen_tts", "bitsandbytes"):
        assert importlib.util.find_spec(module) is None, module
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        # A native-text PDF built without an extra PDF-generation dependency.
        stream = b"BT /F1 24 Tf 72 720 Td (MAGNETISM) Tj 0 -40 Td (Magnets attract iron.) Tj ET"
        objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
                   b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
                   b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
                   b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
                   b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
        pdf = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for i, obj in enumerate(objects, 1):
            offsets.append(len(pdf))
            pdf.extend(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
        xref = len(pdf)
        pdf.extend(b"xref\n0 6\n0000000000 65535 f \n")
        for offset in offsets[1:]:
            pdf.extend(f"{offset:010d} 00000 n \n".encode())
        pdf.extend(f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
        (root / "native.pdf").write_bytes(pdf)

        image = Image.new("RGB", (1200, 1600), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default(size=48)
        draw.text((120, 180), "MAGNETISM", font=font, fill="black")
        draw.text((120, 260), "Magnets attract iron.", font=font, fill="black")
        image.save(root / "scanned.pdf", resolution=150)
        started = time.monotonic()
        for name in ("native", "scanned"):
            result = convert_pdf(str(root / f"{name}.pdf"), str(root))
            text = Path(result).read_text(encoding="utf-8").lower()
            assert "magnet" in text, (name, text)
        print(f"CPU native/scanned PDF checks passed in {time.monotonic() - started:.1f}s.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", action="store_true")
    parser.add_argument("--url")
    args = parser.parse_args()
    if not args.pdf and not args.url:
        parser.error("choose --pdf and/or --url")
    if args.pdf:
        check_pdfs()
    if args.url:
        check_http(args.url)
