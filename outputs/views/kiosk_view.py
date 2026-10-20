"""Customer-facing self-service kiosk screen."""

from __future__ import annotations

import itertools
import re
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from models import order_model, product_model
from views.common import php, show_error
from views.theme import PAGE


class KioskView(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=12)
        self._cart_ids = itertools.count(1)
        self.cart: dict[int, dict] = {}
        self.products: list[dict] = []
        self.categories: list[dict] = []
        self.order_type: str | None = None
        self._search_job = None
        self._photo_refs = []
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_welcome()

    def _build_welcome(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        self.order_type = None
        self.cart.clear()
        panel = ttk.Frame(self, padding=40, style="Welcome.TFrame")
        panel.grid(row=0, column=0, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        ttk.Label(panel, text="\U0001F354     \U0001F35F     \U0001F355", style="WelcomeFood.TLabel").grid(
            row=0, column=0, pady=(55, 14)
        )
        ttk.Label(panel, text="WORLD FAST FOOD EXPRESS", style="WelcomeBrand.TLabel").grid(
            row=1, column=0, pady=(0, 10)
        )
        ttk.Label(panel, text="Famous favorites, made fresh.", style="WelcomeText.TLabel").grid(
            row=2, column=0, pady=(0, 28)
        )
        ttk.Button(panel, text="TOUCH TO START ORDER", style="Gold.TButton",
                   command=self._choose_order_type).grid(
            row=3, column=0, ipadx=25, ipady=7
        )

    def _choose_order_type(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Choose Order Type")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.resizable(False, False)
        box = ttk.Frame(dialog, padding=24)
        box.pack(fill="both", expand=True)
        ttk.Label(box, text="How would you like your order?", font=("Segoe UI", 15, "bold")).pack(pady=(0, 18))

        def choose(value: str) -> None:
            self.order_type = value
            dialog.destroy()
            self._build_ordering()

        ttk.Button(box, text="Dine-In", command=lambda: choose("Dine-In")).pack(fill="x", pady=5, ipady=8)
        ttk.Button(box, text="Take-Out", command=lambda: choose("Take-Out")).pack(fill="x", pady=5, ipady=8)
        ttk.Button(box, text="Cancel", command=dialog.destroy).pack(anchor="e", pady=(12, 0))

    def _build_ordering(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        self.columnconfigure(0, weight=4)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(1, weight=0)
        self.rowconfigure(2, weight=0)

        top = ttk.Frame(self)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        ttk.Label(top, text=f"{self.order_type} Order", style="MenuTitle.TLabel").pack(side="left")
        ttk.Button(top, text="Start Over", command=self._confirm_reset).pack(side="right")
        search_row = ttk.Frame(self)
        search_row.grid(row=1, column=0, sticky="ew", padx=(0, 12))
        ttk.Label(search_row, text="Search menu").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_row, textvariable=self.search_var, width=28)
        self.search_entry.pack(side="left", padx=(8, 15))
        self.search_var.trace_add("write", self._search_changed)
        self.category_var = tk.StringVar(value="All categories")
        category_shell = ttk.Frame(self)
        category_shell.grid(row=2, column=0, sticky="ew", padx=(0, 12), pady=(4, 2))
        category_shell.columnconfigure(0, weight=1)
        self.category_canvas = tk.Canvas(category_shell, height=42, highlightthickness=0,
                                         background=PAGE, borderwidth=0)
        self.category_canvas.grid(row=0, column=0, sticky="ew")
        category_scroll = ttk.Scrollbar(category_shell, orient="horizontal", command=self.category_canvas.xview)
        category_scroll.grid(row=1, column=0, sticky="ew")
        self.category_canvas.configure(xscrollcommand=category_scroll.set)
        self.category_buttons = ttk.Frame(self.category_canvas)
        self.category_window = self.category_canvas.create_window(
            (0, 0), window=self.category_buttons, anchor="nw"
        )
        self.category_buttons.bind(
            "<Configure>", lambda _event: self.category_canvas.configure(
                scrollregion=self.category_canvas.bbox("all")
            )
        )
        self.category_canvas.bind(
            "<Shift-MouseWheel>",
            lambda event: self.category_canvas.xview_scroll(-1 if event.delta > 0 else 1, "units"),
        )

        body = ttk.Panedwindow(self, orient="horizontal")
        body.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(6, 0))
        self.rowconfigure(3, weight=1)
        menu_panel = ttk.Frame(body, padding=(0, 0, 10, 0))
        cart_panel = ttk.Frame(body, padding=12, relief="groove")
        body.add(menu_panel, weight=3)
        body.add(cart_panel, weight=2)

        self.menu_canvas = tk.Canvas(menu_panel, highlightthickness=0, background=PAGE, borderwidth=0)
        menu_scroll = ttk.Scrollbar(menu_panel, orient="vertical", command=self.menu_canvas.yview)
        self.cards_frame = ttk.Frame(self.menu_canvas)
        self.cards_frame.bind(
            "<Configure>", lambda _event: self.menu_canvas.configure(scrollregion=self.menu_canvas.bbox("all"))
        )
        self.menu_window = self.menu_canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")
        self.menu_canvas.configure(yscrollcommand=menu_scroll.set)
        self.menu_canvas.bind("<Configure>", self._resize_menu_content)
        self.menu_canvas.pack(side="left", fill="both", expand=True)
        menu_scroll.pack(side="right", fill="y")

        cart_panel.columnconfigure(0, weight=1)
        cart_panel.rowconfigure(1, weight=1)
        self.cart_count_var = tk.StringVar(value="Your Cart - 0 items")
        ttk.Label(cart_panel, textvariable=self.cart_count_var, style="MenuTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.cart_tree = ttk.Treeview(cart_panel, columns=("qty", "amount"), show="tree headings", height=7)
        self.cart_tree.heading("#0", text="Item")
        self.cart_tree.heading("qty", text="Qty")
        self.cart_tree.heading("amount", text="Subtotal")
        self.cart_tree.column("#0", width=140, minwidth=100, stretch=True)
        self.cart_tree.column("qty", width=42, minwidth=38, stretch=False, anchor="center")
        self.cart_tree.column("amount", width=92, minwidth=82, stretch=False, anchor="e")
        self.cart_tree.grid(row=1, column=0, sticky="nsew", pady=(10, 8))
        controls = ttk.Frame(cart_panel)
        controls.grid(row=2, column=0, sticky="ew")
        ttk.Button(controls, text="−", width=4, command=lambda: self._change_quantity(-1)).pack(side="left")
        ttk.Button(controls, text="+", width=4, command=lambda: self._change_quantity(1)).pack(side="left", padx=4)
        ttk.Button(controls, text="Delete", command=self._delete_selected).pack(side="left", padx=4)
        self.total_var = tk.StringVar(value=php(0))
        total_row = ttk.Frame(cart_panel)
        total_row.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(total_row, text="TOTAL", font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Label(total_row, textvariable=self.total_var, style="MetricValue.TLabel").pack(side="right")
        ttk.Button(cart_panel, text="Review & Place Order", command=self._preview_order).grid(
            row=4, column=0, sticky="ew", pady=(10, 0), ipady=4
        )

        self._load_categories()
        self._load_products()

    def _resize_menu_content(self, event) -> None:
        self.menu_canvas.itemconfigure(self.menu_window, width=event.width)

    def _load_categories(self) -> None:
        try:
            self.categories = product_model.list_categories()
            for child in self.category_buttons.winfo_children():
                child.destroy()
            labels = [("All categories", "All")]
            labels.extend((item["category_name"], item["category_name"]) for item in self.categories)
            for label, visible in labels:
                selected = self.category_var.get() == label
                ttk.Button(
                    self.category_buttons,
                    text=visible,
                    style="CategorySelected.TButton" if selected else "CategoryPill.TButton",
                    command=lambda value=label: self._choose_category(value),
                ).pack(side="left", padx=(0, 7), pady=2)
            self.category_canvas.configure(scrollregion=self.category_canvas.bbox("all"))
        except Exception as exc:
            show_error(exc, "Could not load categories")

    def _choose_category(self, label: str) -> None:
        self.category_var.set(label)
        self._load_categories()
        self._load_products()

    def _selected_category_id(self) -> int | None:
        label = self.category_var.get()
        for category in self.categories:
            if category["category_name"] == label:
                return int(category["category_id"])
        return None

    def _search_changed(self, *_args) -> None:
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(250, self._load_products)

    def _load_products(self) -> None:
        if not self.winfo_exists() or not hasattr(self, "cards_frame"):
            return
        try:
            self.products = product_model.list_products(self.search_var.get(), self._selected_category_id())
            self._render_products()
        except Exception as exc:
            show_error(exc, "Could not load menu")

    def _render_products(self) -> None:
        for child in self.cards_frame.winfo_children():
            child.destroy()
        self._photo_refs = []
        if not self.products:
            ttk.Label(self.cards_frame, text="No menu items match your search.").grid(padx=20, pady=30)
            return
        for column in range(3):
            self.cards_frame.columnconfigure(column, weight=1, uniform="menu-card")
        for index, product in enumerate(self.products):
            row, column = divmod(index, 3)
            card = ttk.Frame(self.cards_frame, padding=10, style="MenuCard.TFrame")
            card.grid(row=row, column=column, sticky="nsew", padx=6, pady=6)
            photo = self._product_photo(product.get("image_path"), product["product_name"])
            if photo:
                image_label = ttk.Label(card, image=photo, style="MenuCard.TLabel")
                image_label.pack(pady=(0, 6))
                self._photo_refs.append(photo)
            else:
                ttk.Label(card, text="🍽", font=("Segoe UI Emoji", 26)).pack(pady=(0, 3))
            ttk.Label(card, text=product["product_name"], style="MenuCard.TLabel",
                      font=("Segoe UI", 11, "bold"),
                      wraplength=210, justify="center").pack(fill="x")
            ttk.Label(card, text=product["category_name"], style="MenuCardCategory.TLabel").pack()
            ttk.Label(card, text=product["description"] or "", style="MenuCard.TLabel", wraplength=210,
                      justify="center").pack(fill="x", pady=(4, 2))
            ttk.Label(card, text=php(product["price"]), style="MenuCardPrice.TLabel").pack(pady=3)
            if product["can_order"]:
                ttk.Button(card, text="+ Customize & Add", command=lambda p=product: self._customize(p)).pack(
                    fill="x", pady=(3, 0)
                )
            else:
                ttk.Label(card, text="Out of Stock", foreground="#a32020").pack(pady=(3, 0))

    def _product_photo(self, path: str | None, product_name: str):
        try:
            from PIL import Image, ImageOps, ImageTk
            app_root = Path(__file__).resolve().parents[1]
            candidates = []
            if path:
                stored_path = Path(path).expanduser()
                if stored_path.is_absolute():
                    candidates.append(stored_path)
                else:
                    candidates.append(app_root / stored_path)
                    candidates.append(stored_path)
            slug = re.sub(r"[^a-z0-9]+", "-", product_name.casefold()).strip("-")
            menu_assets = app_root / "assets" / "menu"
            candidates.extend(
                menu_assets / f"{slug}{suffix}"
                for suffix in (".png", ".jpg", ".jpeg", ".webp")
            )
            for candidate in candidates:
                try:
                    with Image.open(candidate) as source:
                        image = ImageOps.fit(
                            source.convert("RGB"), (220, 130), method=Image.LANCZOS
                        )
                    return ImageTk.PhotoImage(image)
                except OSError:
                    continue
        except ImportError:
            return None
        return None

    def _customize(self, product: dict) -> None:
        dialog = tk.Toplevel(self)
        dialog.title(f"Customize {product['product_name']}")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.resizable(False, False)
        panel = ttk.Frame(dialog, padding=18)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text=product["product_name"], font=("Segoe UI", 15, "bold")).pack(anchor="w")
        size_var = tk.StringVar(value="Regular")
        ttk.Label(panel, text="Size").pack(anchor="w", pady=(12, 2))
        ttk.Radiobutton(panel, text="Regular", value="Regular", variable=size_var).pack(anchor="w")
        ttk.Radiobutton(panel, text="Large (+₱60.00)", value="Large", variable=size_var).pack(anchor="w")
        ttk.Label(panel, text="Extras").pack(anchor="w", pady=(12, 2))
        extras = {
            "Extra cheese (+₱30.00)": ("Extra cheese", 30),
            "Extra gravy (+₱20.00)": ("Extra gravy", 20),
            "Bacon (+₱45.00)": ("Bacon", 45),
        }
        extra_vars = {label: tk.BooleanVar(value=False) for label in extras}
        for label, variable in extra_vars.items():
            ttk.Checkbutton(panel, text=label, variable=variable).pack(anchor="w")
        ttk.Label(panel, text="Remove ingredients or add a preference").pack(anchor="w", pady=(12, 2))
        exclusions = ttk.Entry(panel, width=42)
        exclusions.insert(0, "e.g. no onions, extra spicy")
        exclusions.pack(fill="x")
        ttk.Label(panel, text="Special instructions").pack(anchor="w", pady=(10, 2))
        instructions = ttk.Entry(panel, width=42)
        instructions.pack(fill="x")

        def add_item() -> None:
            adjustment = 60 if size_var.get() == "Large" else 0
            chosen = []
            if size_var.get() == "Large":
                chosen.append("Large")
            for label, variable in extra_vars.items():
                if variable.get():
                    name, price = extras[label]
                    adjustment += price
                    chosen.append(name)
            if exclusions.get().strip() and not exclusions.get().startswith("e.g."):
                chosen.append(exclusions.get().strip())
            custom = ", ".join(chosen) if chosen else "Regular"
            cart_id = next(self._cart_ids)
            self.cart[cart_id] = {
                "product_id": int(product["product_id"]),
                "name": product["product_name"],
                "quantity": 1,
                "unit_price": product["price"],
                "unit_adjustment": adjustment,
                "customization": custom,
                "special_instructions": instructions.get().strip(),
            }
            dialog.destroy()
            self._render_cart()

        buttons = ttk.Frame(panel)
        buttons.pack(fill="x", pady=(16, 0))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left")
        ttk.Button(buttons, text="Add to Cart", command=add_item).pack(side="right")

    def _line_total(self, line: dict):
        return (line["unit_price"] + line["unit_adjustment"]) * line["quantity"]

    def _render_cart(self) -> None:
        for iid in self.cart_tree.get_children():
            self.cart_tree.delete(iid)
        total = 0
        item_count = 0
        for cart_id, line in self.cart.items():
            amount = self._line_total(line)
            total += amount
            item_count += line["quantity"]
            display_name = line["name"]
            if line["customization"]:
                display_name += f" — {line['customization']}"
            self.cart_tree.insert("", "end", iid=str(cart_id), text=display_name,
                                  values=(line["quantity"], php(amount)))
        self.total_var.set(php(total))
        self.cart_count_var.set(f"Your Cart - {item_count} item" + ("s" if item_count != 1 else ""))

    def _change_quantity(self, change: int) -> None:
        selected = self.cart_tree.selection()
        if not selected:
            return
        cart_id = int(selected[0])
        self.cart[cart_id]["quantity"] += change
        if self.cart[cart_id]["quantity"] < 1:
            del self.cart[cart_id]
        self._render_cart()

    def _delete_selected(self) -> None:
        selected = self.cart_tree.selection()
        if selected:
            self.cart.pop(int(selected[0]), None)
            self._render_cart()

    def _preview_order(self) -> None:
        if not self.cart:
            messagebox.showinfo("Your cart is empty", "Add an item to your cart first.")
            return
        total = sum((self._line_total(line) for line in self.cart.values()), 0)
        lines = [f"{line['quantity']} × {line['name']} — {line['customization']} {php(self._line_total(line))}"
                 for line in self.cart.values()]
        summary = (
            f"Order type: {self.order_type}\n\n" + "\n".join(lines) +
            f"\n\nSubtotal: {php(total)}\nVAT/Taxes: {php(0)}\nTotal: {php(total)}"
        )
        if not messagebox.askyesno("Review Order", f"{summary}\n\nPlace this order?", parent=self):
            return
        payload = [
            {key: line[key] for key in ("product_id", "quantity", "unit_adjustment", "customization", "special_instructions")}
            for line in self.cart.values()
        ]
        try:
            order = order_model.create_order(self.order_type or "Take-Out", payload)
            self._show_order_slip(order)
        except Exception as exc:
            show_error(exc, "Could not place order")

    def _show_order_slip(self, order: dict) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Order Slip")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        panel = ttk.Frame(dialog, padding=22)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text="WORLD FAST FOOD EXPRESS", font=("Consolas", 15, "bold")).pack()
        ttk.Label(panel, text="DIGITAL ORDER SLIP", font=("Consolas", 11)).pack(pady=(2, 10))
        ttk.Separator(panel).pack(fill="x", pady=5)
        ttk.Label(panel, text=f"Order Code: {order['order_code']}", font=("Consolas", 14, "bold")).pack(anchor="w")
        ttk.Label(panel, text=f"Time: {datetime.now():%Y-%m-%d %H:%M:%S}").pack(anchor="w")
        ttk.Label(panel, text=f"Type: {self.order_type}").pack(anchor="w")
        ttk.Label(panel, text="Status: Pending Payment").pack(anchor="w")
        ttk.Label(panel, text=f"Total: {php(order['total_amount'])}").pack(anchor="w")
        ttk.Separator(panel).pack(fill="x", pady=8)
        ttk.Label(panel, text="Please pay at the cashier to begin preparation.\nKeep your order code for pickup.",
                  justify="left").pack(anchor="w")

        def cancel_order() -> None:
            if messagebox.askyesno("Cancel order", "Cancel this unpaid order?", parent=dialog):
                try:
                    order_model.cancel_order(order["order_code"])
                    dialog.destroy()
                    self._build_welcome()
                except Exception as exc:
                    show_error(exc, "Could not cancel order")

        buttons = ttk.Frame(panel)
        buttons.pack(fill="x", pady=(16, 0))
        ttk.Button(buttons, text="Cancel Order", command=cancel_order).pack(side="left")
        ttk.Button(buttons, text="Done", command=lambda: (dialog.destroy(), self._build_welcome())).pack(side="right")

    def _confirm_reset(self) -> None:
        if not self.cart or messagebox.askyesno("Start over", "Clear your cart and start over?", parent=self):
            self._build_welcome()
