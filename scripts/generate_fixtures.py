"""Generate fictional documents and separately labeled ground truth, never live AI results."""

import hashlib
import json
from io import BytesIO
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw

ROOT = Path("tests/fixtures")


def picture(lines):
    image = Image.new("RGB", (1000, 650), "white")
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(lines):
        draw.text((45, 30 + index * 48), line, fill="black", font_size=26)
    out = BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def generate():
    ROOT.mkdir(parents=True, exist_ok=True)
    base = {
        "document_type": "invoice",
        "vendor": "Fictional Meadow Tools",
        "date": "2026-10-12",
        "document_number": "DEMO-001",
        "description": "Field sampling equipment",
        "subtotal": "100.00",
        "tax": "20.00",
        "grand_total": "120.00",
        "currency": "EUR",
        "tax_mode": "exclusive",
        "category_id": "equipment",
        "items": [
            {
                "description": "Sampling kit",
                "quantity": "1",
                "unit_price": "100.00",
                "line_amount": "100.00",
            }
        ],
        "evidence": ["Page 1: Grand total EUR 120.00"],
    }
    cases = [
        ("digital.pdf", base, "text"),
        (
            "missing-total.pdf",
            {**base, "document_number": "DEMO-002", "grand_total": None, "evidence": []},
            "text",
        ),
        (
            "missing-currency.pdf",
            {**base, "document_number": "DEMO-003", "currency": None, "evidence": []},
            "text",
        ),
        (
            "tax-inclusive.pdf",
            {**base, "document_number": "DEMO-004", "subtotal": "120.00", "tax_mode": "inclusive"},
            "text",
        ),
        (
            "discount.pdf",
            {
                **base,
                "document_number": "DEMO-005",
                "discount": "10.00",
                "discount_explicit": True,
                "grand_total": "110.00",
                "evidence": ["Page 1: Discount 10.00 applied; Grand total EUR 110.00"],
            },
            "text",
        ),
        (
            "arithmetic-conflict.pdf",
            {
                **base,
                "document_number": "DEMO-006",
                "grand_total": "160.00",
                "evidence": ["Page 1: Grand total EUR 160.00"],
            },
            "text",
        ),
        (
            "legitimate-purchase.pdf",
            {
                **base,
                "document_number": "DEMO-007",
                "items": [{"description": "Measuring tape"}],
                "description": "Measuring tape",
            },
            "text",
        ),
        (
            "business-duplicate.pdf",
            {**base, "description": "Field sampling equipment (copy)"},
            "text",
        ),
        (
            "scanned.pdf",
            {
                **base,
                "document_number": "DEMO-008",
                "currency": "USD",
                "evidence": ["Page 1: Grand total USD 120.00"],
            },
            "vision",
        ),
        ("mixed.pdf", {**base, "document_number": "DEMO-009"}, "mixed/fallback"),
    ]
    manifest = []
    for filename, candidate, expected_route in cases:
        lines = [
            "FICTIONAL DEMO DOCUMENT - not a real invoice",
            candidate["vendor"],
            f"Invoice {candidate['document_number']}",
            f"Date {candidate['date']}",
            candidate["description"],
            f"Subtotal {candidate['subtotal']}",
            f"VAT {candidate['tax']} ({candidate['tax_mode']})",
        ]
        if candidate.get("discount"):
            lines.append(f"Discount {candidate['discount']} applied to subtotal")
        currency = candidate.get("currency") or "[not reported]"
        total = f"Grand total {currency} {candidate['grand_total']}"
        if candidate["grand_total"] is None:
            total = "Grand total: [not reported]"
        pdf = pymupdf.open()
        if expected_route == "vision":
            page = pdf.new_page()
            page.insert_image(pymupdf.Rect(10, 10, 580, 460), stream=picture(lines + [total]))
        else:
            page = pdf.new_page()
            page.insert_text(
                (45, 50),
                "\n".join(lines + ([] if filename == "mixed.pdf" else [total])),
                fontsize=12,
            )
            if filename == "mixed.pdf":
                second = pdf.new_page()
                second.insert_image(pymupdf.Rect(10, 10, 580, 460), stream=picture([total]))
        # Stable document IDs make regeneration independent of wall-clock time.
        data = pdf.tobytes(no_new_id=True)
        pdf.close()
        (ROOT / filename).write_bytes(data)
        manifest.append(
            {
                "file": filename,
                "sha256": hashlib.sha256(data).hexdigest(),
                "route": expected_route,
                "candidate": candidate,
            }
        )
    receipt = {
        **base,
        "document_type": "receipt",
        "document_number": None,
        "vendor": "Fictional North Rail",
        "description": "Workshop train travel",
        "category_id": "travel",
        "currency": "USD",
        "subtotal": None,
        "tax": None,
        "tax_mode": "unknown",
        "grand_total": "45.50",
        "items": [],
        "evidence": ["Receipt: USD 45.50"],
    }
    data = picture(
        [
            "FICTIONAL DEMO RECEIPT",
            "Fictional North Rail",
            "2026-10-12",
            "Workshop train travel",
            "Grand total USD 45.50",
        ]
    )
    (ROOT / "receipt.png").write_bytes(data)
    manifest.append(
        {
            "file": "receipt.png",
            "sha256": hashlib.sha256(data).hexdigest(),
            "route": "vision",
            "candidate": receipt,
        }
    )
    (ROOT / "ground_truth.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Generated {len(manifest)} fictional documents and labeled ground truth.")


if __name__ == "__main__":
    generate()
