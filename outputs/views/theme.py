"""Shared red-and-cream visual theme for the desktop app."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


RED = "#d32f2f"
DARK_RED = "#c62828"
LIGHT_RED = "#fbe9e8"
GOLD = "#ffc107"
PAGE = "#f8f9fa"
CARD = "#fffdfb"
TEXT = "#292524"
MUTED = "#756b68"
BORDER = "#e6d8d2"


def configure_theme(root: tk.Misc) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    root.configure(background=PAGE)
    style.configure(".", font=("Segoe UI", 10), background=PAGE, foreground=TEXT)
    style.configure("TFrame", background=PAGE)
    style.configure("TLabel", background=PAGE, foreground=TEXT)
    style.configure("TButton", background=RED, foreground="white", padding=(14, 12), borderwidth=0)
    style.map(
        "TButton",
        background=[("disabled", "#d9b8b8"), ("pressed", DARK_RED), ("active", "#d93636")],
        foreground=[("disabled", "#fffafa"), ("!disabled", "white")],
    )
    style.configure("Nav.TButton", background=DARK_RED, foreground="white", padding=(10, 6))
    style.map(
        "Nav.TButton",
        background=[("pressed", RED), ("active", "#c92b32")],
        foreground=[("disabled", "#f5dada"), ("!disabled", "white")],
    )
    style.configure("Gold.TButton", background=GOLD, foreground=DARK_RED,
                    font=("Segoe UI", 13, "bold"), padding=(22, 18))
    style.map("Gold.TButton", background=[("pressed", "#e0a800"), ("active", "#ffd54f")])
    style.configure("CategoryPill.TButton", background="white", foreground=DARK_RED,
                    padding=(12, 8), borderwidth=1)
    style.map(
        "CategoryPill.TButton",
        background=[("active", LIGHT_RED)],
        foreground=[("disabled", MUTED), ("!disabled", DARK_RED)],
    )
    style.configure("CategorySelected.TButton", background=GOLD, foreground=DARK_RED,
                    padding=(12, 8), borderwidth=1, font=("Segoe UI", 9, "bold"))
    style.map(
        "CategorySelected.TButton",
        background=[("pressed", "#e0a800"), ("active", "#ffd54f")],
        foreground=[("disabled", MUTED), ("!disabled", DARK_RED)],
    )
    style.configure("KioskCategoryPill.TButton", background="white", foreground=DARK_RED,
                    padding=(10, 4), borderwidth=1, font=("Segoe UI", 9))
    style.map("KioskCategoryPill.TButton", background=[("active", LIGHT_RED)],
              foreground=[("disabled", MUTED), ("!disabled", DARK_RED)])
    style.configure("KioskCategorySelected.TButton", background=GOLD, foreground=DARK_RED,
                    padding=(10, 4), borderwidth=1, font=("Segoe UI", 9, "bold"))
    style.map("KioskCategorySelected.TButton", background=[("pressed", "#e0a800"), ("active", "#ffd54f")],
              foreground=[("disabled", MUTED), ("!disabled", DARK_RED)])
    style.configure("Danger.TButton", background="#e53935", foreground="white", padding=(12, 8))
    style.map("Danger.TButton", background=[("pressed", "#b71c1c"), ("active", "#ef5350")])
    style.configure("TEntry", fieldbackground="white", foreground=TEXT, padding=6)
    style.configure("TCombobox", fieldbackground="white", foreground=TEXT, padding=5)
    style.map("TCombobox", fieldbackground=[("readonly", "white")])
    style.configure("TCheckbutton", background=PAGE, foreground=TEXT)
    style.configure("TRadiobutton", background=PAGE, foreground=TEXT)
    style.configure("TNotebook", background=PAGE, borderwidth=0)
    style.configure("TNotebook.Tab", background="#eadfda", foreground=TEXT, padding=(14, 8))
    style.map(
        "TNotebook.Tab",
        background=[("selected", RED), ("active", LIGHT_RED)],
        foreground=[("selected", "white"), ("!selected", TEXT)],
    )
    style.configure("TLabelframe", background=PAGE, bordercolor=BORDER)
    style.configure("TLabelframe.Label", background=PAGE, foreground=DARK_RED, font=("Segoe UI", 10, "bold"))
    style.configure("Treeview", background="white", fieldbackground="white", foreground=TEXT, rowheight=28)
    style.configure("Treeview.Heading", background="#eee4df", foreground=TEXT, font=("Segoe UI", 9, "bold"))
    style.map("Treeview", background=[("selected", RED)], foreground=[("selected", "white")])
    style.configure("TSeparator", background=BORDER)
    style.configure("Header.TFrame", background=DARK_RED)
    style.configure("HeaderTitle.TLabel", background=DARK_RED, foreground="white", font=("Segoe UI", 15, "bold"))
    style.configure("HeaderInfo.TLabel", background=DARK_RED, foreground="#fff1f0")
    style.configure("HeaderBadge.TLabel", background=GOLD, foreground=DARK_RED,
                    padding=(9, 5), font=("Segoe UI", 9, "bold"))
    style.configure("Clock.TLabel", background=DARK_RED, foreground="#fff1f0", font=("Segoe UI", 10))
    style.configure("Welcome.TFrame", background=RED)
    style.configure("WelcomeBrand.TLabel", background=RED, foreground="white",
                    font=("Segoe UI", 28, "bold"))
    style.configure("WelcomeText.TLabel", background=RED, foreground="#fff3e0",
                    font=("Segoe UI", 15))
    style.configure("WelcomeFood.TLabel", background=RED, foreground=GOLD,
                    font=("Segoe UI Emoji", 46))
    style.configure("LoginBackdrop.TFrame", background=RED)
    style.configure("LoginCard.TFrame", background="white", relief="solid", borderwidth=1,
                    bordercolor=BORDER)
    style.configure("LoginCard.TLabel", background="white", foreground=TEXT)
    style.configure("LoginTitle.TLabel", background="white", foreground=DARK_RED,
                    font=("Segoe UI", 20, "bold"))
    style.configure("Login.TRadiobutton", background="white", foreground=TEXT, padding=(4, 6))
    style.configure("MenuTitle.TLabel", background=PAGE, foreground=DARK_RED,
                    font=("Segoe UI", 18, "bold"))
    style.configure("KioskGuide.TFrame", background="#fff3cd", relief="solid",
                    borderwidth=1, bordercolor=GOLD)
    style.configure("KioskGuideTitle.TLabel", background="#fff3cd", foreground=DARK_RED,
                    font=("Segoe UI", 11, "bold"))
    style.configure("KioskGuideStep.TLabel", background="#fff3cd", foreground=DARK_RED,
                    font=("Segoe UI", 9, "bold"))
    style.configure("KioskGuideText.TLabel", background="#fff3cd", foreground=TEXT,
                    font=("Segoe UI", 10))
    style.configure("MenuCard.TFrame", background=CARD, bordercolor=BORDER, relief="solid", borderwidth=1)
    style.configure("MenuCard.TLabel", background=CARD, foreground=TEXT)
    style.configure("MenuCardCategory.TLabel", background=CARD, foreground=MUTED)
    style.configure("MenuCardPrice.TLabel", background=CARD, foreground=DARK_RED, font=("Segoe UI", 12, "bold"))
    style.configure("OutOfStock.TFrame", background="#eeeceb", bordercolor="#c9c4c1",
                    relief="solid", borderwidth=1)
    style.configure("OutOfStock.TLabel", background="#eeeceb", foreground="#827c79")
    style.configure("OutOfStockCategory.TLabel", background="#eeeceb", foreground="#928b88")
    style.configure("OutOfStockPrice.TLabel", background="#eeeceb", foreground="#827c79",
                    font=("Segoe UI", 12, "bold"))
    style.configure("OutOfStockBadge.TLabel", background="#e53935", foreground="white",
                    padding=(8, 4), font=("Segoe UI", 9, "bold"))
    style.configure("ChangeValue.TLabel", background=PAGE, foreground=DARK_RED,
                    font=("Segoe UI", 14, "bold"))
    style.configure("KdsColumn.TFrame", background="#eee7e3", relief="solid", borderwidth=1)
    style.configure("KdsEmpty.TLabel", background="#eee7e3", foreground=MUTED)
    style.configure("KdsCard.TFrame", background=CARD, relief="solid", borderwidth=1)
    style.configure("KdsCard.TLabel", background=CARD, foreground=TEXT)
    style.configure("KdsCode.TLabel", background=CARD, foreground=DARK_RED,
                    font=("Segoe UI", 13, "bold"))
    style.configure("KdsPending.TLabel", background="#ff9800", foreground="white",
                    padding=(8, 4), font=("Segoe UI", 10, "bold"))
    style.configure("KdsPreparing.TLabel", background="#0288d1", foreground="white",
                    padding=(8, 4), font=("Segoe UI", 10, "bold"))
    style.configure("KdsReady.TLabel", background="#2e7d32", foreground="white",
                    padding=(8, 4), font=("Segoe UI", 10, "bold"))
    style.configure("KdsCompleted.TLabel", background="#455a64", foreground="white",
                    padding=(8, 4), font=("Segoe UI", 10, "bold"))
    style.configure("MetricCard.TFrame", background=CARD, relief="solid", borderwidth=1)
    style.configure("MetricTitle.TLabel", background=CARD, foreground=MUTED)
    style.configure("MetricValue.TLabel", background=CARD, foreground=DARK_RED,
                    font=("Segoe UI", 23, "bold"))
    style.configure("MetricPending.TLabel", background=CARD, foreground="#ff9800",
                    font=("Segoe UI", 23, "bold"))
    style.configure("MetricPreparing.TLabel", background=CARD, foreground="#0288d1",
                    font=("Segoe UI", 23, "bold"))
    style.configure("MetricReady.TLabel", background=CARD, foreground="#2e7d32",
                    font=("Segoe UI", 23, "bold"))
    style.configure("MetricCancelled.TLabel", background=CARD, foreground="#e53935",
                    font=("Segoe UI", 23, "bold"))
    style.configure("ReceiptTitle.TLabel", background="white", foreground=DARK_RED,
                    font=("Segoe UI", 17, "bold"))
    style.configure("ReceiptSubtitle.TLabel", background="white", foreground=MUTED,
                    font=("Segoe UI", 10))
