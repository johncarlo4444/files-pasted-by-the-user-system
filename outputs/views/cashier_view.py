"""Cashier order lookup, payment entry, and receipt generation."""

from __future__ import annotations

import tkinter as tk
from decimal import Decimal, InvalidOperation
from tkinter import messagebox, simpledialog, ttk

from models import order_model
from models.receipt_model import ReceiptData, ReceiptItem
from views.common import php, show_error, size_popup
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
        ttk.Label(search, text="Pending orders (oldest first)").grid(row=0, column=0, sticky="w")
        self.pending_var = tk.StringVar()
        self.pending_codes: dict[str, str] = {}
        self.pending_box = ttk.Combobox(search, textvariable=self.pending_var, state="readonly", width=58)
        self.pending_box.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(4, 8))
        self.pending_box.bind("<<ComboboxSelected>>", self._pending_selected)
        self.pending_box.bind("<Button-1>", lambda _event: self._refresh_pending_orders(), add="+")
        self.code_var = tk.StringVar()
        entry = ttk.Entry(search, textvariable=self.code_var, width=18, font=("Segoe UI", 16))
        entry.grid(row=2, column=0, sticky="w")
        entry.bind("<Return>", lambda _event: self.lookup())
        ttk.Button(search, text="Search Order", command=self.lookup).grid(row=2, column=1, padx=8, sticky="w")
        ttk.Button(search, text="Clear", command=self.clear).grid(row=2, column=2, sticky="w")
        ttk.Button(search, text="Refresh Queue", command=self._refresh_pending_orders).grid(
            row=2, column=3, padx=(10, 0), sticky="w"
        )
        search.columnconfigure(0, weight=1)

        self.details = ttk.LabelFrame(self, text="Order Verification", padding=12)
        self.details.pack(fill="both", expand=True)
        self.summary_var = tk.StringVar(value="Enter the order code to verify the customer order.")
        ttk.Label(self.details, textvariable=self.summary_var, justify="left").pack(anchor="w", pady=(0, 8))

        # Keep cashier editing actions above the expandable item list. Packing
        # them after the Treeview can push them out of view on shorter screens.
        edit_bar = ttk.LabelFrame(self.details, text="Order item actions", padding=(8, 6))
        edit_bar.pack(fill="x", pady=(0, 8))
        self.edit_quantity_button = ttk.Button(edit_bar, text="Change Quantity", command=self.change_quantity)
        self.edit_quantity_button.pack(side="left", padx=(0, 6))
        self.remove_item_button = ttk.Button(edit_bar, text="Remove Selected Item", command=self.remove_item)
        self.remove_item_button.pack(side="left", padx=6)
        self.cancel_order_button = ttk.Button(edit_bar, text="Cancel Order", command=self.cancel_current_order)
        self.cancel_order_button.pack(side="left", padx=6)
        ttk.Label(
            edit_bar,
            text="Select an item first. Reducing quantity, removing items, or cancelling requires an admin username and password.",
            wraplength=430,
        ).pack(side="right", padx=6)

        self.items = ttk.Treeview(self.details, columns=("qty", "custom", "amount"), show="tree headings", height=6)
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
        self.amount_var.trace_add("write", lambda *_args: self._update_change_display())
        ttk.Entry(payment, textvariable=self.amount_var, width=18, font=("Segoe UI", 14)).grid(
            row=0, column=3, padx=8, sticky="w"
        )
        self.total_var = tk.StringVar(value="Total: ₱0.00")
        ttk.Label(payment, textvariable=self.total_var, style="MetricValue.TLabel").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(10, 0)
        )
        self.pay_button = ttk.Button(payment, text="Confirm Payment & Generate Receipt", command=self.pay)
        self.pay_button.grid(
            row=1, column=2, columnspan=2, sticky="e", pady=(10, 0)
        )
        self.change_var = tk.StringVar(value="Change: —")
        ttk.Label(payment, textvariable=self.change_var, style="ChangeValue.TLabel").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )
        for col in range(4):
            payment.columnconfigure(col, weight=1)
        # Reserve the payment controls at the bottom before letting the order
        # details expand into the remaining cashier workspace.
        self.details.pack_forget()
        payment.pack(side="bottom", fill="x", pady=(10, 0))
        self.details.pack(fill="both", expand=True)
        self._refresh_pending_orders()
        self._update_action_states()

    def _refresh_pending_orders(self) -> None:
        try:
            orders = order_model.list_pending_orders()
            self.pending_codes.clear()
            labels = []
            for order in orders:
                label = (f"{order['order_code']}  |  {order['created_at']}  |  "
                         f"{order['order_type']}  |  {php(order['total_amount'])}")
                labels.append(label)
                self.pending_codes[label] = order["order_code"]
            self.pending_box.configure(values=labels)
            if self.pending_var.get() not in self.pending_codes:
                self.pending_var.set("")
        except Exception as exc:
            show_error(exc, "Could not load pending orders")

    def _pending_selected(self, _event=None) -> None:
        code = self.pending_codes.get(self.pending_var.get())
        if code:
            self.code_var.set(code)
            self.lookup()

    def _is_editable_order(self) -> bool:
        return bool(self.order and self.order.get("payment_status") == "Unpaid"
                    and self.order.get("order_status") == "Pending Payment")

    def _update_action_states(self) -> None:
        editable = self._is_editable_order()
        edit_state = "normal" if editable else "disabled"
        for button in (self.edit_quantity_button, self.remove_item_button):
            button.configure(state=edit_state)
        cancelable = bool(self.order and self.order.get("order_status") not in ("Completed", "Cancelled"))
        self.cancel_order_button.configure(state="normal" if cancelable else "disabled")
        self.pay_button.configure(state=edit_state)

    def _selected_item_id(self) -> int | None:
        selection = self.items.selection()
        if not selection:
            messagebox.showinfo("Select an item", "Choose an order item first.", parent=self)
            return None
        try:
            return int(selection[0])
        except ValueError:
            return None

    def _admin_credentials(self, action: str) -> tuple[str, str] | None:
        username = simpledialog.askstring("Admin override", f"Admin username to {action}:", parent=self)
        if username is None:
            return None
        password = simpledialog.askstring("Admin override", "Admin password:", show="*", parent=self)
        if password is None:
            return None
        return username.strip(), password

    def _reload_current_order(self) -> None:
        if self.order:
            code = self.order["order_code"]
            self.order = order_model.get_order_by_code(code)
        self._render_order()
        self._refresh_pending_orders()

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
            self._refresh_pending_orders()
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
            self.change_var.set("Change: —")
            self._update_action_states()
            return
        order = self.order
        self.summary_var.set(
            f"Order: {order['order_code']}    Type: {order['order_type']}    "
            f"Created: {order['created_at']}\n"
            f"Payment: {order['payment_status']}    Status: {order['order_status']}"
        )
        for item in order["items"]:
            notes = ", ".join(filter(None, (item.get("customization"), item.get("special_instructions"))))
            self.items.insert("", "end", iid=str(item["order_item_id"]), text=item["product_name"],
                              values=(item["quantity"], notes, php(item["subtotal"])))
        self.total_var.set(f"Total: {php(order['total_amount'])}")
        self.amount_var.set(f"{Decimal(str(order['total_amount'])):.2f}")
        self._update_change_display()
        self._update_action_states()

    def _update_change_display(self) -> None:
        if not getattr(self, "change_var", None):
            return
        if not self.order:
            self.change_var.set("Change: —")
            return
        try:
            tendered = Decimal(self.amount_var.get().strip())
        except (InvalidOperation, AttributeError):
            self.change_var.set("Change: enter tendered amount")
            return
        amount_due = Decimal(str(self.order["total_amount"]))
        if tendered < amount_due:
            self.change_var.set(f"Amount remaining: {php(amount_due - tendered)}")
        elif self.method_var.get() == "Cash":
            self.change_var.set(f"Change: {php(tendered - amount_due)}")
        else:
            self.change_var.set("Change: ₱0.00")

    def change_quantity(self) -> None:
        if not self._is_editable_order():
            return
        item_id = self._selected_item_id()
        if item_id is None:
            return
        item = next((row for row in self.order["items"] if int(row["order_item_id"]) == item_id), None)
        if not item:
            return
        quantity = simpledialog.askinteger(
            "Change quantity", f"New quantity for {item['product_name']}:",
            initialvalue=int(item["quantity"]), minvalue=1, parent=self,
        )
        if quantity is None or quantity == int(item["quantity"]):
            return
        credentials = self._admin_credentials("reduce the quantity") if quantity < int(item["quantity"]) else None
        if quantity < int(item["quantity"]) and credentials is None:
            return
        try:
            options = {}
            if credentials:
                options = {"admin_username": credentials[0], "admin_password": credentials[1]}
            order_model.update_order_item_quantity(
                int(self.order["order_id"]), item_id, quantity, **options,
            )
            self._reload_current_order()
        except Exception as exc:
            show_error(exc, "Could not change item quantity")

    def remove_item(self) -> None:
        if not self._is_editable_order():
            return
        item_id = self._selected_item_id()
        if item_id is None:
            return
        item = next((row for row in self.order["items"] if int(row["order_item_id"]) == item_id), None)
        if not item:
            return
        if not messagebox.askyesno("Remove item", f"Remove {item['product_name']} from this order?", parent=self):
            return
        credentials = self._admin_credentials("remove an order item")
        if credentials is None:
            return
        try:
            order_model.remove_order_item(int(self.order["order_id"]), item_id, *credentials)
            self._reload_current_order()
        except Exception as exc:
            show_error(exc, "Could not remove order item")

    def cancel_current_order(self) -> None:
        if not self.order:
            return
        paid = self.order.get("payment_status") == "Paid"
        prompt = f"Cancel order {self.order['order_code']}?"
        if paid:
            prompt += "\n\nThis will mark the in-app payment cancelled and restore tracked stock. It does not issue a customer refund."
        if not messagebox.askyesno("Cancel order", prompt, parent=self):
            return
        credentials = self._admin_credentials("cancel an order")
        if credentials is None:
            return
        try:
            order_model.cancel_order_as_cashier(self.order["order_code"], *credentials)
            self.order = order_model.get_order_by_code(self.order["order_code"])
            self._render_order()
            self._refresh_pending_orders()
        except Exception as exc:
            show_error(exc, "Could not cancel order")

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
                restaurant_name=getattr(self.winfo_toplevel(), "restaurant_name", "BITEBYTE"),
                tagline=getattr(self.winfo_toplevel(), "brand_tagline", "Crave It. Click It. Bite It."),
                branch=getattr(self.winfo_toplevel(), "restaurant_branch", "Main Branch"),
                address=getattr(self.winfo_toplevel(), "restaurant_address", "Manila, Philippines"),
                contact=getattr(self.winfo_toplevel(), "restaurant_contact", "09123456789"),
            )
            ReceiptModal(self, receipt, on_next=self.clear)
            self._refresh_pending_orders()
        except (InvalidOperation, ValueError) as exc:
            show_error(exc, "Payment was not recorded")
        except Exception as exc:
            show_error(exc, "Payment was not recorded")

    def clear(self) -> None:
        self.order = None
        self.code_var.set("")
        self._render_order()
        self._refresh_pending_orders()

    def open_history(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Transaction History")
        dialog.transient(self.winfo_toplevel())
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
        size_popup(dialog, self, 1120, 660, min_width=760, min_height=500)
