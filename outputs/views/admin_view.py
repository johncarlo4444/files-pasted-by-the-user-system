"""Admin dashboard, menu, inventory, users, and sales reports."""

from __future__ import annotations

import shutil
import tkinter as tk
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from models import inventory_model, product_model, report_model, settings_model, user_model
from views.common import php, show_error, size_popup


class AdminView(ttk.Frame):
    def __init__(self, parent, admin: dict):
        super().__init__(parent, padding=12)
        self.admin = admin
        ttk.Label(self, text="Admin Management", style="MenuTitle.TLabel").pack(anchor="w")
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, pady=(10, 0))
        self.tabs.add(DashboardTab(self.tabs), text="Dashboard")
        self.tabs.add(ProductsTab(self.tabs), text="Products & Categories")
        self.tabs.add(InventoryTab(self.tabs), text="Inventory")
        self.tabs.add(StaffTab(self.tabs), text="Staff Users")
        self.tabs.add(BrandingTab(self.tabs), text="Branding")
        self.tabs.add(ReportsTab(self.tabs), text="Sales Reports")


class DashboardTab(ttk.Frame):
    LABELS = (
        ("total_orders", "Orders Today"), ("pending", "Pending"),
        ("preparing", "Paid / Preparing"), ("ready", "Ready"),
        ("completed", "Completed"), ("cancelled", "Cancelled"),
    )

    def __init__(self, parent):
        super().__init__(parent, padding=14)
        self.metric_vars: dict[str, tk.StringVar] = {}
        for index, (key, label) in enumerate(self.LABELS):
            card = ttk.Frame(self, style="MetricCard.TFrame", padding=14)
            card.grid(row=index // 3, column=index % 3, sticky="nsew", padx=6, pady=6)
            ttk.Label(card, text=label, style="MetricTitle.TLabel").pack(anchor="w")
            value = tk.StringVar(value="—")
            self.metric_vars[key] = value
            value_style = {
                "pending": "MetricPending.TLabel",
                "preparing": "MetricPreparing.TLabel",
                "ready": "MetricReady.TLabel",
                "cancelled": "MetricCancelled.TLabel",
            }.get(key, "MetricValue.TLabel")
            ttk.Label(card, textvariable=value, style=value_style).pack(anchor="w", pady=(5, 0))
            self.columnconfigure(index % 3, weight=1)
        sales_card = ttk.Frame(self, style="MetricCard.TFrame", padding=16)
        sales_card.grid(row=2, column=0, columnspan=3, sticky="ew", padx=6, pady=6)
        ttk.Label(sales_card, text="Daily Sales", style="MetricTitle.TLabel").pack(anchor="w")
        self.sales_var = tk.StringVar(value=php(0))
        ttk.Label(sales_card, textvariable=self.sales_var, style="MetricValue.TLabel").pack(anchor="w")
        ttk.Button(self, text="Refresh Now", command=self.refresh).grid(row=3, column=2, sticky="e", padx=6, pady=8)
        self.refresh()
        self._job = self.after(10000, self._auto_refresh)
        self.bind("<Destroy>", self._on_destroy, add="+")

    def refresh(self) -> None:
        try:
            data = report_model.dashboard_metrics()
            for key, _label in self.LABELS:
                self.metric_vars[key].set(str(data.get(key) or 0))
            self.sales_var.set(php(data.get("sales", 0)))
        except Exception as exc:
            show_error(exc, "Could not refresh dashboard")

    def _auto_refresh(self) -> None:
        self.refresh()
        if self.winfo_exists():
            self._job = self.after(10000, self._auto_refresh)

    def _on_destroy(self, event) -> None:
        if event.widget is self and getattr(self, "_job", None):
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass


class ProductsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=10)
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 8))
        self.search_var = tk.StringVar()
        search = ttk.Entry(toolbar, textvariable=self.search_var, width=30)
        search.pack(side="left")
        search.bind("<Return>", lambda _event: self.refresh())
        ttk.Button(toolbar, text="Search", command=self.refresh).pack(side="left", padx=5)
        for label, command in (("Add Product", self.add), ("Edit", self.edit),
                               ("Toggle Availability", self.toggle_availability),
                               ("Delete", self.delete), ("Categories", self.manage_categories)):
            ttk.Button(toolbar, text=label, command=command).pack(side="left", padx=3)
        self.tree = ttk.Treeview(self, columns=("category", "price", "available"), show="tree headings")
        for column, label in (("#0", "Product"), ("category", "Category"), ("price", "Price (PHP)"),
                              ("available", "Availability")):
            self.tree.heading(column, text=label)
        self.tree.column("#0", width=300)
        self.tree.column("category", width=230)
        self.tree.column("price", width=120, anchor="e")
        self.tree.column("available", width=130)
        self.tree.pack(fill="both", expand=True)
        self.products: dict[int, dict] = {}
        self.refresh()

    def refresh(self) -> None:
        try:
            self.products = {int(row["product_id"]): row for row in product_model.list_products(self.search_var.get())}
            for iid in self.tree.get_children():
                self.tree.delete(iid)
            for product_id, row in self.products.items():
                available = "Available" if row["can_order"] else "Out of Stock / Disabled"
                self.tree.insert("", "end", iid=str(product_id), text=row["product_name"],
                                 values=(row["category_name"], php(row["price"]), available))
        except Exception as exc:
            show_error(exc, "Could not load products")

    def _selected(self) -> dict | None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Select a product", "Choose a product first.")
            return None
        return self.products[int(selection[0])]

    def add(self) -> None:
        self._product_form()

    def edit(self) -> None:
        product = self._selected()
        if product:
            self._product_form(product)

    def _product_form(self, product: dict | None = None) -> None:
        try:
            categories = product_model.list_categories()
        except Exception as exc:
            show_error(exc, "Could not load categories")
            return
        if not categories:
            messagebox.showinfo("Create a category", "Add a menu category before adding products.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Edit Product" if product else "Add Product")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        panel = ttk.Frame(dialog, padding=18)
        panel.pack(fill="both", expand=True)
        fields = [
            ("Product name", product.get("product_name", "") if product else ""),
            ("Price (PHP)", str(product.get("price", "")) if product else ""),
            ("Description", product.get("description", "") if product else ""),
        ]
        entries = {}
        for row, (label, value) in enumerate(fields):
            ttk.Label(panel, text=label).grid(row=row, column=0, sticky="w", pady=5)
            entry = ttk.Entry(panel, width=42)
            entry.insert(0, value)
            entry.grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=5)
            entries[label] = entry
        ttk.Label(panel, text="Category").grid(row=3, column=0, sticky="w", pady=5)
        category_names = [item["category_name"] for item in categories]
        category_var = tk.StringVar(value=(product["category_name"] if product else category_names[0]))
        category_box = ttk.Combobox(panel, textvariable=category_var, values=category_names, state="readonly", width=39)
        category_box.grid(row=3, column=1, sticky="ew", padx=(12, 0), pady=5)
        image_path = tk.StringVar(value=(product.get("image_path") or "") if product else "")
        ttk.Label(panel, text="Food photo").grid(row=4, column=0, sticky="w", pady=5)
        image_box = ttk.Frame(panel)
        image_box.grid(row=4, column=1, sticky="ew", padx=(12, 0), pady=5)
        ttk.Entry(image_box, textvariable=image_path, width=30).pack(side="left", fill="x", expand=True)

        def choose_image() -> None:
            path = filedialog.askopenfilename(
                parent=dialog, title="Choose product photo",
                filetypes=(("Images", "*.png *.jpg *.jpeg *.gif *.bmp"), ("All files", "*.*")),
            )
            if path:
                image_path.set(path)

        ttk.Button(image_box, text="Browse", command=choose_image).pack(side="left", padx=(5, 0))
        panel.columnconfigure(1, weight=1)

        def save() -> None:
            try:
                name = entries["Product name"].get().strip()
                price = Decimal(entries["Price (PHP)"].get().strip())
                description = entries["Description"].get().strip()
                selected_category = next(item for item in categories if item["category_name"] == category_var.get())
                selected_path = image_path.get().strip() or None
                if selected_path:
                    app_root = Path(__file__).resolve().parents[1]
                    source = Path(selected_path).expanduser()
                    if not source.is_absolute():
                        source = app_root / source
                    if not source.is_file():
                        raise ValueError("The selected photo cannot be found. Choose the image again.")
                    assets = app_root / "assets" / "menu"
                    assets.mkdir(parents=True, exist_ok=True)
                    try:
                        source.resolve().relative_to(assets.resolve())
                    except ValueError:
                        destination = assets / f"{uuid.uuid4().hex[:8]}_{source.name}"
                        shutil.copy2(source, destination)
                        source = destination
                    selected_path = source.resolve().relative_to(app_root).as_posix()
                product_model.save_product(
                    name, int(selected_category["category_id"]), price, description, selected_path,
                    int(product["product_id"]) if product else None,
                )
                dialog.destroy()
                self.refresh()
            except Exception as exc:
                show_error(exc, "Could not save product")

        buttons = ttk.Frame(panel)
        buttons.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left")
        ttk.Button(buttons, text="Save Product", command=save).pack(side="right")
        size_popup(dialog, self, 720, 560, min_width=620, min_height=480)

    def toggle_availability(self) -> None:
        product = self._selected()
        if not product:
            return
        try:
            product_model.set_product_availability(int(product["product_id"]), not bool(product["is_available"]))
            self.refresh()
        except Exception as exc:
            show_error(exc, "Could not update availability")

    def delete(self) -> None:
        product = self._selected()
        if not product:
            return
        if messagebox.askyesno("Delete product", f"Delete {product['product_name']}?", parent=self):
            try:
                product_model.delete_product(int(product["product_id"]))
                self.refresh()
            except Exception as exc:
                show_error(exc, "Could not delete product")

    def manage_categories(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Menu Categories")
        dialog.transient(self.winfo_toplevel())
        panel = ttk.Frame(dialog, padding=12)
        panel.pack(fill="both", expand=True)
        tree = ttk.Treeview(panel, columns=("id",), show="tree headings", height=10)
        tree.heading("#0", text="Category")
        tree.heading("id", text="ID")
        tree.column("#0", width=280)
        tree.column("id", width=70, anchor="center")
        tree.pack(fill="both", expand=True)
        rows: dict[int, dict] = {}

        def refresh_categories() -> None:
            try:
                rows.clear()
                rows.update({int(item["category_id"]): item for item in product_model.list_categories()})
                for iid in tree.get_children():
                    tree.delete(iid)
                for category_id, item in rows.items():
                    tree.insert("", "end", iid=str(category_id), text=item["category_name"], values=(category_id,))
            except Exception as exc:
                show_error(exc, "Could not load categories")

        def selected_category() -> dict | None:
            selected = tree.selection()
            return rows.get(int(selected[0])) if selected else None

        buttons = ttk.Frame(panel)
        buttons.pack(fill="x", pady=(8, 0))

        def add_category() -> None:
            name = simpledialog.askstring("New category", "Category name:", parent=dialog)
            if name:
                try:
                    product_model.save_category(name)
                    refresh_categories()
                    self.refresh()
                except Exception as exc:
                    show_error(exc, "Could not add category")

        def edit_category() -> None:
            item = selected_category()
            if not item:
                messagebox.showinfo("Select a category", "Choose a category first.", parent=dialog)
                return
            name = simpledialog.askstring("Edit category", "Category name:", initialvalue=item["category_name"], parent=dialog)
            if name:
                try:
                    product_model.save_category(name, int(item["category_id"]))
                    refresh_categories()
                    self.refresh()
                except Exception as exc:
                    show_error(exc, "Could not update category")

        def remove_category() -> None:
            item = selected_category()
            if not item:
                messagebox.showinfo("Select a category", "Choose a category first.", parent=dialog)
                return
            if messagebox.askyesno("Delete category", "This also deletes its products. Continue?", parent=dialog):
                try:
                    product_model.delete_category(int(item["category_id"]))
                    refresh_categories()
                    self.refresh()
                except Exception as exc:
                    show_error(exc, "Could not delete category")

        for label, action in (("Add", add_category), ("Edit", edit_category), ("Delete", remove_category)):
            ttk.Button(buttons, text=label, command=action).pack(side="left", padx=(0, 5))
        ttk.Button(buttons, text="Close", command=dialog.destroy).pack(side="right")
        refresh_categories()
        size_popup(dialog, self, 720, 560, min_width=620, min_height=460)


class InventoryTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=10)
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 8))
        for label, command in (("Add Item", self.add), ("Edit Item", self.edit),
                               ("Restock / Adjust", self.adjust), ("Configure Recipe", self.recipe)):
            ttk.Button(toolbar, text=label, command=command).pack(side="left", padx=(0, 5))
        self.tree = ttk.Treeview(self, columns=("stock", "unit", "minimum", "status"), show="tree headings")
        for column, label in (("#0", "Ingredient"), ("stock", "Stock"), ("unit", "Unit"),
                              ("minimum", "Minimum"), ("status", "Status")):
            self.tree.heading(column, text=label)
        self.tree.column("#0", width=260)
        self.tree.column("stock", width=100, anchor="center")
        self.tree.column("unit", width=100, anchor="center")
        self.tree.column("minimum", width=100, anchor="center")
        self.tree.column("status", width=140)
        self.tree.tag_configure("low", background="#fff0c2")
        self.tree.tag_configure("out", foreground="#a32020")
        self.tree.pack(fill="both", expand=True)
        self.items: dict[int, dict] = {}
        self.refresh()

    def refresh(self) -> None:
        try:
            self.items = {int(row["inventory_id"]): row for row in inventory_model.list_inventory()}
            for iid in self.tree.get_children():
                self.tree.delete(iid)
            for item_id, row in self.items.items():
                tag = "out" if row["status"] == "Out of Stock" else (
                    "low" if row["status"] == "Low Stock" else None
                )
                self.tree.insert("", "end", iid=str(item_id), text=row["item_name"],
                                 values=(row["stock_quantity"], row["unit"], row["min_stock_level"], row["status"]),
                                 tags=(tag,) if tag else ())
        except Exception as exc:
            show_error(exc, "Could not load inventory")

    def _selected(self) -> dict | None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Select an inventory item", "Choose an ingredient first.")
            return None
        return self.items[int(selected[0])]

    def add(self) -> None:
        self._item_form()

    def edit(self) -> None:
        item = self._selected()
        if item:
            self._item_form(item)

    def _item_form(self, item: dict | None = None) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Edit Ingredient" if item else "Add Ingredient")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        panel = ttk.Frame(dialog, padding=16)
        panel.pack(fill="both", expand=True)
        defaults = {
            "Ingredient name": item.get("item_name", "") if item else "",
            "Current stock": str(item.get("stock_quantity", 0)) if item else "0",
            "Unit (pcs, kg, packs, L)": item.get("unit", "pcs") if item else "pcs",
            "Minimum stock": str(item.get("min_stock_level", 10)) if item else "10",
        }
        entries = {}
        for row, (label, value) in enumerate(defaults.items()):
            ttk.Label(panel, text=label).grid(row=row, column=0, sticky="w", pady=4)
            entry = ttk.Entry(panel, width=32)
            entry.insert(0, value)
            entry.grid(row=row, column=1, padx=(10, 0), pady=4)
            entries[label] = entry

        def save() -> None:
            try:
                inventory_model.save_inventory_item(
                    entries["Ingredient name"].get(),
                    int(entries["Current stock"].get()),
                    entries["Unit (pcs, kg, packs, L)"].get(),
                    int(entries["Minimum stock"].get()),
                    int(item["inventory_id"]) if item else None,
                )
                dialog.destroy()
                self.refresh()
            except Exception as exc:
                show_error(exc, "Could not save inventory item")

        buttons = ttk.Frame(panel)
        buttons.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left")
        ttk.Button(buttons, text="Save", command=save).pack(side="right")
        size_popup(dialog, self, 660, 500, min_width=560, min_height=440)

    def adjust(self) -> None:
        item = self._selected()
        if not item:
            return
        amount = simpledialog.askinteger(
            "Restock / Adjust", "Enter a positive quantity to restock or negative to remove:", parent=self,
        )
        if amount is None:
            return
        try:
            inventory_model.adjust_stock(int(item["inventory_id"]), amount)
            self.refresh()
        except Exception as exc:
            show_error(exc, "Could not adjust stock")

    def recipe(self) -> None:
        try:
            products = product_model.list_products()
            ingredients = inventory_model.list_inventory()
        except Exception as exc:
            show_error(exc, "Could not load recipe data")
            return
        if not products or not ingredients:
            messagebox.showinfo("Recipe data required", "Add menu products and inventory items first.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Configure Product Recipe")
        dialog.transient(self.winfo_toplevel())
        panel = ttk.Frame(dialog, padding=14)
        panel.pack(fill="both", expand=True)
        product_names = [row["product_name"] for row in products]
        product_by_name = {row["product_name"]: row for row in products}
        product_var = tk.StringVar(value=product_names[0])
        ttk.Label(panel, text="Menu item").pack(anchor="w")
        product_box = ttk.Combobox(panel, textvariable=product_var, values=product_names, state="readonly")
        product_box.pack(fill="x", pady=(2, 10))
        ttk.Label(panel, text="Required stock quantity for one menu item (leave blank if unused)").pack(anchor="w")
        rows = ttk.Frame(panel)
        rows.pack(fill="both", expand=True, pady=(8, 0))
        quantity_vars: dict[int, tk.StringVar] = {}
        for index, ingredient in enumerate(ingredients):
            ttk.Label(rows, text=f"{ingredient['item_name']} ({ingredient['unit']})").grid(
                row=index, column=0, sticky="w", pady=3
            )
            value = tk.StringVar()
            ttk.Entry(rows, textvariable=value, width=8).grid(row=index, column=1, padx=8)
            quantity_vars[int(ingredient["inventory_id"])] = value

        def load_recipe(_event=None) -> None:
            try:
                product = product_by_name[product_var.get()]
                existing = inventory_model.get_product_recipe(int(product["product_id"]))
                for ingredient_id, variable in quantity_vars.items():
                    variable.set(str(existing[ingredient_id]) if ingredient_id in existing else "")
            except Exception as exc:
                show_error(exc, "Could not load recipe")

        product_box.bind("<<ComboboxSelected>>", load_recipe)
        load_recipe()

        def save_recipe() -> None:
            try:
                quantities = {}
                for ingredient_id, variable in quantity_vars.items():
                    value = variable.get().strip()
                    if value:
                        quantities[ingredient_id] = int(value)
                product = product_by_name[product_var.get()]
                inventory_model.set_product_recipe(int(product["product_id"]), quantities)
                dialog.destroy()
            except Exception as exc:
                show_error(exc, "Could not save recipe")

        buttons = ttk.Frame(panel)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Save Recipe", command=save_recipe).pack(side="right")
        ttk.Button(buttons, text="Close", command=dialog.destroy).pack(side="left")
        size_popup(dialog, self, 820, 720, min_width=680, min_height=560)


class StaffTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=10)
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="Add Staff", command=self.add).pack(side="left", padx=(0, 5))
        ttk.Button(toolbar, text="Edit", command=self.edit).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Deactivate", command=self.deactivate).pack(side="left", padx=5)
        self.tree = ttk.Treeview(self, columns=("role", "active", "created"), show="tree headings")
        for column, label in (("#0", "Username"), ("role", "Role"), ("active", "Active"), ("created", "Created")):
            self.tree.heading(column, text=label)
        self.tree.column("#0", width=200)
        self.tree.column("role", width=180)
        self.tree.column("active", width=90, anchor="center")
        self.tree.column("created", width=200)
        self.tree.pack(fill="both", expand=True)
        self.users: dict[int, dict] = {}
        self.refresh()

    def refresh(self) -> None:
        try:
            self.users = {int(row["user_id"]): row for row in user_model.list_users()}
            for iid in self.tree.get_children():
                self.tree.delete(iid)
            for user_id, row in self.users.items():
                self.tree.insert("", "end", iid=str(user_id), text=row["username"],
                                 values=(row["role"], "Yes" if row["is_active"] else "No", row["created_at"]))
        except Exception as exc:
            show_error(exc, "Could not load staff users")

    def _selected(self) -> dict | None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Select a staff account", "Choose a staff account first.")
            return None
        return self.users[int(selected[0])]

    def add(self) -> None:
        self._user_form()

    def edit(self) -> None:
        user = self._selected()
        if user:
            self._user_form(user)

    def _user_form(self, user: dict | None = None) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Edit Staff Account" if user else "Add Staff Account")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        panel = ttk.Frame(dialog, padding=18)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text="Username").grid(row=0, column=0, sticky="w", pady=5)
        username_var = tk.StringVar(value=user["username"] if user else "")
        ttk.Entry(panel, textvariable=username_var, width=30).grid(row=0, column=1, padx=(12, 0), pady=5)
        ttk.Label(panel, text="Role").grid(row=1, column=0, sticky="w", pady=5)
        role_var = tk.StringVar(value=user["role"] if user else "Cashier")
        ttk.Combobox(panel, textvariable=role_var, values=user_model.VALID_ROLES, state="readonly", width=27).grid(
            row=1, column=1, padx=(12, 0), pady=5
        )
        ttk.Label(panel, text="Password" if not user else "New password (optional)").grid(
            row=2, column=0, sticky="w", pady=5
        )
        password_var = tk.StringVar()
        ttk.Entry(panel, textvariable=password_var, show="●", width=30).grid(
            row=2, column=1, padx=(12, 0), pady=5
        )
        active_var = tk.BooleanVar(value=bool(user["is_active"]) if user else True)
        if user:
            ttk.Checkbutton(panel, text="Account is active", variable=active_var).grid(
                row=3, column=1, sticky="w", padx=(12, 0), pady=5
            )

        def save() -> None:
            try:
                if user:
                    user_model.update_user(int(user["user_id"]), username_var.get(), role_var.get(),
                                           active_var.get(), password_var.get() or None)
                else:
                    user_model.create_user(username_var.get(), password_var.get(), role_var.get())
                dialog.destroy()
                self.refresh()
            except Exception as exc:
                show_error(exc, "Could not save staff account")

        buttons = ttk.Frame(panel)
        buttons.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left")
        ttk.Button(buttons, text="Save", command=save).pack(side="right")
        size_popup(dialog, self, 660, 520, min_width=560, min_height=440)

    def deactivate(self) -> None:
        user = self._selected()
        if not user:
            return
        if int(user["user_id"]) == int(getattr(self.winfo_toplevel(), "current_user", {}).get("user_id", -1)):
            messagebox.showinfo("Current account", "Sign in with another admin before deactivating this account.")
            return
        if messagebox.askyesno("Deactivate account", f"Deactivate {user['username']}?", parent=self):
            try:
                user_model.deactivate_user(int(user["user_id"]))
                self.refresh()
            except Exception as exc:
                show_error(exc, "Could not deactivate account")


class BrandingTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=24)
        ttk.Label(self, text="Restaurant Branding", style="MenuTitle.TLabel").pack(anchor="w")
        ttk.Label(
            self,
            text="Customize the name, tagline, and contact details shown across the app and receipts.",
            wraplength=700,
        ).pack(anchor="w", pady=(8, 16))
        form = ttk.Frame(self)
        form.pack(anchor="w", fill="x")
        self.variables = {
            "restaurant_name": tk.StringVar(),
            "tagline": tk.StringVar(),
            "branch": tk.StringVar(),
            "address": tk.StringVar(),
            "contact": tk.StringVar(),
        }
        fields = (
            ("Restaurant / app name", "restaurant_name"),
            ("Tagline", "tagline"),
            ("Branch name", "branch"),
            ("Address", "address"),
            ("Contact number", "contact"),
        )
        for row, (label, key) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=row * 2, column=0, sticky="w", pady=(3, 0))
            ttk.Entry(form, textvariable=self.variables[key], width=60).grid(
                row=row * 2 + 1, column=0, sticky="ew", pady=(3, 8)
            )
        form.columnconfigure(0, weight=1)
        self.preview_var = tk.StringVar()
        ttk.Label(self, textvariable=self.preview_var, style="MetricValue.TLabel").pack(anchor="w", pady=(4, 14))
        self.variables["restaurant_name"].trace_add("write", self._update_preview)
        self.variables["tagline"].trace_add("write", self._update_preview)
        ttk.Button(self, text="Save Branding", command=self.save).pack(anchor="w")
        self._load_settings()

    def _load_settings(self) -> None:
        try:
            settings = settings_model.get_branding_settings()
            for key, variable in self.variables.items():
                variable.set(settings[key])
            self._update_preview()
        except Exception as exc:
            show_error(exc, "Could not load branding settings")

    def _update_preview(self, *_args) -> None:
        name = self.variables["restaurant_name"].get().strip() or "Your Restaurant Name"
        tagline = self.variables["tagline"].get().strip()
        self.preview_var.set(f"Preview: {name}" + (f"  ·  {tagline}" if tagline else ""))

    def save(self) -> None:
        try:
            settings = settings_model.save_branding_settings(
                *(self.variables[key].get() for key in (
                    "restaurant_name", "tagline", "branch", "address", "contact"
                ))
            )
            root = self.winfo_toplevel()
            if hasattr(root, "set_branding_settings"):
                root.set_branding_settings(settings)
            messagebox.showinfo("Branding saved", "Brand details were updated across the app.", parent=self)
        except Exception as exc:
            show_error(exc, "Could not save branding settings")


class ReportsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=10)
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Label(toolbar, text="Report period").grid(row=0, column=0, sticky="w")
        self.period_var = tk.StringVar(value="Daily")
        self.period_box = ttk.Combobox(
            toolbar, textvariable=self.period_var,
            values=("Daily", "Weekly", "Monthly", "Custom Range"), state="readonly", width=14,
        )
        self.period_box.grid(row=0, column=1, padx=8, sticky="w")
        self.period_box.bind("<<ComboboxSelected>>", self._period_changed)
        ttk.Label(toolbar, text="From (YYYY-MM-DD)").grid(row=0, column=2, padx=(10, 3), sticky="e")
        self.start_var = tk.StringVar(value=date.today().replace(day=1).isoformat())
        self.start_entry = ttk.Entry(toolbar, textvariable=self.start_var, width=12)
        self.start_entry.grid(row=0, column=3, padx=(0, 6))
        ttk.Label(toolbar, text="To").grid(row=0, column=4, padx=(4, 3))
        self.end_var = tk.StringVar(value=date.today().isoformat())
        self.end_entry = ttk.Entry(toolbar, textvariable=self.end_var, width=12)
        self.end_entry.grid(row=0, column=5, padx=(0, 8))
        self.start_entry.configure(state="disabled")
        self.end_entry.configure(state="disabled")
        ttk.Button(toolbar, text="Generate", command=self.refresh).grid(row=0, column=6, padx=3)
        ttk.Button(toolbar, text="Export CSV", command=self.export_csv).grid(row=0, column=7, padx=3)
        ttk.Button(toolbar, text="Save Print PDF", command=self.export_pdf).grid(row=0, column=8, padx=3)
        self.summary_var = tk.StringVar(value="Select a period and generate a report.")
        ttk.Label(self, textvariable=self.summary_var, font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 8))
        self.content = ttk.Frame(self)
        self.content.pack(fill="both", expand=True)
        self.chart_host = ttk.Frame(self.content)
        self.chart_host.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.analytics = tk.Text(self.content, width=45, wrap="word", font=("Segoe UI", 10), padx=10, pady=8)
        self.analytics.pack(side="right", fill="both", expand=True)
        self._chart_canvas = None
        self._report_data: dict | None = None
        self.refresh()

    def _period_changed(self, _event=None) -> None:
        custom = self.period_var.get() == "Custom Range"
        state = "normal" if custom else "disabled"
        self.start_entry.configure(state=state)
        self.end_entry.configure(state=state)
        if not custom:
            self.refresh()

    def refresh(self) -> None:
        try:
            period = self.period_var.get()
            if period == "Custom Range":
                data = report_model.sales_summary(period, start_date=self.start_var.get(), end_date=self.end_var.get())
            else:
                data = report_model.sales_summary(period)
            self._report_data = data
            self.summary_var.set(
                f"{data['start_date']} to {data['end_date']}  |  "
                f"Sales: {php(data['sales'])}  |  Paid Transactions: {data['orders']}"
            )
            self._render_analytics(data)
            self._render_chart(data.get("trend", []), data.get("order_distribution", []))
        except Exception as exc:
            self._report_data = None
            show_error(exc, "Could not generate sales report")

    def _require_report(self) -> dict | None:
        if self._report_data is None:
            messagebox.showinfo("Generate a report", "Generate a valid sales report before exporting.", parent=self)
        return self._report_data

    def export_csv(self) -> None:
        data = self._require_report()
        if data is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self, title="Export Sales Report", initialfile="sales_report.csv",
            defaultextension=".csv", filetypes=(("CSV spreadsheet", "*.csv"),),
        )
        if not path:
            return
        try:
            saved = report_model.save_sales_report_csv(data, path)
            messagebox.showinfo("Report exported", f"CSV report saved to:\n{saved}", parent=self)
        except Exception as exc:
            show_error(exc, "Could not export CSV report")

    def export_pdf(self) -> None:
        data = self._require_report()
        if data is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self, title="Save Print-Ready Sales Report", initialfile="sales_report.pdf",
            defaultextension=".pdf", filetypes=(("PDF document", "*.pdf"),),
        )
        if not path:
            return
        try:
            root = self.winfo_toplevel()
            restaurant = getattr(root, "restaurant_name", "BITEBYTE")
            saved = report_model.save_sales_report_pdf(
                data,
                path,
                restaurant,
                getattr(root, "brand_tagline", "Crave It. Click It. Bite It."),
                getattr(root, "restaurant_branch", ""),
                getattr(root, "restaurant_address", ""),
                getattr(root, "restaurant_contact", ""),
            )
            messagebox.showinfo("Report saved", f"Print-ready PDF saved to:\n{saved}", parent=self)
        except Exception as exc:
            show_error(exc, "Could not save PDF report")

    def _render_analytics(self, data: dict) -> None:
        self.analytics.configure(state="normal")
        self.analytics.delete("1.0", "end")
        self.analytics.insert("end", "DAILY BREAKDOWN\n")
        for item in data.get("trend", []):
            self.analytics.insert("end", f"• {item['sale_date']}: {php(item['sales'])} ({item['orders']} paid)\n")
        products = data.get("products", [])
        if products:
            self.analytics.insert("end", "\nBEST-SELLING DISHES\n")
            for item in products[:5]:
                self.analytics.insert("end", f"• {item['product_name']} — {item['units_sold']} sold, {php(item['revenue'])}\n")
            self.analytics.insert("end", "\nLEAST-SELLING DISHES\n")
            for item in sorted(products, key=lambda row: (row["units_sold"], row["product_name"]))[:5]:
                self.analytics.insert("end", f"• {item['product_name']} — {item['units_sold']} sold\n")
        self.analytics.insert("end", "\nSALES BY CATEGORY\n")
        for item in data.get("categories", []):
            self.analytics.insert("end", f"• {item['category_name']}: {php(item['revenue'])}\n")
        self.analytics.configure(state="disabled")

    def _render_chart(self, trend: list[dict], distribution: list[dict]) -> None:
        for child in self.chart_host.winfo_children():
            child.destroy()
        self._chart_canvas = None
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
        except ImportError:
            ttk.Label(self.chart_host, text="Install matplotlib to display sales charts.").pack(pady=25)
            return
        figure = Figure(figsize=(9, 4), dpi=100, facecolor="#f8f9fa")
        axes = figure.add_subplot(121)
        order_axes = figure.add_subplot(122)
        axes.set_facecolor("white")
        order_axes.set_facecolor("white")
        labels = [str(item["sale_date"]) for item in trend]
        values = [float(item["sales"]) for item in trend]
        if labels:
            axes.plot(labels, values, marker="o", markerfacecolor="#ffc107",
                      markeredgecolor="#a71920", linewidth=2.5, color="#d32f2f")
            axes.set_title(f"{self.period_var.get()} Sales Trend (PHP)")
            axes.set_ylabel("PHP")
            axes.tick_params(axis="x", rotation=35)
            axes.grid(axis="y", color="#eadfda", linewidth=0.8)
        else:
            axes.text(0.5, 0.5, "No sales in this period", ha="center", va="center")
            axes.set_axis_off()
        if distribution:
            status_colors = {
                "Pending Payment": "#ff9800", "Paid": "#0288d1", "Preparing": "#0288d1",
                "Ready": "#2e7d32", "Completed": "#78909c", "Cancelled": "#e53935",
            }
            labels = [row["order_status"] for row in distribution]
            order_axes.bar(labels, [int(row["orders"]) for row in distribution],
                           color=[status_colors.get(label, "#c62828") for label in labels])
            order_axes.set_title("Order Distribution")
            order_axes.set_ylabel("Orders")
            order_axes.tick_params(axis="x", rotation=35)
            order_axes.grid(axis="y", color="#eadfda", linewidth=0.8)
            order_axes.set_axisbelow(True)
        else:
            order_axes.text(0.5, 0.5, "No orders in this period", ha="center", va="center")
            order_axes.set_axis_off()
        figure.tight_layout()
        self._chart_canvas = FigureCanvasTkAgg(figure, master=self.chart_host)
        self._chart_canvas.draw()
        self._chart_canvas.get_tk_widget().pack(fill="both", expand=True)
