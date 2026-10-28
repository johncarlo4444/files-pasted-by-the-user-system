"""Run the World Fast Food Express kiosk and staff desktop application."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from datetime import datetime

from views.admin_view import AdminView
from views.cashier_view import CashierView
from views.kiosk_view import KioskView
from views.kitchen_view import KitchenView
from views.login_view import LoginView
from database import ensure_runtime_schema
from config import (
    RESTAURANT_ADDRESS,
    RESTAURANT_BRANCH,
    RESTAURANT_CONTACT,
    RESTAURANT_NAME,
    RESTAURANT_TAGLINE,
)
from models import settings_model
from views.theme import configure_theme


class FastFoodApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.restaurant_name = RESTAURANT_NAME
        self.brand_tagline = RESTAURANT_TAGLINE
        self.restaurant_branch = RESTAURANT_BRANCH
        self.restaurant_address = RESTAURANT_ADDRESS
        self.restaurant_contact = RESTAURANT_CONTACT
        self.title(self.restaurant_name)
        self.geometry("1280x820")
        self.minsize(980, 640)
        self.current_user: dict | None = None
        self._database_ready = False
        self._database_error = ""

        configure_theme(self)

        self.header = ttk.Frame(self, style="Header.TFrame", padding=(14, 8))
        self.header.pack(fill="x")
        self.title_label = ttk.Label(self.header, text=self.restaurant_name, style="HeaderTitle.TLabel")
        self.title_label.pack(side="left")
        self.clock_var = tk.StringVar()
        ttk.Label(self.header, textvariable=self.clock_var, style="Clock.TLabel").pack(side="left", padx=24)
        self.nav = ttk.Frame(self.header, style="Header.TFrame")
        self.nav.pack(side="right")
        self.content = ttk.Frame(self, padding=4)
        self.content.pack(fill="both", expand=True)
        self._update_clock()
        self._retry_database()

    def _update_clock(self) -> None:
        self.clock_var.set(datetime.now().astimezone().strftime("%a, %b %d  |  %I:%M:%S %p"))
        if self.winfo_exists():
            self.after(1000, self._update_clock)

    def _retry_database(self) -> None:
        """Bring an existing installation up to the schema expected by this app."""
        try:
            ensure_runtime_schema()
            self.set_branding_settings(settings_model.get_branding_settings())
        except Exception as exc:
            self._database_ready = False
            self._database_error = str(exc)
            self.show_database_setup()
            return
        self._database_ready = True
        self._database_error = ""
        self.show_kiosk()

    def set_restaurant_name(self, name: str) -> None:
        """Update the visible brand on the main window and future screens."""
        self.restaurant_name = name
        self.title(name)
        if getattr(self, "title_label", None) and self.title_label.winfo_exists():
            self.title_label.configure(text=name)

    def set_branding_settings(self, settings: dict[str, str]) -> None:
        self.restaurant_name = settings["restaurant_name"]
        self.brand_tagline = settings["tagline"]
        self.restaurant_branch = settings["branch"]
        self.restaurant_address = settings["address"]
        self.restaurant_contact = settings["contact"]
        self.set_restaurant_name(self.restaurant_name)

    def show_database_setup(self) -> None:
        """Show a recoverable setup page instead of opening DB-backed screens."""
        for child in self.nav.winfo_children():
            child.destroy()
        ttk.Button(self.nav, text="Retry", command=self._retry_database, style="Nav.TButton").pack(side="right")
        for child in self.content.winfo_children():
            child.destroy()

        panel = ttk.Frame(self.content, padding=36)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text="Database is not ready", font=("Segoe UI", 20, "bold")).pack(anchor="w", pady=(24, 12))
        ttk.Label(
            panel,
            text=(
                "The app could not connect to the configured MySQL database or complete its "
                "schema upgrade. Check that MySQL is running and the database settings in "
                "config.py are correct, then select Retry."
            ),
            wraplength=820,
            justify="left",
        ).pack(anchor="w", pady=(0, 14))
        ttk.Label(panel, text=f"Database error: {self._database_error}", wraplength=900,
                  justify="left", foreground="#9b1c1c").pack(anchor="w", pady=(0, 14))
        ttk.Label(
            panel,
            text=(
                "For a brand-new installation, create and seed the database by running "
                "python database.py from this app's folder. Existing databases are upgraded "
                "automatically when this app starts."
            ),
            wraplength=820,
            justify="left",
        ).pack(anchor="w")
        ttk.Button(panel, text="Retry database check", command=self._retry_database).pack(anchor="w", pady=20)

    def _require_database(self) -> bool:
        if self._database_ready:
            return True
        self.show_database_setup()
        return False

    def _render_nav(self) -> None:
        for child in self.nav.winfo_children():
            child.destroy()
        ttk.Button(self.nav, text="Customer Kiosk", command=self.show_kiosk, style="Nav.TButton").pack(
            side="left", padx=3
        )
        if not self.current_user:
            ttk.Button(self.nav, text="Staff Sign In", command=self.show_login, style="Nav.TButton").pack(
                side="left", padx=(6, 0)
            )
            return
        ttk.Label(self.nav, text=f"{self.current_user['username']} · {self.current_user['role']}",
                  style="HeaderBadge.TLabel").pack(side="left", padx=(10, 8))
        role = self.current_user["role"]
        if role == "Admin":
            ttk.Button(self.nav, text="Admin", command=self.show_admin, style="Nav.TButton").pack(side="left", padx=2)
            ttk.Button(self.nav, text="Cashier", command=self.show_cashier, style="Nav.TButton").pack(side="left", padx=2)
            ttk.Button(self.nav, text="Kitchen", command=self.show_kitchen, style="Nav.TButton").pack(side="left", padx=2)
        elif role == "Cashier":
            ttk.Button(self.nav, text="Checkout", command=self.show_cashier, style="Nav.TButton").pack(side="left", padx=2)
        elif role == "Kitchen Staff":
            ttk.Button(self.nav, text="Kitchen Queue", command=self.show_kitchen, style="Nav.TButton").pack(
                side="left", padx=2
            )
        ttk.Button(self.nav, text="Sign Out", command=self.sign_out, style="Nav.TButton").pack(
            side="left", padx=(6, 0)
        )

    def _show(self, view_factory) -> None:
        for child in self.content.winfo_children():
            child.destroy()
        view = view_factory(self.content)
        view.pack(fill="both", expand=True)

    def show_kiosk(self) -> None:
        if not self._require_database():
            return
        self._render_nav()
        self._show(KioskView)

    def show_login(self) -> None:
        if not self._require_database():
            return
        self._render_nav()
        self._show(lambda parent: LoginView(parent, self._on_login, self.show_kiosk))

    def _on_login(self, user: dict) -> None:
        self.current_user = user
        self._render_nav()
        if user["role"] == "Admin":
            self.show_admin()
        elif user["role"] == "Cashier":
            self.show_cashier()
        else:
            self.show_kitchen()

    def sign_out(self) -> None:
        self.current_user = None
        self.show_kiosk()

    def _require(self, roles: tuple[str, ...]) -> bool:
        if not self._require_database():
            return False
        if not self.current_user or self.current_user["role"] not in roles:
            self.show_login()
            return False
        return True

    def show_admin(self) -> None:
        if self._require(("Admin",)):
            self._render_nav()
            self._show(lambda parent: AdminView(parent, self.current_user))

    def show_cashier(self) -> None:
        if self._require(("Admin", "Cashier")):
            self._render_nav()
            self._show(lambda parent: CashierView(parent, self.current_user))

    def show_kitchen(self) -> None:
        if self._require(("Admin", "Kitchen Staff")):
            self._render_nav()
            self._show(KitchenView)


if __name__ == "__main__":
    FastFoodApp().mainloop()
