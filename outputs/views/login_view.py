"""Staff sign-in screen."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from models import user_model
from views.common import show_error


class LoginView(ttk.Frame):
    def __init__(self, parent, on_login, on_back):
        super().__init__(parent, padding=16, style="LoginBackdrop.TFrame")
        self.on_login = on_login
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        panel = ttk.Frame(self, padding=30, style="LoginCard.TFrame")
        panel.grid(row=0, column=0, pady=18)
        panel.columnconfigure(1, weight=1)
        self._logo = self._load_logo()
        if self._logo:
            ttk.Label(panel, image=self._logo, background="white").grid(
                row=0, column=0, columnspan=2, pady=(0, 10)
            )
        ttk.Label(panel, text="Staff Sign In", style="LoginTitle.TLabel").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 16)
        )
        ttk.Label(panel, text="Username", style="LoginCard.TLabel").grid(row=2, column=0, sticky="w", pady=5)
        self.username = ttk.Entry(panel, width=32, font=("Segoe UI", 11))
        self.username.grid(row=2, column=1, sticky="ew", padx=(15, 0), pady=5)
        ttk.Label(panel, text="Password", style="LoginCard.TLabel").grid(row=3, column=0, sticky="w", pady=5)
        self.password = ttk.Entry(panel, width=32, show="●")
        self.password.grid(row=3, column=1, sticky="ew", padx=(15, 0), pady=5)
        self.username.bind("<Return>", self._submit_on_enter)
        self.password.bind("<Return>", self._submit_on_enter)

        ttk.Label(panel, text="Role", style="LoginCard.TLabel").grid(
            row=4, column=0, sticky="w", pady=(12, 4)
        )
        self.role_var = tk.StringVar(value="")
        role_row = ttk.Frame(panel, style="LoginCard.TFrame")
        role_row.grid(row=4, column=1, sticky="w", padx=(15, 0), pady=(12, 4))
        for role in user_model.VALID_ROLES:
            ttk.Radiobutton(
                role_row, text=role, value=role, variable=self.role_var,
                style="Login.TRadiobutton",
            ).pack(side="left", padx=(0, 8))

        buttons = ttk.Frame(panel, style="LoginCard.TFrame")
        buttons.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        ttk.Button(buttons, text="Back to Kiosk", command=on_back).pack(side="left")
        ttk.Button(buttons, text="Sign In", command=self.submit).pack(side="right")
        self.username.focus_set()

    @staticmethod
    def _load_logo():
        try:
            from PIL import Image, ImageOps, ImageTk

            path = Path(__file__).resolve().parents[1] / "assets" / "bitebyte-burger-click-logo.png"
            with Image.open(path) as source:
                image = ImageOps.contain(source.convert("RGB"), (240, 160), method=Image.LANCZOS)
            return ImageTk.PhotoImage(image)
        except (ImportError, OSError):
            return None

    def _submit_on_enter(self, _event=None) -> str:
        self.submit()
        return "break"

    def submit(self) -> None:
        try:
            selected_role = self.role_var.get()
            if not selected_role:
                raise ValueError("Select your staff role before signing in.")
            user = user_model.authenticate(self.username.get(), self.password.get())
            if not user:
                raise ValueError("Username or password is incorrect, or the account is inactive.")
            if user["role"] != selected_role:
                raise ValueError("The selected role does not match this account.")
            self.on_login(user)
        except Exception as exc:
            show_error(exc, "Sign-in failed")
