from dataclasses import dataclass, field
from io import BytesIO

import pymupdf
from PIL import Image, UnidentifiedImageError


class FileRejected(ValueError):
    pass


@dataclass
class Inspection:
    mime: str
    pages: int
    route: str
    reason: str
    text: str = ""
    images: list[bytes] = field(default_factory=list)
    image_dimensions: list[tuple[int, int]] = field(default_factory=list)
    pdf_chunks: list[tuple[int, int, bytes]] = field(default_factory=list)


def inspect(data: bytes, max_bytes: int, max_pages: int) -> Inspection:
    if not data or len(data) > max_bytes:
        raise FileRejected("Empty file or file exceeds the configured size limit")
    if data.startswith(b"%PDF-"):
        try:
            with pymupdf.open(stream=data, filetype="pdf") as pdf:
                if pdf.is_encrypted:
                    raise FileRejected("Encrypted PDFs are not supported")
                if not 1 <= len(pdf) <= max_pages:
                    raise FileRejected("PDF exceeds the configured page limit")
                texts, uncertain, images, image_dimensions = [], [], [], []
                for page in pdf:
                    text = page.get_text().strip()
                    texts.append(text)
                    # get_image_info includes inline images. Drawings and annotations
                    # can contain financially relevant values not present in text.
                    suspicious = (
                        len(text) < 40
                        or bool(page.get_image_info())
                        or bool(page.get_drawings())
                        or bool(list(page.annots() or []))
                    )
                    uncertain.append(suspicious)
                # Always provide every PDF page as an image as well as its text.
                # This covers image-only scans and lets vision verify small totals,
                # dates, and layout-dependent labels even when a text layer exists.
                for page in pdf:
                    scale = min(2, 1200 / max(page.rect.width, page.rect.height))
                    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
                    images.append(pixmap.tobytes("png"))
                    image_dimensions.append((pixmap.width, pixmap.height))
                pdf_chunks = []
                chunk_size = 3
                for start in range(0, len(pdf), chunk_size):
                    end = min(start + chunk_size, len(pdf))
                    if start == 0 and end == len(pdf):
                        chunk_bytes = data
                    else:
                        chunk = pymupdf.open()
                        try:
                            chunk.insert_pdf(pdf, from_page=start, to_page=end - 1)
                            chunk_bytes = chunk.tobytes(garbage=4, deflate=True)
                        finally:
                            chunk.close()
                    pdf_chunks.append((start + 1, end, chunk_bytes))
                route = (
                    "text"
                    if not any(uncertain)
                    else ("vision" if all(uncertain) else "mixed/fallback")
                )
                return Inspection(
                    "application/pdf",
                    len(pdf),
                    route,
                    "All PDF pages are supplied as images alongside extracted text"
                    if route == "text"
                    else "All PDF pages are supplied as images alongside any extracted text",
                    "\n\n".join(texts),
                    images,
                    image_dimensions,
                    pdf_chunks,
                )
        except FileRejected:
            raise
        except Exception as exc:
            raise FileRejected("Corrupt or unreadable PDF") from exc
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise FileRejected("Only PDF, JPEG, PNG and WEBP are supported")
            if image.width * image.height > 25_000_000:
                raise FileRejected("Image exceeds the pixel limit")
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image_format = image.format
            image = image.convert("RGB")
            image.thumbnail((1600, 1600))
            output = BytesIO()
            image.save(output, format="PNG")
        return Inspection(
            Image.MIME.get(image_format, "image/png"),
            1,
            "vision",
            "Image requires multimodal extraction",
            images=[output.getvalue()],
            image_dimensions=[(image.width, image.height)],
        )
    except FileRejected:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise FileRejected("Unsupported or corrupt image") from exc
