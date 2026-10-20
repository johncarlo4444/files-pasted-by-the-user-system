"""Cashier order lookup, payment entry, and receipt generation."""

from __future__ import annotations

import tkinter as tk
from decimal import Decimal, InvalidOperation
from tkinter import messagebox, ttk

from models import order_model
from models.receipt_model import ReceiptData, ReceiptItem
from views.common import php, show_error
from views.receipt_modal import ReceiptModal


class CashierView(ttk.Frame):
    def __init__(self, parent, cashier: dict):
        super().__init__(parent, padding=14)
        self.cashier = cashier
        self.order: dict | None = None
        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, text="Cashier Checkout", style="MenuTitle.TLabel").pack(side="left")
        ttk.Button(header, text="Transaction History", command=self.open_history).pack(side="right")
        search = ttk.LabelFrame(self, text="Find an order", padding=10)
        search.pack(fill="x", pady=(12, 10))
        self.code_var = tk.StringVar()
        entry = ttk.Entry(search, textvariable=self.code_var, width=18, font=("Segoe UI", 16))
        entry.pack(side="left")
        entry.bind("<Return>", lambda _event: self.lookup())
        ttk.Button(search, text="Search Order", command=self.lookup).pack(side="left", padx=8)
        ttk.Button(search, text="Clear", command=self.clear).pack(side="left")

        self.details = ttk.LabelFrame(self, text="Order Verification", padding=12)
        self.details.pack(fill="both", expand=True)
        self.summary_var = tk.StringVar(value="Enter the order code to verify the customer order.")
        ttk.Label(self.details, textvariable=self.summary_var, justify="left").pack(anchor="w", pady=(0, 8))
        self.items = ttk.Treeview(self.details, columns=("qty", "custom", "amount"), show="tree headings", height=10)
        for col, title in (("#0", "Item"), ("qty", "Qty"), ("custom", "Customization / Notes"), ("amount", "Line Total")):
            self.items.heading(col, text=title)
        self.items.column("#0", width=230)
        self.items.column("qty", width=55, anchor="center")
        self.items.column("custom", width=280)
        self.items.column("amount", width=110, anchor="e")
        self.items.pack(fill="both", expand=True)

        payment = ttk.LabelFrame(self, text="Record Payment", padding=12)
        payment.pack(fill="x", pady=(10, 0))
        ttk.Label(payment, text="Method").grid(row=0, column=0, sticky="w")
        self.method_var = tk.StringVar(value="Cash")
        method = ttk.Combobox(payment, textvariable=self.method_var, values=("Cash", "GCash", "Card"),
                              state="readonly", width=14)
        method.grid(row=0, column=1, padx=(8, 18), sticky="w")
        method.bind("<<ComboboxSelected>>", lambda _event: self._set_due_amount())
        ttk.Label(payment, text="Amount Tendered (PHP)").grid(row=0, column=2, sticky="w")
        self.amount_var = tk.StringVar()
        ttk.Entry(payment, textvariable=self.amount_var, width=18).grid(row=0, column=3, padx=8, sticky="w")
        self.total_var = tk.StringVar(value="Total: ₱0.00")
        ttk.Label(payment, textvariable=self.total_var, style="MetricValue.TLabel").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(10, 0)
        )
        ttk.Button(payment, text="Confirm Payment & Generate Receipt", command=self.pay).grid(
            row=1, column=2, columnspan=2, sticky="e", pady=(10, 0)
        )
        for col in range(4):
            payment.columnconfigure(col, weight=1)

    def lookup(self) -> None:
        code = self.code_var.get().strip()
        if not code:
            messagebox.showinfo("Order code required", "Enter the order code printed on the kiosk slip.")
            return
        try:
            self.order = order_model.get_order_by_code(code)
            if not self.order:
                raise ValueError("No order was found with that code.")
            self._render_order()
        except Exception as exc:
            self.order = None
            self._render_order()
            show_error(exc, "Order lookup failed")

    def _render_order(self) -> None:
        for iid in self.items.get_children():
            self.items.delete(iid)
        if not self.order:
            self.summary_var.set("Enter the order code to verify the customer order.")
            self.total_var.set("Total: ₱0.00")
            self.amount_var.set("")
            return
        order = self.order
        self.summary_var.set(
            f"Order: {order['order_code']}    Type: {order['order_type']}    "
            f"Created: {order['created_at']}\n"
            f"Payment: {order['payment_status']}    Status: {order['order_status']}"
        )
        for item in order["items"]:
            notes = ", ".join(filter(None, (item.get("customization"), item.get("special_instructions"))))
            self.items.insert("", "end", text=item["product_name"],
                              values=(item["quantity"], notes, php(item["subtotal"])))
        self.total_var.set(f"Total: {php(order['total_amount'])}")
        self.amount_var.set(f"{Decimal(str(order['total_amount'])):.2f}")

    def _set_due_amount(self) -> None:
        if self.order:
            self.amount_var.set(f"{Decimal(str(self.order['total_amount'])):.2f}")

    def pay(self) -> None:
        if not self.order:
            messagebox.showinfo("Search for an order", "Verify an order before recording payment.")
            return
        try:
            tendered = Decimal(self.amount_var.get().strip())
            payment = order_model.record_payment(
                self.order["order_code"], self.method_var.get(), tendered,
                cashier_user_id=int(self.cashier["user_id"]),
            )
            paid_order = order_model.get_order_by_code(self.order["order_code"])
            if not paid_order:
                raise RuntimeError("Payment was recorded, but the order could not be reloaded.")
            receipt = ReceiptData(
                order_code=paid_order["order_code"],
                order_type=paid_order["order_type"],
                cashier_name=self.cashier["username"],
                items=[
                    ReceiptItem(
                        quantity=int(item["quantity"]),
                        name=item["product_name"],
                        line_total=item["subtotal"],
                        customization=item.get("customization") or "",
                        special_instructions=item.get("special_instructions") or "",
                    )
                    for item in paid_order["items"]
                ],
                subtotal=paid_order["total_amount"],
                vat=Decimal("0.00"),
                total_amount=paid_order["total_amount"],
                payment_method=payment["payment_method"],
                amount_tendered=payment["amount_tendered"],
                change_returned=payment["change_returned"],
            )
            ReceiptModal(self, receipt, on_next=self.clear)
        except (InvalidOperation, ValueError) as exc:
            show_error(exc, "Payment was not recorded")
        except Exception as exc:
            show_error(exc, "Payment was not recorded")

    def clear(self) -> None:
        self.order = None
        self.code_var.set("")
        self._render_order()

    def open_history(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Transaction History")
        dialog.transient(self.winfo_toplevel())
        dialog.geometry("850x480")
        panel = ttk.Frame(dialog, padding=12)
        panel.pack(fill="both", expand=True)
        toolbar = ttk.Frame(panel)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Label(toolbar, text="Search by order code or date").pack(side="left")
        search_var = tk.StringVar()
        entry = ttk.Entry(toolbar, textvariable=search_var, width=28)
        entry.pack(side="left", padx=8)
        tree = ttk.Treeview(panel, columns=("type", "total", "payment", "status", "created"),
                            show="tree headings")
        for column, label in (("#0", "Order Code"), ("type", "Type"), ("total", "Total"),
                              ("payment", "Payment"), ("status", "Status"), ("created", "Created")):
            tree.heading(column, text=label)
        tree.column("#0", width=110)
        tree.column("type", width=100)
        tree.column("total", width=110, anchor="e")
        tree.column("payment", width=110)
        tree.column("status", width=120)
        tree.column("created", width=180)
        tree.pack(fill="both", expand=True)

        def refresh() -> None:
            try:
                orders = order_model.list_orders(search=search_var.get(), limit=500)
                for iid in tree.get_children():
                    tree.delete(iid)
                for order in orders:
                    if order["payment_status"] not in ("Paid", "Cancelled"):
                        continue
                    tree.insert("", "end", iid=str(order["order_id"]), text=order["order_code"],
                                values=(order["order_type"], php(order["total_amount"]),
                                        order["payment_status"], order["order_status"], order["created_at"]))
            except Exception as exc:
                show_error(exc, "Could not load transaction history")

        def load_selected(_event=None) -> None:
            selection = tree.selection()
            if selection:
                self.code_var.set(tree.item(selection[0], "text"))
                dialog.destroy()
                self.lookup()

        ttk.Button(toolbar, text="Search", command=refresh).pack(side="left")
        ttk.Button(toolbar, text="Load Selected", command=load_selected).pack(side="right")
        tree.bind("<Double-1>", load_selected)
        entry.bind("<Return>", lambda _event: refresh())
        refresh()
