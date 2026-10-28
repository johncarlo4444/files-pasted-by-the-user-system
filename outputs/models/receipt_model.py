"""Format and save cashier receipts as UTF-8 text files."""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable

from config import (
    RESTAURANT_ADDRESS,
    RESTAURANT_BRANCH,
    RESTAURANT_CONTACT,
    RESTAURANT_NAME,
    RESTAURANT_TAGLINE,
)


CENT = Decimal("0.01")


def _money(value: Decimal | int | float | str) -> str:
    amount = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    return f"₱{amount:,.2f}"


@dataclass(frozen=True)
class ReceiptItem:
    quantity: int
    name: str
    line_total: Decimal | int | float | str
    customization: str = ""
    special_instructions: str = ""


@dataclass(frozen=True)
class ReceiptData:
    order_code: str
    order_type: str
    cashier_name: str
    items: Iterable[ReceiptItem]
    subtotal: Decimal | int | float | str
    vat: Decimal | int | float | str
    total_amount: Decimal | int | float | str
    payment_method: str
    amount_tendered: Decimal | int | float | str
    change_returned: Decimal | int | float | str
    timestamp: datetime = field(default_factory=datetime.now)
    restaurant_name: str = RESTAURANT_NAME
    tagline: str = RESTAURANT_TAGLINE
    branch: str = RESTAURANT_BRANCH
    address: str = RESTAURANT_ADDRESS
    contact: str = RESTAURANT_CONTACT


def format_receipt(data: ReceiptData, *, width: int = 42) -> str:
    """Return a thermal-printer-style receipt as printable text."""
    if width < 30:
        raise ValueError("Receipt width must be at least 30 characters.")

    rule = "=" * width
    thin_rule = "-" * width
    lines = [data.restaurant_name.center(width)]
    lines.extend(line.center(width) for line in textwrap.wrap(data.tagline, width=width))
    lines.extend((data.branch.center(width), data.address.center(width)))
    lines.append(f"Contact: {data.contact}".center(width))
    lines.extend(
        [
            rule,
            f"Date: {data.timestamp:%Y-%m-%d %H:%M:%S}",
            f"Order: {data.order_code}",
            f"Type: {data.order_type}",
            f"Cashier: {data.cashier_name}",
            thin_rule,
            "QTY  ITEM".ljust(width - 12) + "LINE TOTAL".rjust(12),
            thin_rule,
        ]
    )

    for item in data.items:
        qty_text = str(item.quantity)
        amount = _money(item.line_total)
        name_width = max(8, width - len(qty_text) - len(amount) - 4)
        wrapped_names = textwrap.wrap(item.name, width=name_width) or [""]
        lines.append(f"{qty_text:>3}  {wrapped_names[0]:<{name_width}} {amount:>12}")
        for continuation in wrapped_names[1:]:
            lines.append(f"     {continuation}")
        for label, note in (
            ("Customization", item.customization),
            ("Instructions", item.special_instructions),
        ):
            if note.strip():
                for note_line in textwrap.wrap(f"{label}: {note.strip()}", width=width - 2):
                    lines.append(f"  {note_line}")

    lines.extend(
        [
            thin_rule,
            f"Subtotal: {_money(data.subtotal)}".rjust(width),
            f"VAT/Taxes: {_money(data.vat)}".rjust(width),
            f"TOTAL DUE: {_money(data.total_amount)}".rjust(width),
            thin_rule,
            f"Payment: {data.payment_method}",
            f"Tendered: {_money(data.amount_tendered)}".rjust(width),
            f"Change: {_money(data.change_returned)}".rjust(width),
            rule,
            "Thank you for dining with us!".center(width),
            "Please present your order code at the".center(width),
            "kitchen counter.".center(width),
            rule,
        ]
    )
    return "\n".join(lines) + "\n"


def save_receipt(
    data: ReceiptData,
    directory: str | Path | None = None,
    *,
    width: int = 42,
) -> Path:
    """Save a receipt under ``receipts/`` and return its absolute path."""
    target_dir = Path(directory) if directory else Path(__file__).resolve().parents[1] / "receipts"
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_code = re.sub(r"[^A-Za-z0-9_-]", "_", data.order_code).strip("_") or "order"
    stamp = data.timestamp.strftime("%Y%m%d_%H%M%S")
    target = target_dir / f"receipt_{safe_code}_{stamp}.txt"
    target.write_text(format_receipt(data, width=width), encoding="utf-8", newline="\n")
    return target.resolve()


def save_receipt_pdf(data: ReceiptData, path: str | Path | None = None) -> Path:
    """Save a compact thermal-width PDF copy of a receipt."""
    try:
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise RuntimeError("PDF export requires reportlab. Install the app dependencies first.") from exc

    if path is None:
        target_dir = Path(__file__).resolve().parents[1] / "receipts"
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_code = re.sub(r"[^A-Za-z0-9_-]", "_", data.order_code).strip("_") or "order"
        stamp = data.timestamp.strftime("%Y%m%d_%H%M%S")
        target = target_dir / f"receipt_{safe_code}_{stamp}.pdf"
    else:
        target = Path(path).expanduser().resolve()
        if target.suffix.lower() != ".pdf":
            target = target.with_suffix(".pdf")
        target.parent.mkdir(parents=True, exist_ok=True)

    lines = format_receipt(data, width=42).splitlines()
    page_width = 80 * mm
    line_height = 10
    page_height = max(220, (len(lines) + 3) * line_height + 20)
    document = canvas.Canvas(str(target), pagesize=(page_width, page_height))
    document.setTitle(f"Receipt {data.order_code}")
    document.setFont("Courier", 7.6)
    y = page_height - 16
    for line in lines:
        safe_line = line.replace("\u20b1", "PHP ").encode("ascii", "replace").decode("ascii")
        document.drawString(8, y, safe_line)
        y -= line_height
    document.save()
    return target.resolve()
