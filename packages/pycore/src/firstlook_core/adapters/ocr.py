"""OCR for scanned PDFs and images. Tesseract locally; swappable later."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Protocol


class OcrEngine(Protocol):
    available: bool

    def image_to_text(self, data: bytes, suffix: str = ".png") -> str: ...


class TesseractOcr:
    def __init__(self, binary: str = "tesseract"):
        self.binary = shutil.which(binary)
        self.available = self.binary is not None

    def image_to_text(self, data: bytes, suffix: str = ".png") -> str:
        if not self.binary:
            raise RuntimeError("tesseract is not installed")
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / f"in{suffix}"
            src.write_bytes(data)
            out = subprocess.run(
                [self.binary, str(src), "stdout"], capture_output=True, check=True, timeout=120
            )
            return out.stdout.decode("utf-8", errors="replace")


class NoopOcr:
    """Used when no OCR engine is installed: returns nothing, never fails."""

    available = False

    def image_to_text(self, data: bytes, suffix: str = ".png") -> str:
        return ""


@lru_cache
def get_ocr() -> OcrEngine:
    engine = TesseractOcr()
    return engine if engine.available else NoopOcr()
