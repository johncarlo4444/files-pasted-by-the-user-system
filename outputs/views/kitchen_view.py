"""Live kitchen kanban board and order status workflow."""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from models import order_model
from views.common import php, show_error
from views.theme import PAGE


class KitchenView(ttk.Frame):
    GROUPS = (
        ("Pending Payment", {"Pending Payment"}, "KdsPending.TLabel"),
        ("Preparing", {"Paid", "Preparing"}, "KdsPreparing.TLabel"),
        ("Ready", {"Ready"}, "KdsReady.TLabel"),
        ("Completed", {"Completed"}, "KdsCompleted.TLabel"),
    )
    NEXT_LABEL = {
        "Paid": "Start Prep",
        "Preparing": "Mark Ready",
        "Ready": "Complete",
    }

    def __init__(self, parent):
        super().__init__(parent, padding=12)
        ttk.Label(self, text="Kitchen Display", style="MenuTitle.TLabel").pack(anchor="w")
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(10, 8))
        ttk.Label(toolbar, text="Find order").pack(side="left")
        self.search_var = tk.StringVar()
        entry = ttk.Entry(toolbar, textvariable=self.search_var, width=28)
        entry.pack(side="left", padx=8)
        entry.bind("<Return>", lambda _event: self.refresh())
        ttk.Button(toolbar, text="Search", command=self.refresh).pack(side="left")
        ttk.Button(toolbar, text="Refresh", command=self.refresh).pack(side="right")

        board_wrap = ttk.Frame(self)
        board_wrap.pack(fill="both", expand=True)
        board_wrap.columnconfigure(0, weight=1)
        board_wrap.rowconfigure(0, weight=1)
        self.board_canvas = tk.Canvas(board_wrap, background=PAGE, highlightthickness=0, borderwidth=0)
        horizontal = ttk.Scrollbar(board_wrap, orient="horizontal", command=self.board_canvas.xview)
        vertical = ttk.Scrollbar(board_wrap, orient="vertical", command=self.board_canvas.yview)
        self.board_canvas.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)
        self.board_canvas.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.board = ttk.Frame(self.board_canvas)
        self.board_window = self.board_canvas.create_window((0, 0), window=self.board, anchor="nw")
        self.board.bind("<Configure>", self._update_board_region)

        self.columns: dict[str, ttk.Frame] = {}
        self.count_vars: dict[str, tk.StringVar] = {}
        self.elapsed_labels: dict[int, tuple[ttk.Label, datetime]] = {}
        for index, (name, _statuses, badge_style) in enumerate(self.GROUPS):
            column = ttk.Frame(self.board, style="KdsColumn.TFrame", padding=8, width=292)
            column.grid(row=0, column=index, sticky="ns", padx=6, pady=6)
            column.grid_propagate(False)
            header = ttk.Frame(column, style="KdsColumn.TFrame")
            header.pack(fill="x", pady=(0, 7))
            ttk.Label(header, text=name, style=badge_style).pack(side="left", padx=3, pady=3)
            count = tk.StringVar(value="0")
            self.count_vars[name] = count
            ttk.Label(header, textvariable=count, style="HeaderBadge.TLabel").pack(side="right")
            cards = ttk.Frame(column, style="KdsColumn.TFrame")
            cards.pack(fill="both", expand=True)
            self.columns[name] = cards

        self._refresh_job = None
        self._clock_job = None
        self.refresh()
        self._schedule_refresh()
        self._update_elapsed_labels()
        self.bind("<Destroy>", self._on_destroy, add="+")

    def _update_board_region(self, _event=None) -> None:
        self.board_canvas.configure(scrollregion=self.board_canvas.bbox("all"))

    def _schedule_refresh(self) -> None:
        if self.winfo_exists():
            self._refresh_job = self.after(5000, self._timed_refresh)

    def _timed_refresh(self) -> None:
        self.refresh()
        self._schedule_refresh()

    def _update_elapsed_labels(self) -> None:
        for label, created_at in list(self.elapsed_labels.values()):
            elapsed = max(0, int((datetime.now() - created_at).total_seconds()))
            minutes, seconds = divmod(elapsed, 60)
            hours, minutes = divmod(minutes, 60)
            label.configure(text=f"Elapsed  {hours:02d}:{minutes:02d}:{seconds:02d}")
        if self.winfo_exists():
            self._clock_job = self.after(1000, self._update_elapsed_labels)

    def _on_destroy(self, event) -> None:
        if event.widget is self:
            for job in (self._refresh_job, self._clock_job):
                if job:
                    try:
                        self.after_cancel(job)
                    except tk.TclError:
                        pass
            self._refresh_job = None
            self._clock_job = None

    @staticmethod
    def _created_datetime(value) -> datetime:
        if isinstance(value, datetime):
            return value.replace(tzinfo=None)
        try:
            return datetime.fromisoformat(str(value)).replace(tzinfo=None)
        except ValueError:
            return datetime.now()

    def refresh(self) -> None:
        try:
            orders = order_model.list_orders(search=self.search_var.get(), limit=500)
            self.elapsed_labels.clear()
            for column in self.columns.values():
                for child in column.winfo_children():
                    child.destroy()

            for group_name, statuses, _badge_style in self.GROUPS:
                group_orders = [order for order in orders if order["order_status"] in statuses]
                self.count_vars[group_name].set(str(len(group_orders)))
                for order in group_orders:
                    self._render_ticket(group_name, order)
                if not group_orders:
                    ttk.Label(
                        self.columns[group_name],
                        text="No orders",
                        style="KdsEmpty.TLabel",
                    ).pack(anchor="center", pady=20)
            self._update_board_region()
        except Exception as exc:
            show_error(exc, "Could not refresh kitchen board")

    def _render_ticket(self, group_name: str, order: dict) -> None:
        card = ttk.Frame(self.columns[group_name], style="KdsCard.TFrame", padding=10)
        card.pack(fill="x", padx=2, pady=5)

        heading = ttk.Frame(card, style="KdsCard.TFrame")
        heading.pack(fill="x")
        ttk.Label(heading, text=order["order_code"], style="KdsCode.TLabel").pack(side="left")
        ttk.Label(heading, text=order["order_type"], style="KdsCard.TLabel").pack(side="right")
        ttk.Label(card, text=php(order["total_amount"]), style="KdsCard.TLabel",
                  font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(3, 5))

        ticket_items = (order.get("ticket_items") or "No item details available").strip()
        ttk.Label(card, text=ticket_items, style="KdsCard.TLabel", wraplength=250,
                  justify="left").pack(anchor="w", pady=(0, 6))
        created_at = self._created_datetime(order["created_at"])
        elapsed = ttk.Label(card, style="KdsCard.TLabel", foreground="#756b68")
        elapsed.pack(anchor="w", pady=(0, 7))
        self.elapsed_labels[int(order["order_id"])] = (elapsed, created_at)

        actions = ttk.Frame(card, style="KdsCard.TFrame")
        actions.pack(fill="x")
        ttk.Button(
            actions,
            text="Details",
            command=lambda code=order["order_code"]: self.show_details(code),
        ).pack(side="left")
        current_status = order["order_status"]
        next_label = self.NEXT_LABEL.get(current_status)
        if next_label:
            ttk.Button(
                actions,
                text=next_label,
                command=lambda order_id=int(order["order_id"]): self.advance(order_id),
            ).pack(side="right")
        elif current_status == "Pending Payment":
            ttk.Button(
                actions,
                text="Cancel",
                command=lambda order_id=int(order["order_id"]), code=order["order_code"]:
                    self.cancel_unpaid(order_id, code),
            ).pack(side="right")

    def show_details(self, order_code: str) -> None:
        try:
            order = order_model.get_order_by_code(order_code)
            if not order:
                raise ValueError("Order was not found.")
            dialog = tk.Toplevel(self)
            dialog.title(f"Order {order['order_code']} Details")
            dialog.transient(self.winfo_toplevel())
            dialog.geometry("560x450")
            panel = ttk.Frame(dialog, padding=18)
            panel.pack(fill="both", expand=True)
            ttk.Label(panel, text=f"Order {order['order_code']}", style="MenuTitle.TLabel").pack(anchor="w")
            ttk.Label(
                panel,
                text=f"{order['order_type']}  |  {order['order_status']}  |  {order['created_at']}",
            ).pack(anchor="w", pady=(4, 10))
            for item in order["items"]:
                ttk.Label(
                    panel,
                    text=f"{item['quantity']} x {item['product_name']}  {php(item['subtotal'])}",
                    font=("Segoe UI", 11, "bold"),
                ).pack(anchor="w", pady=(5, 0))
                for note in (item.get("customization"), item.get("special_instructions")):
                    if note:
                        ttk.Label(panel, text=note, wraplength=500).pack(anchor="w", padx=(18, 0))
            ttk.Label(panel, text=f"Total: {php(order['total_amount'])}",
                      font=("Segoe UI", 13, "bold")).pack(anchor="e", pady=(10, 0))
            ttk.Button(panel, text="Close", command=dialog.destroy).pack(anchor="e", pady=(10, 0))
        except Exception as exc:
            show_error(exc, "Could not load order details")

    def advance(self, order_id: int) -> None:
        try:
            status = order_model.advance_order_status(order_id)
            self.refresh()
            messagebox.showinfo("Order updated", f"Order moved to {status}.", parent=self)
        except Exception as exc:
            show_error(exc, "Could not advance order")

    def cancel_unpaid(self, order_id: int, order_code: str) -> None:
        try:
            order = order_model.get_order_by_code(order_code)
            if not order:
                raise ValueError("Order was not found.")
            if order["payment_status"] != "Unpaid":
                raise ValueError("Only unpaid orders can be cancelled from this control.")
            if not messagebox.askyesno("Cancel unpaid order", f"Cancel order {order['order_code']}?", parent=self):
                return
            order_model.cancel_order(order["order_code"])
            self.refresh()
        except Exception as exc:
            show_error(exc, "Could not cancel order")
