"""Staff sign-in screen."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from models import user_model
from views.common import show_error


class LoginView(ttk.Frame):
    def __init__(self, parent, on_login, on_back):
        super().__init__(parent, padding=30)
        self.on_login = on_login
        self.columnconfigure(0, weight=1)
        panel = ttk.Frame(self, padding=32, style="MenuCard.TFrame")
        panel.grid(row=0, column=0, sticky="n", pady=35)
        ttk.Label(panel, text="Staff Sign In", style="MenuTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 20)
        )
        ttk.Label(panel, text="Username").grid(row=1, column=0, sticky="w", pady=5)
        self.username = ttk.Entry(panel, width=32, font=("Segoe UI", 11))
        self.username.grid(row=1, column=1, sticky="ew", padx=(15, 0), pady=5)
        ttk.Label(panel, text="Password").grid(row=2, column=0, sticky="w", pady=5)
        self.password = ttk.Entry(panel, width=32, show="●")
        self.password.grid(row=2, column=1, sticky="ew", padx=(15, 0), pady=5)
        self.username.bind("<Return>", self._submit_on_enter)
        self.password.bind("<Return>", self._submit_on_enter)
        buttons = ttk.Frame(panel)
        buttons.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        ttk.Button(buttons, text="Back to Kiosk", command=on_back).pack(side="left")
        ttk.Button(buttons, text="Sign In", command=self.submit).pack(side="right")
        self.username.focus_set()

    def _submit_on_enter(self, _event=None) -> str:
        self.submit()
        return "break"

    def submit(self) -> None:
        try:
            user = user_model.authenticate(self.username.get(), self.password.get())
            if not user:
                raise ValueError("Username or password is incorrect, or the account is inactive.")
            self.on_login(user)
        except Exception as exc:
            show_error(exc, "Sign-in failed")
