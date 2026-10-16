"""
widgets.py
Reusable GUI parts with hover effects and animations:
    HoverButton, Badge, Card, StatCard, StyledEntry, StyledText, DataTable, Pager,
    ScrollFrame, Toast, Modal, Sidebar,
    AnimatedBarChart, AnimatedDonutChart, AnimatedLineChart, AnimatedRankList
"""
import math
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from theme import (C, CATEGORY_COLORS, FONT, PALETTE, STATUS_STYLES, animate, bg_of,
                   clamp, darken, ease_in_out, ease_out_back, ease_out_cubic, ellipsize, font,
                   lerp_color, lighten, linear, rounded_points, rounded_rect, stop)

def setup_styles(root):
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TCombobox", fieldbackground=C.WHITE, background=C.WHITE, foreground=C.TEXT,
                    bordercolor=C.BORDER, lightcolor=C.BORDER, darkcolor=C.BORDER,
                    arrowcolor=C.BLUE, padding=7, relief="flat")
    style.map("TCombobox",
              fieldbackground=[("readonly", C.WHITE)],
              foreground=[("readonly", C.TEXT)],
              bordercolor=[("focus", C.BLUE), ("active", "#9DB8E8")],
              lightcolor=[("focus", C.BLUE)], darkcolor=[("focus", C.BLUE)],
              selectbackground=[("readonly", C.WHITE)], selectforeground=[("readonly", C.TEXT)],
              arrowcolor=[("active", C.BLUE_DARK)])
    root.option_add("*TCombobox*Listbox.background", C.WHITE)
    root.option_add("*TCombobox*Listbox.foreground", C.TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", C.BLUE)
    root.option_add("*TCombobox*Listbox.selectForeground", C.WHITE)
    root.option_add("*TCombobox*Listbox.font", font(10))

    style.layout("Slim.Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {
        "sticky": "ns", "children": [("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
    style.configure("Slim.Vertical.TScrollbar", troughcolor=C.BG, background="#C3CEE4",
                    bordercolor=C.BG, lightcolor="#C3CEE4", darkcolor="#C3CEE4", gripcount=0, width=8)
    style.map("Slim.Vertical.TScrollbar", background=[("active", "#9DB0D6")])


def make_combo(parent, values, width=18, value=None):
    box = ttk.Combobox(parent, values=values, state="readonly", width=width, font=font(10))
    if value is not None:
        box.set(value)
    box.bind("<<ComboboxSelected>>", lambda e: box.selection_clear(), add="+")
    return box


class HoverArea:
    """Calls on_enter / on_leave when the mouse enters or leaves a widget (children included)."""

    def __init__(self, widget, on_enter, on_leave):
        self.widget, self.on_enter, self.on_leave = widget, on_enter, on_leave
        self.inside = False
        self._bind(widget)

    def _bind(self, w):
        w.bind("<Enter>", self._enter, add="+")
        w.bind("<Leave>", self._leave, add="+")
        for child in w.winfo_children():
            self._bind(child)

    def _enter(self, _e):
        if not self.inside:
            self.inside = True
            self.on_enter()

    def _leave(self, _e):
        try:
            self.widget.after(25, self._check)
        except tk.TclError:
            pass

    def _check(self):
        try:
            if not self.widget.winfo_exists():
                return
            x, y = self.widget.winfo_pointerxy()
            x0, y0 = self.widget.winfo_rootx(), self.widget.winfo_rooty()
            inside = x0 <= x < x0 + self.widget.winfo_width() and y0 <= y < y0 + self.widget.winfo_height()
        except tk.TclError:
            return
        if self.inside and not inside:
            self.inside = False
            self.on_leave()


def set_bg_tree(widget, color):
    """Change the background of a widget and everything inside it."""
    try:
        widget.configure(bg=color)
    except tk.TclError:
        pass
    for child in widget.winfo_children():
        set_bg_tree(child, color)

BUTTON_STYLES = {
    "primary": dict(bg=C.BLUE, hover="#3D8BFF", press=C.BLUE_DARK, fg="#FFFFFF"),
    "success": dict(bg=C.GREEN, hover="#2BC789", press="#148A5C", fg="#FFFFFF"),
    "danger": dict(bg=C.RED, hover="#F26469", press="#C23B40", fg="#FFFFFF"),
    "outline": dict(bg=C.WHITE, hover=C.BLUE_SOFT, press="#CFE0FF", fg=C.BLUE, border=C.BLUE),
    "gray": dict(bg="#EEF2F9", hover="#E0E7F4", press="#CFD8EA", fg=C.TEXT),
    "soft": dict(bg=C.BLUE_SOFT, hover="#CFE1FF", press="#B9D3FF", fg=C.BLUE),
    "soft_red": dict(bg=C.RED_SOFT, hover="#FBCFCF", press="#F7B7B7", fg="#C23B40"),
    "soft_green": dict(bg=C.GREEN_SOFT, hover="#C5F0DA", press="#AEE6C9", fg="#168A5C"),
    "soft_orange": dict(bg=C.ORANGE_SOFT, hover="#FFE5B0", press="#FFD98A", fg="#B7791F"),
}


class HoverButton(tk.Canvas):
    """A rounded button. The color fades smoothly when the mouse is over it."""

    def __init__(self, master, text, command=None, style="primary", width=None, height=38,
                 radius=10, size=10, pad=36):
        self._style = BUTTON_STYLES[style]
        self._font = tkfont.Font(family=FONT, size=size, weight="bold")
        w = width or self._font.measure(text) + pad
        super().__init__(master, width=w, height=height, bg=bg_of(master), highlightthickness=0,
                         bd=0, cursor="hand2")
        self._text, self._cmd, self._radius = text, command, radius
        self._bw, self._bh = w, height
        self._color = self._style["bg"]
        self._anim = None
        self._enabled = True
        self._shape = rounded_rect(self, 1, 1, w - 1, height - 1, radius, fill=self._color,
                                   outline=self._style.get("border", self._color), width=1.5)
        self._label = self.create_text(w / 2, height / 2, text=text, font=self._font,
                                       fill=self._style["fg"])
        self.bind("<Enter>", lambda e: self._fade(self._style["hover"]))
        self.bind("<Leave>", lambda e: self._fade(self._style["bg"]))
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Configure>", self._resize)

    def _resize(self, e):
        self._bw, self._bh = e.width, e.height
        self.coords(self._shape, *rounded_points(1, 1, e.width - 1, e.height - 1,
                                                 min(self._radius, e.height / 2)))
        self.coords(self._label, e.width / 2, e.height / 2)

    def _fade(self, target):
        if not self._enabled:
            return
        stop(self._anim)
        start = self._color

        def step(t):
            self._color = lerp_color(start, target, t)
            self.itemconfigure(self._shape, fill=self._color)
        self._anim = animate(self, 150, step, ease=linear)

    def _press(self, _e):
        if not self._enabled:
            return
        stop(self._anim)
        self._color = self._style["press"]
        self.itemconfigure(self._shape, fill=self._color)
        self.coords(self._label, self._bw / 2, self._bh / 2 + 1)

    def _release(self, e):
        if not self._enabled:
            return
        self.coords(self._label, self._bw / 2, self._bh / 2)
        inside = 0 <= e.x <= self._bw and 0 <= e.y <= self._bh
        self._fade(self._style["hover"] if inside else self._style["bg"])
        if inside and self._cmd:
            self._cmd()

    def set_text(self, text):
        self._text = text
        self.itemconfigure(self._label, text=text)

    def set_style(self, style):
        """Change the look (for example: active tab / inactive tab) with a smooth fade."""
        old = self._color
        self._style = BUTTON_STYLES[style]
        stop(self._anim)
        self.itemconfigure(self._label, fill=self._style["fg"])
        self.itemconfigure(self._shape, outline=self._style.get("border", self._style["bg"]))
        target = self._style["bg"]

        def step(t):
            self._color = lerp_color(old, target, t)
            self.itemconfigure(self._shape, fill=self._color)
        self._anim = animate(self, 220, step, ease=linear)

    def set_enabled(self, enabled):
        self._enabled = enabled
        stop(self._anim)
        if enabled:
            self._color = self._style["bg"]
            self.itemconfigure(self._label, fill=self._style["fg"])
            self.configure(cursor="hand2")
        else:
            self._color = "#C9D2E3"
            self.itemconfigure(self._label, fill="#FFFFFF")
            self.configure(cursor="arrow")
        self.itemconfigure(self._shape, fill=self._color,
                           outline=self._color if not enabled else self._style.get("border", self._color))

    def flash(self, color=C.GREEN, text=None, ms=900):
        """Quick color flash after a success (used after Submit)."""
        old_text = self._text
        if text:
            self.set_text(text)
        stop(self._anim)
        self.itemconfigure(self._shape, fill=color, outline=color)
        self.after(ms, self._unflash)
        self._old_text = old_text

    def _unflash(self):
        try:
            self.set_text(self._old_text)
            self._color = self._style["bg"]
            self.itemconfigure(self._shape, fill=self._color,
                               outline=self._style.get("border", self._color))
        except tk.TclError:
            pass


class Badge(tk.Canvas):
    """Small rounded label like 'Pending' or 'Resolved'."""
    _font = None

    def __init__(self, master, text, bg_color=None, fg_color=None, height=24, size=9):
        if Badge._font is None:
            Badge._font = tkfont.Font(family=FONT, size=size, weight="bold")
        default = STATUS_STYLES.get(text, (C.BLUE_SOFT, C.BLUE))
        bg_color, fg_color = bg_color or default[0], fg_color or default[1]
        w = Badge._font.measure(text) + 26
        super().__init__(master, width=w, height=height, bg=bg_of(master), highlightthickness=0, bd=0)
        rounded_rect(self, 0, 0, w, height, height / 2, fill=bg_color, outline="")
        self.create_text(w / 2, height / 2, text=text, fill=fg_color, font=Badge._font)


def category_badge(master, category):
    color = CATEGORY_COLORS.get(category, C.BLUE)
    return Badge(master, category, bg_color=lighten(color, 0.82), fg_color=darken(color, 0.25))


class LinkLabel(tk.Label):
    """Blue text that gets an underline when the mouse is over it."""

    def __init__(self, master, text, command=None, size=9):
        super().__init__(master, text=text, fg=C.BLUE, bg=bg_of(master), font=font(size, "bold"),
                         cursor="hand2")
        self._normal, self._under = font(size, "bold"), (FONT, size, "bold underline")
        self.bind("<Enter>", lambda e: self.configure(font=self._under, fg=C.BLUE_DARK))
        self.bind("<Leave>", lambda e: self.configure(font=self._normal, fg=C.BLUE))
        if command:
            self.bind("<Button-1>", lambda e: command())


# ======================================================================
#  Cards
# ======================================================================
class Card(tk.Frame):
    """White box with a border that lights up when the mouse is over it."""

    def __init__(self, master, accent=C.BLUE, pad=18, hover=True, bg=C.WHITE):
        super().__init__(master, bg=bg, highlightthickness=2, highlightbackground=C.CARD_BORDER)
        self.accent, self._anim, self._border = accent, None, C.CARD_BORDER
        self.body = tk.Frame(self, bg=bg)
        self.body.pack(fill="both", expand=True, padx=pad, pady=pad)
        if hover:
            self.after_idle(lambda: HoverArea(self, lambda: self._glow(self.accent),
                                              lambda: self._glow(C.CARD_BORDER)))

    def _glow(self, target):
        stop(self._anim)
        start = self._border

        def step(t):
            self._border = lerp_color(start, target, t)
            self.configure(highlightbackground=self._border)
        self._anim = animate(self, 200, step)


class StatCard(Card):
    """Number card with an icon. The number counts up when it appears."""

    def __init__(self, master, label, glyph, color, soft_color, delay=0):
        super().__init__(master, accent=color, pad=16)
        self._shown, self._anim_num, self._delay = 0, None, delay
        icon = tk.Canvas(self.body, width=46, height=46, bg=C.WHITE, highlightthickness=0)
        rounded_rect(icon, 1, 1, 45, 45, 14, fill=soft_color, outline="")
        icon.create_text(23, 23, text=glyph, fill=color, font=font(17, "bold"))
        icon.pack(anchor="w")
        tk.Label(self.body, text=label, bg=C.WHITE, fg=C.MUTED, font=font(9, "bold")).pack(anchor="w", pady=(10, 0))
        self.number = tk.Label(self.body, text="0", bg=C.WHITE, fg=C.TEXT, font=font(24, "bold"))
        self.number.pack(anchor="w")

    def set_value(self, value):
        stop(self._anim_num)
        start, delay = self._shown, self._delay
        self._delay = 0

        def step(t):
            self._shown = start + (value - start) * t
            self.number.configure(text=str(int(round(self._shown))))
        self._anim_num = animate(self, 900, step, delay=delay)


# ======================================================================
#  Inputs
# ======================================================================
class StyledEntry(tk.Entry):
    """Entry with placeholder text, hover color and a blue glow when focused."""

    def __init__(self, master, placeholder="", password=False, width=30, size=10):
        super().__init__(master, relief="flat", bg=C.WHITE, fg=C.TEXT, insertbackground=C.BLUE,
                         highlightthickness=2, highlightbackground=C.BORDER, highlightcolor=C.BLUE,
                         font=font(size), width=width, bd=6)
        self._placeholder, self._password = placeholder, password
        self._has_ph, self._anim, self._focused = False, None, False
        self._show_placeholder()
        self.bind("<FocusIn>", self._focus_in)
        self.bind("<FocusOut>", self._focus_out)
        self.bind("<Enter>", lambda e: self._hover("#9DB8E8"))
        self.bind("<Leave>", lambda e: self._hover(C.BORDER))

    def _hover(self, color):
        if not self._focused:
            stop(self._anim)
            start = self.cget("highlightbackground")
            self._anim = animate(self, 140, lambda t: self.configure(
                highlightbackground=lerp_color(start, color, t)), ease=linear)

    def _focus_in(self, _e):
        self._focused = True
        stop(self._anim)
        self.configure(highlightcolor=C.BORDER)
        self._anim = animate(self, 180, lambda t: self.configure(
            highlightcolor=lerp_color(C.BORDER, C.BLUE, t)), ease=linear)
        if self._has_ph:
            self.delete(0, "end")
            self._has_ph = False
            self.configure(fg=C.TEXT, show="\u25CF" if self._password else "")

    def _focus_out(self, _e):
        self._focused = False
        self.configure(highlightbackground=C.BORDER)
        self._show_placeholder()

    def _show_placeholder(self):
        if self._placeholder and not super().get():
            self._has_ph = True
            self.configure(fg="#9AA6BE", show="")
            self.insert(0, self._placeholder)

    def value(self, strip=True):
        if self._has_ph:
            return ""
        text = super().get()
        return text.strip() if strip else text

    def set_value(self, text):
        if self._has_ph:
            self.delete(0, "end")
            self._has_ph = False
            self.configure(fg=C.TEXT, show="\u25CF" if self._password else "")
        self.delete(0, "end")
        self.insert(0, text)

    def clear(self):
        self.delete(0, "end")
        self._has_ph = False
        self.configure(fg=C.TEXT, show="\u25CF" if self._password else "")
        if not self._focused:
            self._show_placeholder()

    def set_password_visible(self, visible):
        self._password = not visible
        if not self._has_ph:
            self.configure(show="" if visible else "\u25CF")


class StyledText(tk.Frame):
    """Multi-line text box with a character counter (0/500)."""

    def __init__(self, master, height=7, limit=500, placeholder="", bg=C.WHITE):
        super().__init__(master, bg=bg)
        self.limit = limit
        self.text = tk.Text(self, height=height, wrap="word", relief="flat", bg=C.WHITE, fg=C.TEXT,
                            font=font(10), highlightthickness=2, highlightbackground=C.BORDER,
                            highlightcolor=C.BLUE, bd=8, insertbackground=C.BLUE, undo=True)
        self.text.pack(fill="both", expand=True)
        self.counter = tk.Label(self, text=f"0/{limit}", bg=bg, fg=C.MUTED, font=font(8))
        self.counter.pack(anchor="e", pady=(3, 0))
        self._hint = tk.Label(self.text, text=placeholder, bg=C.WHITE, fg="#9AA6BE", font=font(10),
                              cursor="xterm", justify="left", wraplength=420)
        self._hint.bind("<Button-1>", lambda e: self.text.focus_set())
        self.text.bind("<Key>", lambda e: self.after_idle(self._changed))
        self.text.bind("<<Paste>>", lambda e: self.after_idle(self._changed))
        self.text.bind("<<Cut>>", lambda e: self.after_idle(self._changed))
        self.text.bind("<Enter>", lambda e: self.text.configure(highlightbackground="#9DB8E8"))
        self.text.bind("<Leave>", lambda e: self.text.configure(highlightbackground=C.BORDER))
        self._changed()

    def _changed(self):
        content = self.text.get("1.0", "end-1c")
        if len(content) > self.limit:
            self.text.delete(f"1.0+{self.limit}c", "end")
            content = content[:self.limit]
        n = len(content)
        self.counter.configure(text=f"{n}/{self.limit}", fg=C.RED if n >= self.limit else C.MUTED)
        if self._hint.cget("text") and not content:
            self._hint.place(x=10, y=8)
        else:
            self._hint.place_forget()

    def value(self):
        return self.text.get("1.0", "end-1c").strip()

    def set_value(self, text):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self._changed()

    def clear(self):
        self.set_value("")


def form_label(parent, text, required=False, bg=C.WHITE):
    row = tk.Frame(parent, bg=bg)
    tk.Label(row, text=text, bg=bg, fg=C.TEXT, font=font(10, "bold")).pack(side="left")
    if required:
        tk.Label(row, text=" *", bg=bg, fg=C.RED, font=font(10, "bold")).pack(side="left")
    return row


# ======================================================================
#  Scrolling page
# ======================================================================
class ScrollFrame(tk.Frame):
    """A frame that scrolls with the mouse wheel when the content is taller than the window."""

    def __init__(self, master, bg=C.BG):
        super().__init__(master, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview,
                                 style="Slim.Vertical.TScrollbar")
        self.canvas.configure(yscrollcommand=self._on_scroll)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self._fit())
        self.canvas.bind("<Configure>", lambda e: self._fit())

    def _fit(self):
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        need = self.inner.winfo_reqheight()
        self.canvas.itemconfigure(self._win, width=w, height=max(need, h))
        self.canvas.configure(scrollregion=(0, 0, w, max(need, h)))
        if need > h + 1:
            self.bar.place(relx=1.0, rely=0, relheight=1.0, anchor="ne", width=9)
        else:
            self.bar.place_forget()
            self.canvas.yview_moveto(0)

    def _on_scroll(self, first, last):
        self.bar.set(first, last)

    def scroll(self, units):
        if self.inner.winfo_reqheight() > self.canvas.winfo_height() + 1:
            self.canvas.yview_scroll(units, "units")


def wheel_units(event):
    if event.num == 4:
        return -2
    if event.num == 5:
        return 2
    if sys.platform == "darwin":
        return -int(event.delta)
    return -2 if event.delta > 0 else 2


def find_scroll_parent(widget):
    while widget is not None:
        if isinstance(widget, ScrollFrame):
            return widget
        widget = getattr(widget, "master", None)
    return None


# ======================================================================
#  Pager + DataTable
# ======================================================================
class Pager(tk.Frame):
    def __init__(self, master, on_change, bg=C.WHITE):
        super().__init__(master, bg=bg)
        self.on_change = on_change
        self.info = tk.Label(self, text="", bg=bg, fg=C.MUTED, font=font(9))
        self.info.pack(side="left")
        self.next_btn = HoverButton(self, "\u203A", lambda: self._go(1), "soft", width=34, height=28, size=11)
        self.next_btn.pack(side="right")
        self.page_lbl = tk.Label(self, text="", bg=bg, fg=C.TEXT, font=font(9, "bold"))
        self.page_lbl.pack(side="right", padx=8)
        self.prev_btn = HoverButton(self, "\u2039", lambda: self._go(-1), "soft", width=34, height=28, size=11)
        self.prev_btn.pack(side="right")
        self.page = self.pages = 0

    def update_state(self, page, page_size, total):
        self.pages = max(1, math.ceil(total / page_size))
        self.page = min(page, self.pages - 1)
        first = 0 if total == 0 else self.page * page_size + 1
        last = min(total, (self.page + 1) * page_size)
        self.info.configure(text=f"Showing {first}-{last} of {total}")
        self.page_lbl.configure(text=f"{self.page + 1} / {self.pages}")
        self.prev_btn.set_enabled(self.page > 0)
        self.next_btn.set_enabled(self.page < self.pages - 1)

    def _go(self, step):
        new = self.page + step
        if 0 <= new < self.pages:
            self.on_change(new)


class Column:
    """width = wanted width in pixels (columns grow or shrink together in the same proportion)."""

    def __init__(self, title, key, width=100, kind="text"):
        self.title, self.key, self.width, self.kind = title, key, width, kind


class DataTable(tk.Frame):
    """
    Table with hover rows, status badges, action buttons and pages.
    set_rows() takes a list of dicts:  {"cells": {key: value}, "actions": [(text, style, command)]}
    """

    def __init__(self, master, columns, page_size=6, row_height=46, footer=True,
                 empty_text="Nothing to show yet."):
        super().__init__(master, bg=C.WHITE)
        self.columns, self.page_size, self.row_height = columns, page_size, row_height
        self.empty_text, self.rows, self.page = empty_text, [], 0
        self._reveal_jobs = []
        self._fonts = {"normal": tkfont.Font(family=FONT, size=10),
                       "bold": tkfont.Font(family=FONT, size=10, weight="bold")}
        header = tk.Frame(self, bg="#F5F8FD")
        header.pack(fill="x")
        self._grid_columns(header)
        for i, col in enumerate(columns):
            tk.Label(header, text=col.title, bg="#F5F8FD", fg=C.MUTED, font=font(9, "bold"),
                     anchor="w").grid(row=0, column=i, sticky="w", padx=10, pady=9)
        self.body = tk.Frame(self, bg=C.WHITE, height=(row_height + 1) * page_size)
        self.body.pack(fill="x")
        self.body.pack_propagate(False)
        self.pager = Pager(self, self._change_page) if footer else None
        if self.pager:
            self.pager.pack(fill="x", pady=(10, 0))

    def _grid_columns(self, frame):
        for i, col in enumerate(self.columns):
            frame.grid_columnconfigure(i, weight=int(col.width), uniform="col")

    def set_rows(self, rows, keep_page=False, animate_rows=True):
        self.rows = rows
        if not keep_page:
            self.page = 0
        self._render(animate_rows and not keep_page)

    def _change_page(self, page):
        self.page = page
        self._render(True)

    def _render(self, animate_rows):
        for job in self._reveal_jobs:
            try:
                self.after_cancel(job)
            except (ValueError, tk.TclError):
                pass
        self._reveal_jobs = []
        for child in self.body.winfo_children():
            child.destroy()
        total = len(self.rows)
        pages = max(1, math.ceil(total / self.page_size))
        self.page = min(self.page, pages - 1)
        chunk = self.rows[self.page * self.page_size:(self.page + 1) * self.page_size]
        if self.pager:
            self.pager.update_state(self.page, self.page_size, total)
        if not chunk:
            tk.Label(self.body, text=self.empty_text, bg=C.WHITE, fg=C.MUTED,
                     font=font(10)).pack(pady=40)
            return
        for i, row in enumerate(chunk):
            frame = self._make_row(row)
            if animate_rows:
                self._reveal_jobs.append(self.after(i * 45, lambda f=frame: self._show(f)))
            else:
                self._show(frame)

    @staticmethod
    def _show(frame):
        try:
            frame.pack(fill="x")
        except tk.TclError:
            pass

    def _make_row(self, row):
        outer = tk.Frame(self.body, bg=C.WHITE)
        frame = tk.Frame(outer, bg=C.WHITE, height=self.row_height)
        frame.pack(fill="x")
        frame.grid_propagate(False)
        frame.grid_rowconfigure(0, weight=1)
        self._grid_columns(frame)
        texts = []
        for i, col in enumerate(self.columns):
            self._make_cell(frame, i, col, row, texts)
        frame.bind("<Configure>", lambda e: self._fit_texts(e.width, texts))
        tk.Frame(outer, bg="#EDF1F8", height=1).pack(fill="x")
        HoverArea(frame, lambda f=frame: self._tint(f, C.ROW_HOVER), lambda f=frame: self._tint(f, C.WHITE))
        return outer

    def _make_cell(self, frame, i, col, row, texts):
        value = row["cells"].get(col.key, "") if col.key else ""
        if col.kind == "actions":
            box = tk.Frame(frame, bg=C.WHITE)
            for text, style, command in row.get("actions", []):
                HoverButton(box, text, command, style, height=28, radius=8, size=9, pad=24).pack(side="left", padx=(0, 6))
            box.grid(row=0, column=i, sticky="w", padx=10)
        elif col.kind == "badge":
            Badge(frame, str(value)).grid(row=0, column=i, sticky="w", padx=10)
        elif col.kind == "category":
            category_badge(frame, str(value)).grid(row=0, column=i, sticky="w", padx=10)
        elif col.kind == "votes":
            tk.Label(frame, text=f"\u25B2 {value}" if value != "" else "\u2014", bg=C.WHITE,
                     fg=C.PURPLE if value != "" else C.MUTED, font=font(10, "bold"),
                     anchor="w").grid(row=0, column=i, sticky="w", padx=10)
        else:
            weight = "bold" if col.kind == "title" else "normal"
            color = C.MUTED if col.kind == "id" else C.TEXT
            lbl = tk.Label(frame, text=str(value), bg=C.WHITE, fg=color, font=font(10, weight),
                           anchor="w", width=1)
            lbl.grid(row=0, column=i, sticky="we", padx=10)
            texts.append((lbl, str(value), col.width, self._fonts["bold" if weight == "bold" else "normal"]))

    def _fit_texts(self, frame_width, texts):
        """Cut long texts with '...' so they fit inside their column."""
        total = sum(c.width for c in self.columns)
        for lbl, full, col_width, fnt in texts:
            room = frame_width * col_width / total - 22
            try:
                lbl.configure(text=ellipsize(full, fnt, max(20, room)))
            except tk.TclError:
                pass

    def _tint(self, frame, color):
        try:
            set_bg_tree(frame, color)
        except tk.TclError:
            pass


# ======================================================================
#  Toast (small message that slides in)
# ======================================================================
class Toast:
    COLORS = {"success": (C.GREEN, "\u2713"), "error": (C.RED, "\u2715"),
              "info": (C.BLUE, "\u2139"), "warning": (C.ORANGE, "!")}

    def __init__(self, root):
        self.root, self.frame, self._anim, self._job = root, None, None, None

    def show(self, message, kind="success", duration=2800):
        self._clear()
        color, icon = self.COLORS.get(kind, self.COLORS["info"])
        f = tk.Frame(self.root, bg=C.WHITE, highlightthickness=1, highlightbackground=C.BORDER)
        tk.Frame(f, bg=color, width=6).pack(side="left", fill="y")
        tk.Label(f, text=icon, bg=color, fg="white", font=font(10, "bold"), width=3).pack(side="left", fill="y")
        tk.Label(f, text=message, bg=C.WHITE, fg=C.TEXT, font=font(10), wraplength=330,
                 justify="left").pack(side="left", padx=14, pady=12)
        f.update_idletasks()
        w = f.winfo_reqwidth()
        f.place(relx=1.0, x=0, y=20, anchor="ne")
        f.lift()
        self.frame = f
        self._anim = animate(f, 420, lambda t: f.place_configure(x=(1 - t) * (w + 30) - 20),
                             ease=ease_out_back)
        self._job = self.root.after(duration, lambda: self._leave(f, w))

    def _leave(self, f, w):
        try:
            if f is not self.frame or not f.winfo_exists():
                return
            animate(f, 300, lambda t: f.place_configure(x=-20 + t * (w + 40)),
                    done=lambda: self._destroy(f), ease=ease_in_out)
        except tk.TclError:
            pass

    @staticmethod
    def _destroy(f):
        try:
            f.destroy()
        except tk.TclError:
            pass

    def _clear(self):
        if self._job:
            try:
                self.root.after_cancel(self._job)
            except (ValueError, tk.TclError):
                pass
        stop(self._anim)
        if self.frame is not None:
            self._destroy(self.frame)
            self.frame = None


# ======================================================================
#  Modal window
# ======================================================================
class Modal(tk.Toplevel):
    def __init__(self, root, title, width=520, accent=C.BLUE):
        super().__init__(root)
        self.withdraw()
        self.root = root
        self.title(title)
        self.configure(bg=C.WHITE)
        self.resizable(False, False)
        self.transient(root)
        self._width = width
        tk.Frame(self, bg=accent, height=5).pack(fill="x")
        tk.Label(self, text=title, bg=C.WHITE, fg=C.TEXT, font=font(14, "bold")).pack(anchor="w", padx=26, pady=(18, 4))
        self.body = tk.Frame(self, bg=C.WHITE)
        self.body.pack(fill="both", expand=True, padx=26, pady=(6, 4))
        self.footer = tk.Frame(self, bg=C.WHITE)
        self.footer.pack(fill="x", padx=26, pady=(8, 22))
        self.bind("<Escape>", lambda e: self.close())

    def show(self):
        self.update_idletasks()
        w = self._width
        h = self.winfo_reqheight()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - h) // 3
        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        try:
            self.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        self.deiconify()
        try:
            self.wait_visibility()
            self.grab_set()
            animate(self, 220, lambda t: self.attributes("-alpha", t))
        except tk.TclError:
            pass
        self.focus_set()

    def close(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


def confirm(root, title, message, on_yes, yes_text="Yes, delete", style="danger"):
    m = Modal(root, title, width=440, accent=C.RED if style == "danger" else C.BLUE)
    tk.Label(m.body, text=message, bg=C.WHITE, fg=C.MUTED, font=font(10), wraplength=380,
             justify="left").pack(anchor="w")
    HoverButton(m.footer, yes_text, lambda: (m.close(), on_yes()), style).pack(side="right")
    HoverButton(m.footer, "Cancel", m.close, "gray").pack(side="right", padx=8)
    m.show()


# ======================================================================
#  Sidebar
# ======================================================================
class NavItem(tk.Canvas):
    def __init__(self, master, key, label, icon, command, width=232):
        super().__init__(master, width=width, height=46, bg=C.NAVY, highlightthickness=0, bd=0,
                         cursor="hand2")
        self.key, self.command, self.active = key, command, False
        self._fill, self._text, self._shift, self._anim = C.NAVY, "#C5D5F5", 0.0, None
        self._bar = 0.0
        self._bw = width
        self._shape = rounded_rect(self, 12, 3, width - 12, 43, 12, fill=C.NAVY, outline="")
        self._accent = self.create_rectangle(12, 14, 12, 32, fill="white", outline="", state="hidden")
        self._icon = self.create_text(38, 23, text=icon, fill=self._text, font=font(13))
        self._label = self.create_text(62, 23, text=label, fill=self._text, font=font(10, "bold"), anchor="w")
        self.bind("<Enter>", lambda e: self._go(C.NAVY_HOVER if not self.active else C.BLUE, "#FFFFFF", 5))
        self.bind("<Leave>", lambda e: self._go(self._rest_fill(), self._rest_text(), 0))
        self.bind("<Button-1>", lambda e: self.command(self.key))
        self.bind("<Configure>", self._resize)

    def _rest_fill(self):
        return C.BLUE if self.active else C.NAVY

    def _rest_text(self):
        return "#FFFFFF" if self.active else "#C5D5F5"

    def _resize(self, e):
        self._bw = e.width
        self.coords(self._shape, *rounded_points(12, 3, e.width - 12, 43, 12))

    def _go(self, fill, text, shift):
        stop(self._anim)
        f0, t0, s0 = self._fill, self._text, self._shift

        def step(t):
            self._fill, self._text = lerp_color(f0, fill, t), lerp_color(t0, text, t)
            self._shift = s0 + (shift - s0) * t
            self.itemconfigure(self._shape, fill=self._fill)
            self.itemconfigure(self._icon, fill=self._text)
            self.itemconfigure(self._label, fill=self._text)
            self.coords(self._icon, 38 + self._shift, 23)
            self.coords(self._label, 62 + self._shift, 23)
        self._anim = animate(self, 170, step, ease=linear)

    def set_active(self, active):
        self.active = active
        self._go(self._rest_fill(), self._rest_text(), 0)
        start = self._bar
        target = 4.0 if active else 0.0

        def bar(t):
            self._bar = start + (target - start) * t
            self.coords(self._accent, 12, 14, 12 + self._bar, 32)
            self.itemconfigure(self._accent, state="normal" if self._bar > 0.6 else "hidden")
        animate(self, 260, bar, ease=ease_out_back)


class Sidebar(tk.Frame):
    def __init__(self, master, user, on_navigate, on_logout, width=232):
        super().__init__(master, bg=C.NAVY, width=width)
        self.pack_propagate(False)
        self.items = {}
        # --- profile block
        top = tk.Frame(self, bg=C.NAVY)
        top.pack(fill="x", padx=18, pady=(24, 18))
        avatar = tk.Canvas(top, width=44, height=44, bg=C.NAVY, highlightthickness=0)
        avatar.create_oval(1, 1, 43, 43, fill=C.BLUE, outline="#5B9BFF", width=2)
        avatar.create_text(22, 22, text=user.initial, fill="white", font=font(15, "bold"))
        avatar.pack(side="left")
        names = tk.Frame(top, bg=C.NAVY)
        names.pack(side="left", padx=11)
        tk.Label(names, text=user.role.capitalize(), bg=C.NAVY, fg="#8FB4F5", font=font(8, "bold")).pack(anchor="w")
        tk.Label(names, text=user.full_name if len(user.full_name) < 17 else user.full_name[:15] + "..",
                 bg=C.NAVY, fg="white", font=font(11, "bold")).pack(anchor="w")
        tk.Frame(self, bg=C.NAVY_HOVER, height=1).pack(fill="x", padx=18, pady=(0, 12))
        # --- menu
        for key, label, icon in user.menu_items():
            item = NavItem(self, key, label, icon, on_navigate, width)
            item.pack(fill="x", pady=1)
            self.items[key] = item
        # --- bottom: live sync + logout
        bottom = tk.Frame(self, bg=C.NAVY)
        bottom.pack(side="bottom", fill="x", pady=(0, 14))
        logout = NavItem(bottom, "logout", "Logout", "\u279C", lambda k: on_logout(), width)
        logout.pack(fill="x")
        live = tk.Frame(bottom, bg=C.NAVY)
        live.pack(fill="x", padx=24, pady=(10, 0))
        self.dot = tk.Canvas(live, width=16, height=16, bg=C.NAVY, highlightthickness=0)
        self.dot.pack(side="left")
        self._glow = self.dot.create_oval(2, 2, 14, 14, fill=C.NAVY_HOVER, outline="")
        self._core = self.dot.create_oval(5, 5, 11, 11, fill="#35E0A1", outline="")
        tk.Label(live, text="Live sync on", bg=C.NAVY, fg="#8FB4F5", font=font(8)).pack(side="left", padx=6)
        self._phase, self._flash = 0.0, 0
        self._pulse()

    def _pulse(self):
        try:
            self._phase += 0.12
            s = (math.sin(self._phase) + 1) / 2
            r = 3 + 4 * s
            self.dot.coords(self._glow, 8 - r, 8 - r, 8 + r, 8 + r)
            glow = lerp_color(C.NAVY, "#35E0A1" if self._flash == 0 else C.ORANGE, 0.35 * (1 - s) + 0.1)
            self.dot.itemconfigure(self._glow, fill=glow)
            self.dot.itemconfigure(self._core, fill="#35E0A1" if self._flash == 0 else C.ORANGE)
            if self._flash:
                self._flash -= 1
            self.after(40, self._pulse)
        except tk.TclError:
            pass

    def flash_sync(self):
        self._flash = 25

    def set_active(self, key):
        for k, item in self.items.items():
            if (k == key) != item.active:
                item.set_active(k == key)


# ======================================================================
#  Charts
# ======================================================================
def nice_step(max_value, steps=4):
    raw = max(1, math.ceil(max_value / steps))
    mag = 10 ** int(math.floor(math.log10(raw)))
    for m in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if raw <= m * mag:
            return int(math.ceil(m * mag))
    return raw


def draw_tooltip(canvas, x, y, text):
    w = canvas.winfo_width()
    t = canvas.create_text(0, 0, text=text, fill="white", font=font(9, "bold"), anchor="nw", justify="left")
    x1, y1, x2, y2 = canvas.bbox(t)
    tw, th = x2 - x1 + 22, y2 - y1 + 14
    px, py = x + 14, y - th - 10
    if px + tw > w - 4:
        px = x - tw - 14
    if py < 4:
        py = y + 18
    px = max(4, px)
    box = rounded_rect(canvas, px, py, px + tw, py + th, 9, fill=C.NAVY, outline="")
    canvas.coords(t, px + 11, py + 7)
    canvas.tag_raise(t, box)


class AnimatedBarChart(tk.Canvas):
    """Bars grow up one by one. Hover a bar to make it pop and show its number."""

    def __init__(self, master, height=240):
        super().__init__(master, height=height, bg=C.WHITE, highlightthickness=0)
        self.labels, self.values, self.colors = [], [], []
        self._shown, self._anim, self._hover, self._mouse, self._bars = [], None, None, (0, 0), []
        self.bind("<Configure>", lambda e: self._render())
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", self._leave)

    def set_data(self, labels, values, colors):
        old = list(self._shown) if len(self._shown) == len(values) else [0] * len(values)
        self.labels, self.values, self.colors = list(labels), list(values), list(colors)
        n = len(values)
        total = 650 + 90 * n
        stop(self._anim)

        def step(t):
            self._shown = [old[i] + (values[i] - old[i]) * ease_out_cubic(clamp((t * total - i * 90) / 650))
                           for i in range(n)]
            self._render()
        self._anim = animate(self, total, step, ease=linear)

    def _render(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        n = len(self.values)
        if w < 30 or h < 30:
            return
        if n == 0 or sum(self.values) == 0:
            self._bars = []
            self.create_text(w / 2, h / 2, text="No data yet", fill=C.MUTED, font=font(10))
            return
        shown = self._shown if len(self._shown) == n else self.values
        left, right, top, bottom = 38, 14, 26, 34
        pw, ph = w - left - right, h - top - bottom
        step_val = nice_step(max(self.values))
        top_val = step_val * 4
        for i in range(5):
            y = top + ph - ph * i / 4
            self.create_line(left, y, w - right, y, fill="#E8EDF6", dash=(3, 3) if i else ())
            self.create_text(left - 8, y, text=str(step_val * i), anchor="e", fill=C.MUTED, font=font(8))
        slot = pw / n
        bw = min(70, slot * 0.5)
        self._bars = []
        for i in range(n):
            cx = left + slot * (i + 0.5)
            hov = i == self._hover
            pad = 4 if hov else 0
            bh = ph * shown[i] / top_val
            y2, y1 = top + ph, top + ph - bh
            color = lighten(self.colors[i], 0.18) if hov else self.colors[i]
            if bh >= 1:
                r = min(9, bh / 2)
                rounded_rect(self, cx - bw / 2 - pad, y1 - pad, cx + bw / 2 + pad, y2, r, fill=color, outline="")
                if bh > r:
                    self.create_rectangle(cx - bw / 2 - pad, y2 - r, cx + bw / 2 + pad, y2, fill=color, outline="")
                self.create_text(cx, y1 - 12 - pad, text=str(int(round(shown[i]))), fill=C.TEXT, font=font(9, "bold"))
            self.create_text(cx, top + ph + 17, text=self.labels[i], fill=C.TEXT if hov else C.MUTED,
                             font=font(9, "bold" if hov else "normal"))
            self._bars.append((cx - slot / 2, cx + slot / 2))
        if self._hover is not None and self._hover < n:
            total = sum(self.values) or 1
            v = self.values[self._hover]
            draw_tooltip(self, self._mouse[0], self._mouse[1], f"{self.labels[self._hover]}\n{v}  ({v / total:.0%})")

    def _motion(self, e):
        idx = next((i for i, (a, b) in enumerate(self._bars) if a <= e.x <= b), None)
        self._mouse = (e.x, e.y)
        self.configure(cursor="hand2" if idx is not None else "")
        if idx is not None or self._hover is not None:
            self._hover = idx
            self._render()

    def _leave(self, _e):
        if self._hover is not None:
            self._hover = None
            self._render()


class AnimatedDonutChart(tk.Canvas):
    """Donut that sweeps around when it appears. Hover a slice (or its legend) to pull it out."""

    def __init__(self, master, height=240, legend=True):
        super().__init__(master, height=height, bg=C.WHITE, highlightthickness=0)
        self.legend = legend
        self.labels, self.values, self.colors = [], [], []
        self._progress, self._anim, self._hover = 1.0, None, None
        self._geo, self._rows = (0, 0, 0, 0), []
        self.bind("<Configure>", lambda e: self._render())
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", self._leave)

    def set_data(self, labels, values, colors):
        self.labels, self.values, self.colors = list(labels), list(values), list(colors)
        stop(self._anim)
        self._progress = 0.0

        def step(t):
            self._progress = t
            self._render()
        self._anim = animate(self, 1100, step, ease=ease_out_cubic)

    def _render(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        total = sum(self.values)
        if w < 60 or h < 60:
            return
        if total <= 0:
            self.create_text(w / 2, h / 2, text="No data yet", fill=C.MUTED, font=font(10))
            return
        legend_w = 200 if self.legend and w > 380 else 0
        area_w = w - legend_w
        R = max(30, min(h - 30, area_w - 30) / 2)
        cx, cy = area_w / 2, h / 2
        thick = R * 0.38
        self._geo = (cx, cy, R, thick)
        sweep = 360 * self._progress
        nonzero = sum(1 for v in self.values if v > 0)
        start = 0.0
        self._spans = []
        for i, v in enumerate(self.values):
            extent = v / total * 360
            self._spans.append((start, start + extent))
            hov = i == self._hover
            draw = max(0.0, min(extent, sweep - start))
            gap = 1.8 if nonzero > 1 else 0
            if draw - gap > 0.2:
                rr = R + (6 if hov else 0)
                mid = rr - thick / 2
                color = lighten(self.colors[i], 0.12) if hov else self.colors[i]
                self.create_arc(cx - mid, cy - mid, cx + mid, cy + mid, start=90 - (start + gap / 2),
                                extent=-min(draw - gap, 359.8), style="arc", outline=color,
                                width=thick + (4 if hov else 0))
            start += extent
        # center text
        if self._hover is not None and self.values[self._hover] > 0:
            v = self.values[self._hover]
            self.create_text(cx, cy - 16, text=self.labels[self._hover], fill=C.MUTED, font=font(9, "bold"))
            self.create_text(cx, cy + 4, text=str(v), fill=self.colors[self._hover], font=font(20, "bold"))
            self.create_text(cx, cy + 26, text=f"{v / total:.0%}", fill=C.MUTED, font=font(9))
        else:
            self.create_text(cx, cy - 6, text=str(int(round(total * self._progress))), fill=C.TEXT, font=font(22, "bold"))
            self.create_text(cx, cy + 18, text="Total", fill=C.MUTED, font=font(9))
        # legend
        self._rows = []
        if legend_w:
            n = len(self.labels)
            row_h = 28
            y = cy - n * row_h / 2
            for i, label in enumerate(self.labels):
                y1, y2 = y + i * row_h, y + (i + 1) * row_h
                self._rows.append((y1, y2))
                if i == self._hover:
                    rounded_rect(self, area_w + 2, y1 + 1, w - 6, y2 - 1, 8, fill=C.ROW_HOVER, outline="")
                rounded_rect(self, area_w + 12, y1 + 8, area_w + 24, y1 + 20, 4, fill=self.colors[i], outline="")
                self.create_text(area_w + 34, (y1 + y2) / 2, text=label, anchor="w", fill=C.TEXT,
                                 font=font(10, "bold" if i == self._hover else "normal"))
                self.create_text(w - 16, (y1 + y2) / 2, text=f"{self.values[i] / total:.0%}", anchor="e",
                                 fill=C.MUTED, font=font(10, "bold"))

    def _slice_at(self, x, y):
        cx, cy, R, thick = self._geo
        dist = math.hypot(x - cx, y - cy)
        if R - thick - 4 <= dist <= R + 10:
            angle = math.degrees(math.atan2(x - cx, -(y - cy))) % 360
            for i, (a, b) in enumerate(getattr(self, "_spans", [])):
                if a <= angle < b:
                    return i
        for i, (y1, y2) in enumerate(self._rows):
            if x > cx + R and y1 <= y <= y2:
                return i
        return None

    def _motion(self, e):
        idx = self._slice_at(e.x, e.y)
        self.configure(cursor="hand2" if idx is not None else "")
        if idx != self._hover:
            self._hover = idx
            self._render()

    def _leave(self, _e):
        if self._hover is not None:
            self._hover = None
            self._render()


class AnimatedLineChart(tk.Canvas):
    """Line that draws itself from left to right with a soft colored area under it."""

    def __init__(self, master, height=240, color=C.BLUE):
        super().__init__(master, height=height, bg=C.WHITE, highlightthickness=0)
        self.color, self.labels, self.values = color, [], []
        self._progress, self._anim, self._hover, self._pts = 1.0, None, None, []
        self.bind("<Configure>", lambda e: self._render())
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", self._leave)

    def set_data(self, labels, values):
        self.labels, self.values = list(labels), list(values)
        stop(self._anim)
        self._progress = 0.0

        def step(t):
            self._progress = t
            self._render()
        self._anim = animate(self, 1300, step, ease=ease_in_out)

    def _render(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        n = len(self.values)
        if w < 60 or h < 60:
            return
        if n == 0 or sum(self.values) == 0:
            self.create_text(w / 2, h / 2, text="No data yet", fill=C.MUTED, font=font(10))
            return
        left, right, top, bottom = 38, 22, 24, 34
        pw, ph = w - left - right, h - top - bottom
        step_val = nice_step(max(self.values))
        top_val = step_val * 4
        for i in range(5):
            y = top + ph - ph * i / 4
            self.create_line(left, y, w - right, y, fill="#E8EDF6", dash=(3, 3) if i else ())
            self.create_text(left - 8, y, text=str(step_val * i), anchor="e", fill=C.MUTED, font=font(8))
        self._pts = [(left + pw * i / max(1, n - 1), top + ph - ph * v / top_val) for i, v in enumerate(self.values)]
        for i, (x, _y) in enumerate(self._pts):
            self.create_text(x, top + ph + 17, text=self.labels[i], fill=C.MUTED, font=font(8))
        pos = self._progress * (n - 1)
        whole = int(pos)
        visible = self._pts[:whole + 1]
        if whole < n - 1:
            (x0, y0), (x1, y1) = self._pts[whole], self._pts[whole + 1]
            f = pos - whole
            visible = visible + [(x0 + (x1 - x0) * f, y0 + (y1 - y0) * f)]
        if len(visible) >= 2:
            area = [visible[0][0], top + ph]
            for x, y in visible:
                area += [x, y]
            area += [visible[-1][0], top + ph]
            self.create_polygon(area, fill=lighten(self.color, 0.86), outline="")
            flat = [c for p in visible for c in p]
            self.create_line(flat, fill=self.color, width=3, joinstyle="round", capstyle="round")
        for i, (x, y) in enumerate(self._pts):
            if i <= pos + 0.001:
                big = i == self._hover
                r = 6 if big else 4
                self.create_oval(x - r, y - r, x + r, y + r, fill=C.WHITE, outline=self.color, width=2.5)
        if self._hover is not None and self._hover <= pos + 0.001:
            x, y = self._pts[self._hover]
            self.create_line(x, top, x, top + ph, fill=self.color, dash=(4, 3))
            draw_tooltip(self, x, y, f"{self.labels[self._hover]}\n{self.values[self._hover]} submissions")

    def _motion(self, e):
        if not self._pts:
            return
        idx = min(range(len(self._pts)), key=lambda i: abs(self._pts[i][0] - e.x))
        if abs(self._pts[idx][0] - e.x) > 40:
            idx = None
        if idx != self._hover:
            self._hover = idx
            self._render()

    def _leave(self, _e):
        if self._hover is not None:
            self._hover = None
            self._render()


class AnimatedRankList(tk.Canvas):
    """Ranked list with colored bars that grow. Used for 'Top Voted Suggestions'."""
    ROW_H = 50

    def __init__(self, master, on_click=None, empty_text="No votes yet."):
        super().__init__(master, height=self.ROW_H, bg=C.WHITE, highlightthickness=0)
        self.items, self.on_click, self.empty_text = [], on_click, empty_text
        self._progress, self._anim, self._hover = [], None, None
        self._font = tkfont.Font(family=FONT, size=10, weight="bold")
        self.bind("<Configure>", lambda e: self._render())
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._click)

    def set_data(self, items):
        """items = list of (title, value)"""
        self.items = list(items)
        n = len(self.items)
        self.configure(height=max(1, n) * self.ROW_H if n else 90)
        stop(self._anim)
        self._progress = [0.0] * n
        total = 600 + 100 * n

        def step(t):
            self._progress = [ease_out_cubic(clamp((t * total - i * 100) / 600)) for i in range(n)]
            self._render()
        self._anim = animate(self, total, step, ease=linear)

    def _render(self):
        self.delete("all")
        w = self.winfo_width()
        if w < 60:
            return
        if not self.items:
            self.create_text(w / 2, 40, text=self.empty_text, fill=C.MUTED, font=font(10))
            return
        top = max(v for _t, v in self.items) or 1
        for i, (title, value) in enumerate(self.items):
            y0 = i * self.ROW_H
            color = PALETTE[i % len(PALETTE)]
            if i == self._hover:
                rounded_rect(self, 2, y0 + 3, w - 2, y0 + self.ROW_H - 3, 10, fill=C.ROW_HOVER, outline="")
            self.create_oval(10, y0 + 12, 32, y0 + 34, fill=color, outline="")
            self.create_text(21, y0 + 23, text=str(i + 1), fill="white", font=font(9, "bold"))
            self.create_text(w - 14, y0 + 20, text=f"{value}", anchor="e", fill=color, font=font(12, "bold"))
            room = w - 14 - 44 - 50
            self.create_text(44, y0 + 20, text=ellipsize(title, self._font, room), anchor="w",
                             fill=C.TEXT, font=self._font)
            x1, x2, by = 44, w - 14, y0 + self.ROW_H - 14
            rounded_rect(self, x1, by, x2, by + 6, 3, fill="#EEF2FA", outline="")
            fill_w = (x2 - x1) * value / top * (self._progress[i] if i < len(self._progress) else 1)
            if fill_w > 2:
                rounded_rect(self, x1, by, x1 + fill_w, by + 6, 3,
                             fill=lighten(color, 0.15) if i == self._hover else color, outline="")

    def _row(self, e):
        idx = e.y // self.ROW_H
        return idx if 0 <= idx < len(self.items) else None

    def _motion(self, e):
        idx = self._row(e)
        self.configure(cursor="hand2" if idx is not None and self.on_click else "")
        if idx != self._hover:
            self._hover = idx
            self._render()

    def _leave(self, _e):
        if self._hover is not None:
            self._hover = None
            self._render()

    def _click(self, e):
        idx = self._row(e)
        if idx is not None and self.on_click:
            self.on_click(idx)
