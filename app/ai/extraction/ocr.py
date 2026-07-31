import io
from pathlib import Path

import fitz  # PyMuPDF — pure-pip PDF rendering, no external binary needed
import pytesseract
from PIL import Image

PAGE_MARKER = "\n\n--- PAGE {page_no} ---\n\n"


def ocr_pdf_to_text(pdf_path: Path, *, dpi: int = 300) -> str:
    """Rasterizes each page of the PDF and runs Tesseract over it. Page
    boundaries are marked in the output text (`--- PAGE N ---`) so the LLM
    can still report which page a field came from downstream — the one
    provenance signal OCR can preserve. There's no equivalent for pixel-level
    bounding boxes: OCR discards layout/geometry, so unlike the native-vision
    extraction this replaced, extraction results here carry no bounding_box."""
    doc = fitz.open(pdf_path)
    try:
        pages_text = []
        for page_no, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=dpi)
            image = Image.open(io.BytesIO(pix.tobytes("png")))
            page_text = pytesseract.image_to_string(image)
            pages_text.append(PAGE_MARKER.format(page_no=page_no) + page_text)
        return "".join(pages_text).strip()
    finally:
        doc.close()
