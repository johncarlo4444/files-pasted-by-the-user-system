"""Small shared helpers for Tkinter views."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from tkinter import messagebox


def php(value: object) -> str:
    amount = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"₱{amount:,.2f}"


def show_error(error: Exception, title: str = "Unable to complete action") -> None:
    messagebox.showerror(title, str(error))


def clear_frame(frame) -> None:
    for child in frame.winfo_children():
        child.destroy()
