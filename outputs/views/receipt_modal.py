"""Digital receipt preview opened after cashier checkout."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from models.receipt_model import ReceiptData, format_receipt, save_receipt, save_receipt_pdf


class ReceiptModal(tk.Toplevel):
    def __init__(self, parent, receipt: ReceiptData, on_next=None):
        super().__init__(parent)
        self.receipt = receipt
        self.on_next = on_next
        self.title(f"Official Digital Receipt — {receipt.order_code}")
        self.transient(parent.winfo_toplevel())
        self.geometry("520x700")
        self.minsize(440, 520)
        self.grab_set()
        self.configure(background="white")

        ttk.Label(self, text="WORLD FAST FOOD EXPRESS", style="ReceiptTitle.TLabel").pack(
            anchor="center", padx=14, pady=(14, 2)
        )
        ttk.Label(self, text="Official Digital Receipt", style="ReceiptSubtitle.TLabel").pack(
            anchor="center", padx=14, pady=(0, 10)
        )
        self.text = tk.Text(
            self, wrap="none", font=("Consolas", 10), padx=14, pady=10,
            background="white", foreground="#292524", selectbackground="#c62828",
            relief="flat", highlightthickness=1, highlightbackground="#e6d8d2",
        )
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=(0, 12))
        scroll.pack(side="right", fill="y", padx=(0, 14), pady=(0, 12))
        self.text.insert("1.0", format_receipt(receipt))
        self.text.configure(state="disabled")

        actions = ttk.Frame(self, padding=(14, 0, 14, 14))
        actions.pack(fill="x", side="bottom")
        ttk.Button(actions, text="Save PDF", command=self._save_pdf).pack(side="left")
        ttk.Button(actions, text="Save Receipt (.txt)", command=self._save).pack(side="left")
        ttk.Button(actions, text="Print Receipt", command=self._print).pack(side="left", padx=8)
        ttk.Button(actions, text="Close / Next Transaction", command=self._next).pack(side="right")
        self.protocol("WM_DELETE_WINDOW", self._next)

    def _save(self) -> None:
        try:
            path = save_receipt(self.receipt)
            messagebox.showinfo("Receipt saved", f"Receipt saved to:\n{path}", parent=self)
        except Exception as exc:
            messagebox.showerror("Could not save receipt", str(exc), parent=self)

    def _print(self) -> None:
        try:
            path = save_receipt_pdf(self.receipt)
            if not hasattr(os, "startfile"):
                raise OSError("Printing through the default PDF application is available on Windows only.")
            os.startfile(str(path), "print")
        except Exception as exc:
            messagebox.showerror("Could not print receipt", f"{exc}\n\nYou can still save the PDF or text receipt.", parent=self)

    def _save_pdf(self) -> None:
        filename = f"receipt_{self.receipt.order_code}.pdf"
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Save Receipt PDF",
            initialfile=filename,
            defaultextension=".pdf",
            filetypes=(("PDF files", "*.pdf"),),
        )
        if not path:
            return
        try:
            saved_path = save_receipt_pdf(self.receipt, path)
            messagebox.showinfo("Receipt saved", f"Receipt PDF saved to:\n{saved_path}", parent=self)
        except Exception as exc:
            messagebox.showerror("Could not save receipt PDF", str(exc), parent=self)

    def _next(self) -> None:
        self.destroy()
        if self.on_next:
            self.on_next()
