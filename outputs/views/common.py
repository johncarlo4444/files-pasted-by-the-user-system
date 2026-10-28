"""Small shared helpers for Tkinter views."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from tkinter import messagebox


def php(value: object) -> str:
    amount = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"₱{amount:,.2f}"


def show_error(error: Exception, title: str = "Unable to complete action") -> None:
    messagebox.showerror(title, str(error))


def size_popup(
    window,
    parent,
    width: int,
    height: int,
    *,
    min_width: int | None = None,
    min_height: int | None = None,
    resizable: bool = True,
) -> None:
    """Size a popup generously, keep it on-screen, and center it over its owner."""
    window.update_idletasks()
    owner = parent.winfo_toplevel()
    owner.update_idletasks()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    width = min(width, max(320, screen_width - 48))
    height = min(height, max(280, screen_height - 88))

    owner_width = max(owner.winfo_width(), width)
    owner_height = max(owner.winfo_height(), height)
    x = owner.winfo_rootx() + (owner_width - width) // 2
    y = owner.winfo_rooty() + (owner_height - height) // 2
    x = max(24, min(x, screen_width - width - 24))
    y = max(24, min(y, screen_height - height - 48))

    window.geometry(f"{width}x{height}+{x}+{y}")
    window.minsize(min(min_width or width, width), min(min_height or height, height))
    window.resizable(resizable, resizable)


def clear_frame(frame) -> None:
    for child in frame.winfo_children():
        child.destroy()


def enable_mousewheel_scrolling(canvas, *, axis: str = "y") -> None:
    """Route wheel input from a canvas or any of its child widgets to that canvas."""
    if axis not in ("x", "y", "both"):
        raise ValueError("Scroll axis must be 'x', 'y', or 'both'.")
    root = canvas.winfo_toplevel()
    registry = getattr(root, "_mousewheel_canvases", None)
    if registry is None:
        registry = {}
        root._mousewheel_canvases = registry

        def scroll_under_pointer(event):
            hovered = root.winfo_containing(event.x_root, event.y_root)
            target = None
            while hovered is not None:
                registered = registry.get(str(hovered))
                if registered:
                    target = registered
                    break
                parent_path = hovered.winfo_parent()
                if not parent_path:
                    break
                try:
                    hovered = root.nametowidget(parent_path)
                except KeyError:
                    break
            if target is None:
                return None
            widget, target_axis = target
            if not widget.winfo_exists():
                registry.pop(str(widget), None)
                return None
            if getattr(event, "num", None) == 4:
                units = -1
            elif getattr(event, "num", None) == 5:
                units = 1
            else:
                delta = int(getattr(event, "delta", 0) or 0)
                units = -int(delta / 120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)
            horizontal = target_axis == "x" or (
                target_axis == "both" and bool(getattr(event, "state", 0) & 0x0001)
            )
            widget.xview_scroll(units, "units") if horizontal else widget.yview_scroll(units, "units")
            return "break"

        root.bind_all("<MouseWheel>", scroll_under_pointer, add="+")
        root.bind_all("<Button-4>", scroll_under_pointer, add="+")
        root.bind_all("<Button-5>", scroll_under_pointer, add="+")

    registry[str(canvas)] = (canvas, axis)

    def unregister(event, widget_path=str(canvas)):
        if event.widget is canvas:
            registry.pop(widget_path, None)

    canvas.bind("<Destroy>", unregister, add="+")
