"""Customer-facing self-service kiosk screen."""

from __future__ import annotations

import itertools
import re
import tkinter as tk
import ctypes
import os
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from models import order_model, product_model
from views.common import enable_mousewheel_scrolling, php, show_error, size_popup
from views.theme import PAGE, RED


class _BackgroundMusic:
    """Small Windows MCI wrapper for bundled MP3 playback and volume control."""

    _ALIAS = "bitebyte_kiosk_music"

    def __init__(self, path: Path):
        if os.name != "nt":
            raise OSError("Kiosk background music currently requires Windows.")
        if not path.is_file():
            raise FileNotFoundError(path)
        self._winmm = ctypes.WinDLL("winmm")
        self._send = self._winmm.mciSendStringW
        self._send.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p)
        self._send.restype = ctypes.c_ulong
        self._get_error = self._winmm.mciGetErrorStringW
        self._get_error.argtypes = (ctypes.c_ulong, ctypes.c_wchar_p, ctypes.c_uint)
        self._get_error.restype = ctypes.c_int
        self._opened = False
        self._paused = False
        try:
            self._send_command(f'open "{path}" type mpegvideo alias {self._ALIAS}')
            self._opened = True
            self.set_volume(45)
            self.play()
        except Exception:
            self.close()
            raise

    def _send_command(self, command: str) -> None:
        code = self._send(command, None, 0, None)
        if code:
            message = ctypes.create_unicode_buffer(256)
            if self._get_error(code, message, len(message)):
                raise OSError(message.value)
            raise OSError(f"Windows audio error {code}")

    def play(self) -> None:
        if self._opened:
            self._send_command(f"play {self._ALIAS} repeat")
            self._paused = False

    def toggle(self) -> bool:
        if self._paused:
            self._send_command(f"resume {self._ALIAS}")
            self._paused = False
        else:
            self._send_command(f"pause {self._ALIAS}")
            self._paused = True
        return not self._paused

    def set_volume(self, percent: int) -> None:
        if self._opened:
            self._send_command(f"setaudio {self._ALIAS} volume to {max(0, min(100, percent)) * 10}")

    def close(self) -> None:
        if self._opened:
            try:
                self._send_command(f"close {self._ALIAS}")
            except OSError:
                pass
            self._opened = False


def _priced_extras(options: tuple[tuple[str, int], ...]) -> dict[str, tuple[str, int]]:
    return {f"{name} (+{php(price)})": (name, price) for name, price in options}


def _extras_for_product(product: dict) -> dict[str, tuple[str, int]]:
    """Return add-ons that make sense for this menu category and product."""
    category = (product.get("category_name") or "").casefold()
    name = (product.get("product_name") or "").casefold()

    if category == "burgers & steaks":
        if "portobello" in name or "veggie" in name:
            options = (
                ("Extra veggie patty", 45),
                ("Extra cheese", 30),
                ("Avocado", 25),
                ("Grilled mushrooms", 25),
            )
        elif "burger" in name:
            options = (
                ("Extra patty", 60),
                ("Extra cheese", 30),
                ("Bacon", 45),
                ("Add egg", 20),
            )
        else:
            options = (
                ("Extra steak portion", 120),
                ("Garlic butter", 25),
                ("Sauteed mushrooms", 35),
                ("Extra vegetables", 25),
            )
    elif category == "american classics":
        if "ribs" in name:
            options = (
                ("Extra ribs", 100),
                ("Extra barbecue sauce", 20),
                ("Add fries", 30),
                ("Coleslaw", 25),
            )
        elif "wing" in name:
            options = (
                ("Extra wing", 35),
                ("Extra Buffalo sauce", 15),
                ("Ranch dip", 20),
                ("Add fries", 30),
            )
        elif "pancake" in name:
            options = (
                ("Extra pancake", 35),
                ("Maple syrup", 15),
                ("Fresh berries", 25),
                ("Bacon", 45),
            )
        elif "cookie" in name:
            options = (
                ("Extra cookie", 35),
                ("Add vanilla ice cream", 35),
                ("Chocolate drizzle", 15),
                ("Walnuts", 20),
            )
        elif "hot dog" in name:
            options = (
                ("Extra sausage", 45),
                ("Cheese sauce", 20),
                ("Chili topping", 25),
                ("Sauerkraut", 15),
            )
        elif "macaroni" in name:
            options = (
                ("Extra cheese", 25),
                ("Add bacon", 45),
                ("Add chicken", 55),
                ("Breadcrumb topping", 15),
            )
        elif "chowder" in name:
            options = (
                ("Extra chowder serving", 60),
                ("Extra clams", 45),
                ("Oyster crackers", 10),
                ("Bacon bits", 25),
            )
        elif "chicken" in name:
            options = (
                ("Extra chicken piece", 45),
                ("Extra gravy", 15),
                ("Add biscuit", 25),
                ("Add side", 30),
            )
        else:
            options = (
                ("Extra serving", 30),
                ("Extra sauce", 15),
            )
    elif category == "chicken & tacos":
        if "taco" in name or "quesadilla" in name:
            options = (
                ("Extra meat filling", 55),
                ("Extra cheese", 25),
                ("Salsa", 15),
                ("Guacamole", 30),
            )
        elif "wing" in name:
            options = (
                ("Extra chicken piece", 45),
                ("Extra wing sauce", 15),
                ("Dipping sauce", 15),
                ("Add fries", 30),
            )
        else:
            options = (
                ("Extra chicken piece", 45),
                ("Extra gravy or sauce", 15),
                ("Add rice", 25),
                ("Spicy seasoning", 10),
            )
    elif category == "pizza & pasta":
        if "pizza" in name:
            options = (
                ("Extra cheese", 35),
                ("Extra toppings", 40),
                ("Add chicken", 55),
                ("Extra pizza sauce", 15),
            )
        else:
            options = (
                ("Extra pasta", 40),
                ("Add chicken", 55),
                ("Extra parmesan", 25),
                ("Extra pasta sauce", 20),
            )
    elif category == "asian classics":
        if "sushi" in name or "roll" in name:
            options = (
                ("Extra sushi roll", 65),
                ("Extra fish topping", 55),
                ("Avocado", 25),
                ("Extra soy sauce", 10),
            )
        elif any(word in name for word in ("ramen", "pho", "noodle", "pad thai")):
            options = (
                ("Extra noodles", 30),
                ("Extra protein", 55),
                ("Add egg", 20),
                ("Extra broth or sauce", 15),
            )
        elif "dim sum" in name:
            options = (
                ("Extra dumpling", 35),
                ("Extra dipping sauce", 15),
                ("Chili oil", 10),
                ("Add rice", 25),
            )
        else:
            options = (
                ("Extra protein", 55),
                ("Add rice", 25),
                ("Extra vegetables", 20),
                ("Extra sauce", 15),
            )
    elif category == "rice meals":
        options = (
            ("Extra rice", 20),
            ("Extra protein", 55),
            ("Add egg", 20),
            ("Extra vegetables", 20),
            ("Extra sauce", 15),
        )
    elif category == "combos":
        options = (
            ("Add a side", 30),
            ("Upgrade drink", 20),
            ("Add dessert", 35),
            ("Extra main item", 55),
        )
    elif category == "sides, desserts & drinks":
        if "bubble tea" in name:
            options = (
                ("Extra tapioca pearls", 20),
                ("Add flavor syrup", 15),
                ("Whipped cream", 20),
            )
        elif "coffee" in name:
            options = (
                ("Extra espresso shot", 35),
                ("Whipped cream", 20),
                ("Add flavor syrup", 15),
                ("Extra milk", 15),
            )
        elif "shake" in name:
            options = (
                ("Add ice cream scoop", 35),
                ("Whipped cream", 20),
                ("Extra fruit syrup", 15),
                ("Extra fruit topping", 20),
            )
        elif "cola" in name:
            options = (
                ("Add ice cream float", 35),
                ("Add cherry topping", 15),
                ("Vanilla syrup", 15),
            )
        elif "lemonade" in name:
            options = (
                ("Extra lemon", 10),
                ("Add fruit flavor", 15),
                ("Mint", 10),
                ("Fruit jelly", 20),
            )
        elif "matcha" in name or "latte" in name:
            options = (
                ("Extra milk", 15),
                ("Add boba pearls", 20),
                ("Vanilla syrup", 15),
                ("Whipped cream", 20),
            )
        elif "tea" in name:
            options = (
                ("Extra lemon", 10),
                ("Add fruit flavor", 15),
                ("Fruit jelly", 20),
                ("Add boba pearls", 20),
            )
        elif any(word in name for word in ("gelato", "ice cream")):
            options = (
                ("Extra scoop", 40),
                ("Chocolate or caramel topping", 20),
                ("Whipped cream", 15),
                ("Waffle cone", 15),
            )
        elif any(word in name for word in ("cake", "pie", "brownie", "churros", "tiramisu", "sticky rice")):
            options = (
                ("Add ice cream", 35),
                ("Chocolate or caramel drizzle", 15),
                ("Whipped cream", 15),
                ("Extra topping", 20),
            )
        else:
            options = (
                ("Upgrade portion", 30),
                ("Cheese sauce", 25),
                ("Dipping sauce", 15),
                ("Seasoning", 10),
            )
    else:
        options = (
            ("Extra portion", 30),
            ("Extra sauce", 15),
        )

    return _priced_extras(options)


def _preferences_for_product(product: dict) -> tuple[str, ...]:
    """Return no-cost preference checkboxes that fit the product being ordered."""
    category = (product.get("category_name") or "").casefold()
    name = (product.get("product_name") or "").casefold()
    if any(word in name for word in (
        "gelato", "ice cream", "cake", "pie", "brownie", "churros", "cookie",
        "pancake", "tiramisu", "sticky rice",
    )):
        return ("No whipped cream", "No drizzle", "Less sweet")
    if category == "sides, desserts & drinks" and any(word in name for word in (
        "tea", "coffee", "cola", "lemonade", "latte", "matcha", "juice", "soda", "shake",
    )):
        return ("No ice", "Less ice", "No sugar", "Less sugar")
    if category == "asian classics":
        return ("No green onions", "No chili", "Less spicy", "Extra spicy")
    if category == "pizza & pasta":
        return ("No olives", "No onions", "Light sauce", "Extra spicy")
    if category == "burgers & steaks":
        return ("No onions", "No pickles", "No tomatoes", "No sauce")
    return ("No onions", "No sauce", "Less spicy", "Extra spicy")


class KioskView(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=6)
        self._cart_ids = itertools.count(1)
        self.cart: dict[int, dict] = {}
        self.products: list[dict] = []
        self.categories: list[dict] = []
        self.order_type: str | None = None
        self.browse_only = False
        self._search_job = None
        self._resize_render_job = None
        self._photo_refs = []
        self.view_mode_var = tk.StringVar(value="Grid")
        self.photo_size_var = tk.StringVar(value="Medium")
        self._music_volume = 45
        self._music_playing = True
        try:
            music_path = Path(__file__).resolve().parents[1] / "assets" / "bitebyte-background-music.mp3"
            self._music = _BackgroundMusic(music_path)
        except Exception as exc:
            self._music = None
            self._music_error = str(exc)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_welcome()

    def _build_welcome(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        self.columnconfigure(1, weight=0)
        self.order_type = None
        self.browse_only = False
        self.cart.clear()
        panel = ttk.Frame(self, padding=40, style="Welcome.TFrame")
        panel.grid(row=0, column=0, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        brand_name = getattr(self.winfo_toplevel(), "restaurant_name", "BITEBYTE")
        brand_tagline = getattr(self.winfo_toplevel(), "brand_tagline", "Crave It. Click It. Bite It.")
        row = 0
        banner = self._banner_photo()
        if banner:
            self._welcome_banner_ref = banner
            ttk.Label(panel, image=banner, background=RED).grid(
                row=row, column=0, pady=(8, 12)
            )
            row += 1
            # The banner includes the default BITEBYTE name and tagline. Keep
            # customized branding visible when the admin changes it.
            if brand_name != "BITEBYTE" or brand_tagline != "Crave It. Click It. Bite It.":
                ttk.Label(panel, text=brand_name, style="WelcomeBrand.TLabel").grid(
                    row=row, column=0, pady=(0, 6)
                )
                row += 1
                ttk.Label(panel, text=brand_tagline, style="WelcomeText.TLabel").grid(
                    row=row, column=0, pady=(0, 12)
                )
                row += 1
        else:
            logo = self._brand_logo((560, 360))
            if logo:
                self._welcome_logo_ref = logo
                ttk.Label(panel, image=logo, background=RED).grid(
                    row=row, column=0, pady=(25, 12)
                )
                row += 1
                if brand_name != "BITEBYTE" or brand_tagline != "Crave It. Click It. Bite It.":
                    ttk.Label(panel, text=brand_name, style="WelcomeBrand.TLabel").grid(
                        row=row, column=0, pady=(0, 6)
                    )
                    row += 1
                    ttk.Label(panel, text=brand_tagline, style="WelcomeText.TLabel").grid(
                        row=row, column=0, pady=(0, 12)
                    )
                    row += 1
            else:
                ttk.Label(panel, text="\U0001F354     \U0001F35F     \U0001F355", style="WelcomeFood.TLabel").grid(
                    row=row, column=0, pady=(55, 14)
                )
                row += 1
                ttk.Label(panel, text=brand_name, style="WelcomeBrand.TLabel").grid(
                    row=row, column=0, pady=(0, 10)
                )
                row += 1
                ttk.Label(panel, text=brand_tagline, style="WelcomeText.TLabel").grid(
                    row=row, column=0, pady=(0, 28)
                )
                row += 1
        actions = ttk.Frame(panel, style="Welcome.TFrame")
        actions.grid(row=row, column=0, pady=(8, 0))
        ttk.Button(actions, text="START ORDER", style="Gold.TButton",
                   command=self._choose_order_type).pack(side="left", padx=6, ipadx=12)
        ttk.Button(actions, text="VIEW MENU", style="Nav.TButton",
                   command=self._browse_menu).pack(side="left", padx=6, ipadx=12, ipady=5)
        row += 1
        music_controls = self._build_music_controls(panel, welcome=True)
        music_controls.grid(row=row, column=0, pady=(14, 0))

    def _build_music_controls(self, parent, *, welcome: bool = False) -> ttk.Frame:
        controls = ttk.Frame(parent, style="Welcome.TFrame" if welcome else "TFrame")
        label_style = "WelcomeText.TLabel" if welcome else "TLabel"
        if self._music is None:
            ttk.Label(controls, text="Background music unavailable", style=label_style).pack(side="left")
            return controls
        self._music_button = ttk.Button(
            controls,
            text="♫ Music: On" if self._music_playing else "♫ Music: Off",
            style="Nav.TButton",
            command=self._toggle_music,
        )
        self._music_button.pack(side="left", padx=(0, 8))
        ttk.Label(controls, text="Volume", style=label_style).pack(side="left", padx=(0, 5))
        self._music_volume_var = tk.DoubleVar(value=self._music_volume)
        ttk.Scale(
            controls,
            from_=0,
            to=100,
            orient="horizontal",
            length=110,
            variable=self._music_volume_var,
            command=self._set_music_volume,
        ).pack(side="left")
        return controls

    def _toggle_music(self) -> None:
        if self._music is None:
            return
        try:
            self._music_playing = self._music.toggle()
            self._music_button.configure(text="♫ Music: On" if self._music_playing else "♫ Music: Off")
        except OSError as exc:
            show_error(exc, "Could not control background music")

    def _set_music_volume(self, value: str) -> None:
        if self._music is None:
            return
        self._music_volume = int(float(value))
        try:
            self._music.set_volume(self._music_volume)
        except OSError as exc:
            show_error(exc, "Could not change music volume")

    def _browse_menu(self) -> None:
        """Show a full-width, view-only catalog without cart controls."""
        self.order_type = None
        self.browse_only = True
        self.cart.clear()
        self._build_ordering()

    def _brand_logo(self, size: tuple[int, int]):
        """Load the bundled kiosk logo at a size that fits the current screen."""
        try:
            from PIL import Image, ImageOps, ImageTk

            logo_path = Path(__file__).resolve().parents[1] / "assets" / "bitebyte-burger-click-logo.png"
            with Image.open(logo_path) as source:
                image = ImageOps.contain(source.convert("RGB"), size, method=Image.LANCZOS)
            return ImageTk.PhotoImage(image)
        except (ImportError, OSError):
            return None

    def _banner_photo(self):
        """Load the welcome advertisement while reserving room for the order CTA."""
        try:
            from PIL import Image, ImageOps, ImageTk

            banner_path = Path(__file__).resolve().parents[1] / "assets" / "bitebyte-feast-advertisement.png"
            max_size = (
                max(320, min(960, self.winfo_screenwidth() - 160)),
                max(240, min(540, self.winfo_screenheight() - 300)),
            )
            with Image.open(banner_path) as source:
                image = ImageOps.contain(source.convert("RGB"), max_size, method=Image.LANCZOS)
            return ImageTk.PhotoImage(image)
        except (ImportError, OSError):
            return None

    def _choose_order_type(self, on_selected=None) -> None:
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
            self.browse_only = False
            dialog.destroy()
            if hasattr(self, "order_title_var"):
                self.order_title_var.set(f"{value} Order")
            if on_selected:
                on_selected()
            else:
                self._build_ordering()

        ttk.Button(box, text="Dine-In", command=lambda: choose("Dine-In")).pack(fill="x", pady=5, ipady=8)
        ttk.Button(box, text="Take-Out", command=lambda: choose("Take-Out")).pack(fill="x", pady=5, ipady=8)
        ttk.Button(box, text="Cancel", command=dialog.destroy).pack(anchor="e", pady=(12, 0))
        size_popup(dialog, self, 520, 380, min_width=440, min_height=340, resizable=False)

    def _build_ordering(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        self.columnconfigure(0, weight=1 if self.browse_only else 4)
        self.columnconfigure(1, weight=0 if self.browse_only else 2)
        # Row 0 is weighted for the centered welcome screen; keep the ordering
        # header at its requested height and let the product area expand.
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=0)
        self.rowconfigure(2, weight=0)

        top = ttk.Frame(self)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 3))
        top.columnconfigure(1, weight=1)
        brand = ttk.Frame(top)
        brand.grid(row=0, column=0, sticky="w")
        logo = self._brand_logo((100, 68))
        if logo:
            self._ordering_logo_ref = logo
            ttk.Label(brand, image=logo, background=PAGE).pack(side="left", padx=(0, 10))
        self.order_title_var = tk.StringVar(
            value=f"{self.order_type} Order" if self.order_type else "Browse the Menu"
        )
        ttk.Label(brand, textvariable=self.order_title_var, style="MenuTitle.TLabel").pack(side="left")
        guide = ttk.Frame(top, padding=(6, 3), style="KioskGuide.TFrame")
        guide.grid(row=0, column=1, sticky="ew", padx=14, pady=2)
        ttk.Label(
            guide, text="BUILD YOUR BITE", style="KioskGuideTitle.TLabel",
            anchor="center", justify="center",
        ).pack(fill="x", anchor="center")
        actions = ttk.Frame(top)
        actions.grid(row=0, column=2, sticky="e")
        ttk.Button(
            actions,
            text="Start Over" if self.order_type else "Back to Welcome",
            command=self._confirm_reset,
            width=16 if self.browse_only else 12,
            style="Nav.TButton",
        ).pack(side="left", padx=(0, 10))
        self._build_music_controls(actions).pack(side="left")
        search_row = ttk.Frame(self)
        search_row.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 12))
        ttk.Label(search_row, text="Search menu").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_row, textvariable=self.search_var, width=20)
        self.search_entry.pack(side="left", padx=(8, 8))
        ttk.Button(
            search_row, text="Search", style="Nav.TButton", command=self._load_products
        ).pack(side="left", padx=(0, 12))
        self.search_entry.bind("<Return>", lambda _event: self._load_products())
        self.search_var.trace_add("write", self._search_changed)
        ttk.Label(search_row, text="View").pack(side="left", padx=(0, 5))
        view_picker = ttk.Combobox(
            search_row, textvariable=self.view_mode_var, values=("Grid", "List"),
            state="readonly", width=8,
        )
        view_picker.pack(side="left", padx=(0, 12))
        view_picker.bind("<<ComboboxSelected>>", self._view_options_changed)
        ttk.Label(search_row, text="Photo size").pack(side="left", padx=(0, 5))
        size_picker = ttk.Combobox(
            search_row, textvariable=self.photo_size_var, values=("Small", "Medium", "Large"),
            state="readonly", width=9,
        )
        size_picker.pack(side="left")
        size_picker.bind("<<ComboboxSelected>>", self._view_options_changed)
        if self.browse_only:
            guide_text = "1 Explore  →  2 Compare  →  3 Start Order"
        else:
            guide_text = "1 Browse  →  2 Customize  →  3 Checkout"
        ttk.Label(search_row, text=guide_text, style="KioskGuideStep.TLabel").pack(
            side="left", padx=(18, 0)
        )
        self.category_var = tk.StringVar(value="All categories")
        category_shell = ttk.Frame(self)
        category_shell.grid(row=2, column=0, columnspan=2,
                            sticky="ew", padx=(0, 12), pady=(2, 0))
        category_shell.columnconfigure(0, weight=1)
        self.category_canvas = tk.Canvas(category_shell, height=32, highlightthickness=0,
                                         background=PAGE, borderwidth=0)
        self.category_canvas.grid(row=0, column=0, sticky="ew")
        category_scroll = ttk.Scrollbar(category_shell, orient="horizontal", command=self.category_canvas.xview)
        category_scroll.grid(row=1, column=0, sticky="ew")
        self.category_canvas.configure(xscrollcommand=category_scroll.set)
        enable_mousewheel_scrolling(self.category_canvas, axis="x")
        self.category_buttons = ttk.Frame(self.category_canvas)
        self.category_window = self.category_canvas.create_window(
            (0, 0), window=self.category_buttons, anchor="nw"
        )
        self.category_buttons.bind(
            "<Configure>", lambda _event: self.category_canvas.configure(
                scrollregion=self.category_canvas.bbox("all")
            )
        )
        self.rowconfigure(3, weight=1)
        if self.browse_only:
            menu_panel = ttk.Frame(self, padding=(0, 0, 0, 0))
            menu_panel.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(3, 0))
        else:
            body = ttk.Panedwindow(self, orient="horizontal")
            body.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(3, 0))
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
        enable_mousewheel_scrolling(self.menu_canvas, axis="y")
        self.menu_canvas.bind("<Configure>", self._resize_menu_content)
        self.menu_canvas.pack(side="left", fill="both", expand=True)
        menu_scroll.pack(side="right", fill="y")

        if not self.browse_only:
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
            ttk.Button(cart_panel, text="PROCEED TO CHECKOUT", command=self._preview_order).grid(
                row=4, column=0, sticky="ew", pady=(10, 0), ipady=4
            )

        self._load_categories()
        self._load_products()

    def _resize_menu_content(self, event) -> None:
        self.menu_canvas.itemconfigure(self.menu_window, width=event.width)
        if self._resize_render_job:
            self.after_cancel(self._resize_render_job)
        self._resize_render_job = self.after(120, self._render_products)

    def _view_options_changed(self, _event=None) -> None:
        self._render_products()

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
                    style="KioskCategorySelected.TButton" if selected else "KioskCategoryPill.TButton",
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
        self._resize_render_job = None
        if not hasattr(self, "cards_frame") or not self.cards_frame.winfo_exists():
            return
        for child in self.cards_frame.winfo_children():
            child.destroy()
        self._photo_refs = []
        if not self.products:
            ttk.Label(self.cards_frame, text="No menu items match your search.").grid(padx=20, pady=30)
            return

        mode = self.view_mode_var.get()
        selected_size = self.photo_size_var.get()
        grid_photo_sizes = {"Small": (130, 82), "Medium": (180, 115), "Large": (250, 160)}
        list_photo_sizes = {"Small": (110, 78), "Medium": (160, 110), "Large": (220, 150)}
        photo_size = (list_photo_sizes if mode == "List" else grid_photo_sizes).get(
            selected_size, grid_photo_sizes["Medium"]
        )
        available_width = self.menu_canvas.winfo_width()
        if available_width < 160:
            available_width = max(360, int(self.winfo_toplevel().winfo_width() * 0.58) - 24)
        target_card_width = {"Small": 180, "Medium": 235, "Large": 350}.get(selected_size, 235)
        columns = 1 if mode == "List" else max(1, min(4, available_width // target_card_width))
        for column in range(4):
            active = column < columns
            self.cards_frame.columnconfigure(
                column,
                weight=1 if active else 0,
                uniform="menu-card" if active and mode == "Grid" else "",
            )

        for index, product in enumerate(self.products):
            row, column = divmod(index, columns)
            can_order = bool(product["can_order"])
            card_style = "MenuCard.TFrame" if can_order else "OutOfStock.TFrame"
            text_style = "MenuCard.TLabel" if can_order else "OutOfStock.TLabel"
            category_style = "MenuCardCategory.TLabel" if can_order else "OutOfStockCategory.TLabel"
            price_style = "MenuCardPrice.TLabel" if can_order else "OutOfStockPrice.TLabel"
            card = ttk.Frame(self.cards_frame, padding=10, style=card_style)
            card.grid(row=row, column=column, sticky="nsew", padx=6, pady=6)
            photo = self._product_photo(
                product.get("image_path"), product["product_name"], disabled=not can_order,
                size=photo_size,
            )
            if photo:
                image_label = ttk.Label(card, image=photo, style=text_style)
                self._photo_refs.append(photo)
            else:
                image_label = ttk.Label(card, text="🍽", font=("Segoe UI Emoji", 26), style=text_style)

            if mode == "List":
                card.columnconfigure(1, weight=1)
                image_label.grid(row=0, column=0, rowspan=6, sticky="nw", padx=(0, 12))
                detail_width = max(180, available_width - photo_size[0] - 84)
                detail = ttk.Frame(card, style=card_style)
                detail.grid(row=0, column=1, sticky="nsew")
                if not can_order:
                    ttk.Label(detail, text="OUT OF STOCK", style="OutOfStockBadge.TLabel").pack(anchor="w", pady=(0, 3))
                ttk.Label(detail, text=product["product_name"], style=text_style,
                          font=("Segoe UI", 11, "bold"), wraplength=detail_width,
                          justify="left").pack(anchor="w", fill="x")
                ttk.Label(detail, text=product["category_name"], style=category_style).pack(anchor="w")
                ttk.Label(detail, text=product["description"] or "", style=text_style,
                          wraplength=detail_width, justify="left").pack(anchor="w", fill="x", pady=(4, 2))
                ttk.Label(detail, text=php(product["price"]), style=price_style).pack(anchor="w", pady=3)
                if can_order and not self.browse_only:
                    ttk.Button(detail, text="+ Customize & Add",
                               command=lambda p=product: self._customize(p)).pack(anchor="w", pady=(3, 0))
            else:
                image_label.pack(pady=(0, 6))
                wrap = max(120, int(available_width / columns) - 42)
                if not can_order:
                    ttk.Label(card, text="OUT OF STOCK", style="OutOfStockBadge.TLabel").pack(pady=(0, 4))
                ttk.Label(card, text=product["product_name"], style=text_style,
                          font=("Segoe UI", 11, "bold"), wraplength=wrap,
                          justify="center").pack(fill="x")
                ttk.Label(card, text=product["category_name"], style=category_style).pack()
                ttk.Label(card, text=product["description"] or "", style=text_style,
                          wraplength=wrap, justify="center").pack(fill="x", pady=(4, 2))
                ttk.Label(card, text=php(product["price"]), style=price_style).pack(pady=3)
                if can_order and not self.browse_only:
                    ttk.Button(card, text="+ Customize & Add", command=lambda p=product: self._customize(p)).pack(
                        fill="x", pady=(3, 0)
                    )

    def _product_photo(
        self, path: str | None, product_name: str, *, disabled: bool = False,
        size: tuple[int, int] = (220, 130),
    ):
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
                            source.convert("RGB"), size, method=Image.LANCZOS
                        )
                        if disabled:
                            image = ImageOps.colorize(
                                ImageOps.grayscale(image), black="#8d8987", white="#e8e6e5"
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
        panel = ttk.Frame(dialog, padding=18)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text=product["product_name"], font=("Segoe UI", 15, "bold")).pack(anchor="w")
        size_var = tk.StringVar(value="Regular")
        ttk.Label(panel, text="Size").pack(anchor="w", pady=(12, 2))
        ttk.Radiobutton(panel, text="Regular", value="Regular", variable=size_var).pack(anchor="w")
        ttk.Radiobutton(panel, text="Large (+₱60.00)", value="Large", variable=size_var).pack(anchor="w")
        ttk.Label(panel, text="Food-specific extras & add-ons").pack(anchor="w", pady=(12, 2))
        extras = _extras_for_product(product)
        extra_vars = {label: tk.BooleanVar(value=False) for label in extras}
        for label, variable in extra_vars.items():
            ttk.Checkbutton(panel, text=label, variable=variable).pack(anchor="w")
        ttk.Label(panel, text="Order preferences").pack(anchor="w", pady=(12, 2))
        preferences = _preferences_for_product(product)
        preference_vars = {preference: tk.BooleanVar(value=False) for preference in preferences}
        for preference, variable in preference_vars.items():
            ttk.Checkbutton(panel, text=preference, variable=variable).pack(anchor="w")
        ttk.Label(panel, text="Other ingredient requests").pack(anchor="w", pady=(8, 2))
        exclusions = ttk.Entry(panel, width=42)
        exclusions.insert(0, "e.g. sauce on the side, no mushrooms")
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
            chosen.extend(
                preference for preference, variable in preference_vars.items() if variable.get()
            )
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
        size_popup(dialog, self, 720, 760, min_width=620, min_height=620)

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
        if self.order_type is None:
            self._choose_order_type(on_selected=self._preview_order)
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
        brand_name = getattr(self.winfo_toplevel(), "restaurant_name", "BITEBYTE")
        brand_tagline = getattr(self.winfo_toplevel(), "brand_tagline", "Crave It. Click It. Bite It.")
        ttk.Label(panel, text=brand_name, font=("Consolas", 15, "bold")).pack()
        ttk.Label(panel, text=brand_tagline, font=("Consolas", 10)).pack(pady=(2, 5))
        ttk.Label(panel, text="DIGITAL ORDER SLIP", font=("Consolas", 11)).pack(pady=(0, 10))
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
        size_popup(dialog, self, 620, 640, min_width=540, min_height=560)

    def _confirm_reset(self) -> None:
        if not self.cart or messagebox.askyesno("Start over", "Clear your cart and start over?", parent=self):
            self._build_welcome()

    def destroy(self) -> None:
        """Stop playback when the app switches away from the customer kiosk."""
        music = getattr(self, "_music", None)
        if music is not None:
            music.close()
        super().destroy()







