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
                texts, uncertain, images = [], [], []
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
                if any(uncertain):
                    # Include every page so visual totals retain their textual context.
                    for page in pdf:
                        scale = min(2, 1600 / max(page.rect.width, page.rect.height))
                        images.append(
                            page.get_pixmap(matrix=pymupdf.Matrix(scale, scale)).tobytes("png")
                        )
                route = (
                    "text"
                    if not any(uncertain)
                    else ("vision" if all(uncertain) else "mixed/fallback")
                )
                return Inspection(
                    "application/pdf",
                    len(pdf),
                    route,
                    "All pages have usable text and no detected visual ambiguity"
                    if route == "text"
                    else "Sparse text, images, drawings or annotations require visual review",
                    "\n\n".join(texts),
                    images,
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
            image = image.convert("RGB")
            image.thumbnail((1600, 1600))
            output = BytesIO()
            image.save(output, format="PNG")
        return Inspection(
            Image.MIME.get(Image.open(BytesIO(data)).format, "image/png"),
            1,
            "vision",
            "Image requires multimodal extraction",
            images=[output.getvalue()],
        )
    except FileRejected:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise FileRejected("Unsupported or corrupt image") from exc
