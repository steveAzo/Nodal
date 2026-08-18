import shutil
from io import BytesIO
from pathlib import Path

import pytesseract
from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings

_COMMON_WINDOWS_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


def _resolve_tesseract_cmd() -> str | None:
    settings = get_settings()
    if settings.tesseract_cmd:
        return settings.tesseract_cmd
    if shutil.which("tesseract"):
        return None  # already on PATH, let pytesseract find it itself
    for path in _COMMON_WINDOWS_PATHS:
        if Path(path).exists():
            return path
    return None


_cmd = _resolve_tesseract_cmd()
if _cmd:
    pytesseract.pytesseract.tesseract_cmd = _cmd


class UnsupportedDocumentError(Exception):
    pass


def extract_text(file_bytes: bytes) -> str:
    """OCR an uploaded image (utility bill / statement photo) to raw text.

    Images only for this prototype — PDF support needs Poppler as an extra
    system dependency on top of Tesseract, which isn't worth the setup cost
    for a hackathon build.
    """
    try:
        image = Image.open(BytesIO(file_bytes))
        image.load()
    except UnidentifiedImageError as exc:
        raise UnsupportedDocumentError(
            "Could not read this file as an image. Only JPG/PNG photos of the "
            "document are supported (no PDF) in this prototype."
        ) from exc

    return pytesseract.image_to_string(image)
