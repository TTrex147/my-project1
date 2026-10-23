"""
widgets.py
Reusable GUI parts with hover effects and animations:
    HoverButton, Badge, Card, KpiCard, StyledEntry, StyledText, DataTable, Pager,
    ScrollFrame, Toast, Modal, Sidebar (floating, expands on hover), PillSearch, RoundIconButton,
    CanvasButton, AnimatedBarChart, AnimatedDonutChart, AnimatedLineChart, AnimatedGauge, AnimatedRankList
"""
import math
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageTk

from icons import icon
from theme import (C, CATEGORY_COLORS, FONT, PALETTE, STATUS_STYLES, animate, bg_of,
                   clamp, darken, ease_in_out, ease_out_back, ease_out_cubic, ellipsize, font,
                   lerp_color, lighten, linear, pill_points, rounded_points, rounded_rect, stop)


# ======================================================================
#  ttk styles (combobox + slim scrollbar)
# ======================================================================
def setup_styles(root):
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TCombobox", fieldbackground=C.WHITE, background=C.WHITE, foreground=C.TEXT,
                    bordercolor=C.BORDER, lightcolor=C.BORDER, darkcolor=C.BORDER,
                    arrowcolor=C.PRIMARY, padding=7, relief="flat")
    style.map("TCombobox",
              fieldbackground=[("readonly", C.WHITE)],
              foreground=[("readonly", C.TEXT)],
              bordercolor=[("focus", C.PRIMARY), ("active", "#A9C2B3")],
              lightcolor=[("focus", C.PRIMARY)], darkcolor=[("focus", C.PRIMARY)],
              selectbackground=[("readonly", C.WHITE)], selectforeground=[("readonly", C.TEXT)],
              arrowcolor=[("active", C.PRIMARY_DARK)])
    root.option_add("*TCombobox*Listbox.background", C.WHITE)
    root.option_add("*TCombobox*Listbox.foreground", C.TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", C.PRIMARY)
    root.option_add("*TCombobox*Listbox.selectForeground", C.WHITE)
    root.option_add("*TCombobox*Listbox.font", font(10))
    # slim scrollbar with no arrows
    style.layout("Slim.Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {
        "sticky": "ns", "children": [("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
    style.configure("Slim.Vertical.TScrollbar", troughcolor=C.BG, background="#C9CFC8",
                    bordercolor=C.BG, lightcolor="#C9CFC8", darkcolor="#C9CFC8", gripcount=0, width=8)
    style.map("Slim.Vertical.TScrollbar", background=[("active", "#AAB5AD")])


def make_combo(parent, values, width=18, value=None):
    box = ttk.Combobox(parent, values=values, state="readonly", width=width, font=font(10))
    if value is not None:
        box.set(value)
    box.bind("<<ComboboxSelected>>", lambda e: box.selection_clear(), add="+")
    return box


# ======================================================================
#  Hover helper
# ======================================================================
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


def destroy_tree(widget):
    """Destroy a widget and everything inside it. A harmless Tk timer error on one widget
    can never stop the rest from being cleaned up."""
    for child in list(widget.winfo_children()):
        destroy_tree(child)
    try:
        widget.destroy()
    except (tk.TclError, AttributeError):
        pass


def set_bg_tree(widget, color):
    """Change the background of a widget and everything inside it."""
    try:
        widget.configure(bg=color)
    except tk.TclError:
        pass
    for child in widget.winfo_children():
        set_bg_tree(child, color)


# ======================================================================
#  Buttons, badges, links
# ======================================================================
BUTTON_STYLES = {
    "primary": dict(bg=C.PRIMARY, hover="#52806A", press=C.PRIMARY_DARK, fg="#FFFFFF"),
    "dark": dict(bg=C.DARK, hover="#35483D", press="#111C17", fg="#FFFFFF"),
    "success": dict(bg=C.GREEN, hover="#52B286", press="#2E8059", fg="#FFFFFF"),
    "danger": dict(bg=C.RED, hover="#E56F69", press="#B8403B", fg="#FFFFFF"),
    "outline": dict(bg=C.WHITE, hover=C.PRIMARY_SOFT, press="#D3E5D9", fg=C.PRIMARY, border=C.PRIMARY),
    "gray": dict(bg="#F0EEE8", hover="#E6E3DB", press="#DAD7CE", fg=C.TEXT),
    "soft": dict(bg=C.PRIMARY_SOFT, hover="#D3E7DA", press="#C2DBCB", fg=C.PRIMARY),
    "soft_red": dict(bg=C.RED_SOFT, hover="#F9D0CD", press="#F4B9B5", fg="#B8403B"),
    "soft_green": dict(bg=C.GREEN_SOFT, hover="#C9EBD7", press="#B2E0C5", fg="#23805A"),
    "soft_orange": dict(bg=C.ORANGE_SOFT, hover="#F8DDB4", press="#F3CF98", fg="#B3741C"),
}


class HoverButton(tk.Canvas):
    """A rounded button. The color fades smoothly when the mouse is over it."""

    def __init__(self, master, text, command=None, style="primary", width=None, height=38,
                 radius=12, size=10, pad=36):
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
            self._color = "#CFCFC8"
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
        default = STATUS_STYLES.get(text, (C.PRIMARY_SOFT, C.PRIMARY))
        bg_color, fg_color = bg_color or default[0], fg_color or default[1]
        w = Badge._font.measure(text) + 26
        super().__init__(master, width=w, height=height, bg=bg_of(master), highlightthickness=0, bd=0)
        rounded_rect(self, 0, 0, w, height, height / 2, fill=bg_color, outline="")
        self.create_text(w / 2, height / 2, text=text, fill=fg_color, font=Badge._font)


def category_badge(master, category):
    color = CATEGORY_COLORS.get(category, C.PRIMARY)
    return Badge(master, category, bg_color=lighten(color, 0.82), fg_color=darken(color, 0.25))


class LinkLabel(tk.Label):
    """Blue text that gets an underline when the mouse is over it."""

    def __init__(self, master, text, command=None, size=9):
        super().__init__(master, text=text, fg=C.PRIMARY, bg=bg_of(master), font=font(size, "bold"),
                         cursor="hand2")
        self._normal, self._under = font(size, "bold"), (FONT, size, "bold underline")
        self.bind("<Enter>", lambda e: self.configure(font=self._under, fg=C.PRIMARY_DARK))
        self.bind("<Leave>", lambda e: self.configure(font=self._normal, fg=C.PRIMARY))
        if command:
            self.bind("<Button-1>", lambda e: command())


# ======================================================================
#  Cards
# ======================================================================
def rr_mask(w, h, r, scale=3):
    """Smooth rounded-rectangle mask (white = visible)."""
    w, h = max(1, int(w)), max(1, int(h))
    big = Image.new("L", (w * scale, h * scale), 0)
    ImageDraw.Draw(big).rounded_rectangle([0, 0, w * scale - 1, h * scale - 1], radius=r * scale, fill=255)
    return big.resize((w, h), Image.LANCZOS)


def gradient_image(w, h, c1, c2, radius):
    """Rounded rectangle with a soft diagonal color gradient (c1 top-left -> c2 bottom-right)."""
    w, h = max(1, int(w)), max(1, int(h))
    horizontal = Image.linear_gradient("L").rotate(90).resize((w, h))
    vertical = Image.linear_gradient("L").resize((w, h))
    diagonal = ImageChops.add(horizontal, vertical, scale=2)
    img = Image.composite(Image.new("RGB", (w, h), c2), Image.new("RGB", (w, h), c1), diagonal).convert("RGBA")
    img.putalpha(rr_mask(w, h, radius))
    return img


def catmull(points, steps=10):
    """Smooth curve through a list of (x, y) points. Returns a longer list of points."""
    if len(points) < 3:
        return list(points)
    pts = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for k in range(steps):
            t = k / steps
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t
                                    + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    out.append(points[-1])
    return out


def fit_text(text, fnt, avail):
    """The longest start of the text that fits in avail pixels (no '...')."""
    if avail <= 6:
        return ""
    while text and fnt.measure(text) > avail:
        text = text[:-1]
    return text


class Card(tk.Frame):
    """White rounded card with a soft shadow. Put your widgets inside `card.body`.
    The border lights up when the mouse is over it.
    (A canvas behind the content draws the rounded shape; the content sets the card's size.)"""

    def __init__(self, master, accent=C.PRIMARY, pad=20, hover=True, bg=C.WHITE, radius=22):
        super().__init__(master, bg=bg_of(master), highlightthickness=0, bd=0)
        self.accent, self._r, self._fill = accent, radius, bg
        self._anim, self._glow_t = None, 0.0
        self._back = tk.Canvas(self, bg=bg_of(master), highlightthickness=0, bd=0)
        self._back.place(x=0, y=0, relwidth=1, relheight=1)
        self._shadow = rounded_rect(self._back, 3, 5, 12, 14, radius, fill=C.SHADOW, outline="")
        self._shape = rounded_rect(self._back, 0, 0, 10, 10, radius, fill=bg, outline=bg, width=2)
        self.body = tk.Frame(self, bg=bg)
        self.body.pack(fill="both", expand=True, padx=pad, pady=(pad, pad + 4))
        self._back.bind("<Configure>", self._resize)
        if hover:
            self.after_idle(lambda: HoverArea(self, lambda: self._glow(1.0), lambda: self._glow(0.0)))

    def _resize(self, e):
        w, h = e.width, e.height
        r = min(self._r, w / 2, h / 2)
        self._back.coords(self._shadow, *rounded_points(3, 5, w - 3, h, r))
        self._back.coords(self._shape, *rounded_points(1, 1, w - 1, h - 4, r))

    def _glow(self, target):
        stop(self._anim)
        start = self._glow_t

        def step(t):
            self._glow_t = start + (target - start) * t
            edge = lerp_color(self._fill, self.accent, 0.5 * self._glow_t)
            self._back.itemconfigure(self._shape, outline=edge)
            self._back.itemconfigure(self._shadow, fill=lerp_color(C.SHADOW, "#CFCBC0", self._glow_t))
        self._anim = animate(self, 200, step)


class KpiCard(tk.Canvas):
    """Number card: label, big number that counts up, and a small animated chart.
    variant: 'bars' (mini bar chart), 'wave' (icon + wave line), 'plain' (icon only),
             'accent' (green gradient card with a white wave)."""
    HEIGHT = 116

    def __init__(self, master, label, icon_name, color, variant="bars", delay=0):
        super().__init__(master, bg=bg_of(master), highlightthickness=0, bd=0, width=10, height=self.HEIGHT)
        self.label, self.icon_name, self.color, self.variant = label, icon_name, color, variant
        self._delay, self._shown, self._series, self._sp = delay, 0.0, [], 1.0
        self._glow, self._ga, self._va, self._sa = 0.0, None, None, None
        self._grad, self._grad_key = None, None
        self.bind("<Configure>", lambda e: self._render())
        self.bind("<Enter>", lambda e: self._glow_to(1.0))
        self.bind("<Leave>", lambda e: self._glow_to(0.0))

    def set_value(self, value):
        stop(self._va)
        start, delay = self._shown, self._delay
        self._delay = 0

        def step(t):
            self._shown = start + (value - start) * t
            self._render()
        self._va = animate(self, 900, step, delay=delay)

    def set_series(self, values):
        self._series = list(values)
        stop(self._sa)
        self._sp = 0.0

        def step(t):
            self._sp = t
            self._render()
        self._sa = animate(self, 1200, step, delay=self._delay)

    def _glow_to(self, target):
        stop(self._ga)
        start = self._glow

        def step(t):
            self._glow = start + (target - start) * t
            self._render()
        self._ga = animate(self, 200, step)

    def _render(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 60 or h < 40:
            return
        self.delete("all")
        r, body_h, pad = 22, h - 4, 22
        accent = self.variant == "accent"
        rounded_rect(self, 3, 5, w - 3, h, r, fill=lerp_color(C.SHADOW, "#CFCBC0", self._glow), outline="")
        if accent:
            if self._grad_key != (w, body_h):
                self._grad = ImageTk.PhotoImage(gradient_image(w, body_h, "#86AA95", "#2F5744", r))
                self._grad_key = (w, body_h)
            self.create_image(0, 0, anchor="nw", image=self._grad)
            label_fg, num_fg, line = "#DCEBE1", "#FFFFFF", "#FFFFFF"
        else:
            edge = lerp_color(C.WHITE, self.color, 0.5 * self._glow)
            rounded_rect(self, 1, 1, w - 1, body_h - 1, r, fill=C.WHITE, outline=edge, width=2)
            label_fg, num_fg, line = C.MUTED, C.TEXT, self.color
        tx = pad
        if self.variant in ("wave", "plain"):
            cy = body_h / 2
            self.create_oval(pad, cy - 21, pad + 42, cy + 21, fill=lighten(self.color, 0.84), outline="")
            self.create_image(pad + 21, cy, image=icon(self.icon_name, self.color, 22))
            tx = pad + 42 + 14
        self.create_text(tx, 28, text=self.label, anchor="w", fill=label_fg, font=font(9, "bold"))
        self.create_text(tx, body_h - 36, text=str(int(round(self._shown))), anchor="w", fill=num_fg,
                         font=font(24, "bold"))
        cw = 70 if self.variant == "wave" else 84
        x0, y_top, y_bot = w - pad - cw, 46, body_h - 20
        if self._series and self.variant != "plain" and x0 > tx + 64:
            self._draw_chart(x0, cw, y_top, y_bot, line)

    def _draw_chart(self, x0, cw, y_top, y_bot, line):
        vals, n = self._series, len(self._series)
        top = max(max(vals), 1)
        if self.variant == "bars":
            bw = 6
            gap = (cw - n * bw) / max(n - 1, 1)
            for i, v in enumerate(vals):
                p = ease_out_cubic(clamp((self._sp * (n + 3) - i) / 3))
                bh = max(7, (y_bot - y_top) * v / top) * p
                x = x0 + i * (bw + gap)
                color = self.color if i >= n - 3 else lighten(self.color, 0.62)
                rounded_rect(self, x, y_bot - bh, x + bw, y_bot, 3, fill=color, outline="")
        else:
            pts = [(x0 + cw * i / max(n - 1, 1), y_bot - (y_bot - y_top) * (0.1 + 0.9 * v / top))
                   for i, v in enumerate(vals)]
            curve = catmull(pts, 8)
            shown = curve[:max(2, int(len(curve) * self._sp))]
            if len(shown) >= 2:
                self.create_line([c for p in shown for c in p], fill=line, width=2.6, capstyle="round",
                                 joinstyle="round")


class AnimatedGauge(tk.Canvas):
    """Half-circle gauge that fills up. Shows a percent in the middle."""

    def __init__(self, master, height=180, color=C.PRIMARY):
        super().__init__(master, height=height, bg=bg_of(master), highlightthickness=0, bd=0)
        self.color, self._pct, self._shown, self._caption, self._anim, self._hover = color, 0.0, 0.0, "", None, False
        self.bind("<Configure>", lambda e: self._render())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))

    def _set_hover(self, value):
        self._hover = value
        self._render()

    def set_value(self, pct, caption=""):
        self._pct, self._caption = max(0.0, min(100.0, pct)), caption
        stop(self._anim)
        start = self._shown

        def step(t):
            self._shown = start + (self._pct - start) * t
            self._render()
        self._anim = animate(self, 1200, step)

    def _render(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 60 or h < 60:
            return
        self.delete("all")
        thick = 24 + (3 if self._hover else 0)
        radius = max(40, min(w / 2 - 22, h - 56))
        cx, cy = w / 2, h - 44
        mid = radius - thick / 2
        box = (cx - mid, cy - mid, cx + mid, cy + mid)
        self.create_arc(*box, start=180, extent=-180, style="arc", outline=C.PRIMARY_SOFT, width=thick)
        frac = self._shown / 100
        if frac > 0.004:
            self.create_arc(*box, start=180, extent=-180 * frac, style="arc", outline=self.color, width=thick)
        if frac > 0.02:
            ang = math.radians(180 - 180 * frac)                  # little tick at the end of the fill
            r1, r2 = radius - thick - 4, radius + 7
            self.create_line(cx + r1 * math.cos(ang), cy - r1 * math.sin(ang), cx + r2 * math.cos(ang),
                             cy - r2 * math.sin(ang), fill=C.DARK, width=3, capstyle="round")
        size = max(14, min(26, int(radius / 3.4)))              # smaller card -> smaller number
        self.create_text(cx, cy - size * 0.45, text=f"{int(round(self._shown))}%", fill=C.TEXT, font=font(size, "bold"))
        if self._caption:
            self.create_text(cx, cy + 28, text=self._caption, fill=C.MUTED, font=font(9))


class PillSearch(tk.Canvas):
    """White pill search box with a dark round search button."""

    def __init__(self, master, placeholder="Search...", command=None, width=330, height=48):
        super().__init__(master, width=width, height=height, bg=bg_of(master), highlightthickness=0, bd=0)
        self.command, self._fill, self._anim = command, C.DARK, None
        rounded_rect(self, 0, 0, width, height, height / 2, fill=C.WHITE, outline="")
        self.entry = StyledEntry(self, placeholder=placeholder, width=20, size=10, bare=True)
        self.create_window(24, height / 2, window=self.entry, anchor="w", width=width - 24 - 64, height=28)
        self._btn = self.create_oval(width - 43, 5, width - 5, height - 5, fill=C.DARK, outline="")
        self._ico = self.create_image(width - 24, height / 2, image=icon("search", "#FFFFFF", 18))
        for item in (self._btn, self._ico):
            self.tag_bind(item, "<Enter>", lambda e: self._tween(C.PRIMARY))
            self.tag_bind(item, "<Leave>", lambda e: self._tween(C.DARK))
            self.tag_bind(item, "<Button-1>", lambda e: self._go())
        self.entry.bind("<Return>", lambda e: self._go())

    def _tween(self, target):
        stop(self._anim)
        start = self._fill

        def step(t):
            self._fill = lerp_color(start, target, t)
            self.itemconfigure(self._btn, fill=self._fill)
        self._anim = animate(self, 150, step, ease=linear)

    def _go(self):
        if self.command:
            self.command(self.entry.value())


class RoundIconButton(tk.Canvas):
    """White round button with an icon (and an optional red dot)."""

    def __init__(self, master, icon_name, command=None, size=48):
        super().__init__(master, width=size, height=size, bg=bg_of(master), highlightthickness=0, bd=0,
                         cursor="hand2")
        self.command, self._fill, self._anim = command, C.WHITE, None
        self._circle = self.create_oval(0, 0, size, size, fill=C.WHITE, outline="")
        self.create_image(size / 2, size / 2, image=icon(icon_name, C.DARK, 22))
        self._dot = self.create_oval(size - 17, 8, size - 8, 17, fill=C.RED, outline=C.WHITE, width=2, state="hidden")
        self.bind("<Enter>", lambda e: self._tween(C.PRIMARY_SOFT))
        self.bind("<Leave>", lambda e: self._tween(C.WHITE))
        self.bind("<Button-1>", lambda e: command() if command else None)

    def set_dot(self, visible):
        self.itemconfigure(self._dot, state="normal" if visible else "hidden")

    def _tween(self, target):
        stop(self._anim)
        start = self._fill

        def step(t):
            self._fill = lerp_color(start, target, t)
            self.itemconfigure(self._circle, fill=self._fill)
        self._anim = animate(self, 150, step, ease=linear)


class CanvasButton:
    """A rounded button drawn straight on a Canvas (so it can sit on top of a picture)."""

    def __init__(self, canvas, box, text, command, fill, hover, press=None, fg="#FFFFFF", radius=14,
                 size=11, outline=None, tag="ui"):
        self.c, self.command, self.fill, self.hover = canvas, command, fill, hover
        self.press = press or darken(hover, 0.12)
        self._cur, self._anim = fill, None
        x1, y1, x2, y2 = box
        uid = f"btn{id(self)}"
        self.shape = rounded_rect(canvas, x1, y1, x2, y2, radius, fill=fill, outline=outline or fill, width=1.5,
                                  tags=(tag, uid))
        self.label = canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=text, fill=fg,
                                        font=font(size, "bold"), tags=(tag, uid))
        canvas.tag_bind(uid, "<Enter>", lambda e: self._enter())
        canvas.tag_bind(uid, "<Leave>", lambda e: self._leave())
        canvas.tag_bind(uid, "<ButtonPress-1>", lambda e: self._paint(self.press))
        canvas.tag_bind(uid, "<ButtonRelease-1>", lambda e: self._click())

    def _paint(self, color):
        self._cur = color
        self.c.itemconfigure(self.shape, fill=color)

    def _fade(self, target):
        stop(self._anim)
        start = self._cur
        self._anim = animate(self.c, 150, lambda t: self._paint(lerp_color(start, target, t)), ease=linear)

    def _enter(self):
        self.c.configure(cursor="hand2")
        self._fade(self.hover)

    def _leave(self):
        self.c.configure(cursor="")
        self._fade(self.fill)

    def _click(self):
        self._fade(self.hover)
        if self.command:
            self.c.after(10, self.command)             # let the click finish first, then open pop-ups


def canvas_link(canvas, x, y, text, command, color=C.PRIMARY, hover=C.PRIMARY_DARK, size=10,
                anchor="center", tag="ui", bold=True):
    """Clickable text on a Canvas. Gets an underline when the mouse is over it."""
    weight = "bold" if bold else "normal"
    item = canvas.create_text(x, y, text=text, fill=color, font=font(size, weight), anchor=anchor, tags=(tag,))

    def enter(_e):
        canvas.itemconfigure(item, fill=hover, font=(FONT, size, weight + " underline"))
        canvas.configure(cursor="hand2")

    def leave(_e):
        canvas.itemconfigure(item, fill=color, font=font(size, weight))
        canvas.configure(cursor="")
    canvas.tag_bind(item, "<Enter>", enter)
    canvas.tag_bind(item, "<Leave>", leave)
    # react when the mouse button is RELEASED (like a normal button), and let the click finish first
    canvas.tag_bind(item, "<ButtonRelease-1>", lambda e: canvas.after(10, command))
    return item


def card_fan_image(w=300, h=170):
    """Picture of three tilted cards (used on the 'Have an idea?' banner)."""
    S = 3
    canvas = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    specs = [(-17, "#CFE3D6", C.PRIMARY, "mail", 36), (0, "#8FB29E", "#FFFFFF", "bulb", 0),
             (17, "#2F5744", "#FFFFFF", "vote", 48)]
    cw, ch = 118 * S, 76 * S
    for angle, fill, ink, name, dy in specs:
        card = gradient_image(cw, ch, lighten(fill, 0.12), fill, 14 * S)
        d = ImageDraw.Draw(card)
        d.rounded_rectangle([14 * S, 44 * S, 74 * S, 49 * S], radius=3 * S, fill=ink)
        d.rounded_rectangle([14 * S, 55 * S, 48 * S, 60 * S], radius=3 * S, fill=ink)
        glyph = icon_image(name, ink, 24 * S)
        card.alpha_composite(glyph, (14 * S, 12 * S))
        rotated = card.rotate(angle, expand=True, resample=Image.BICUBIC)
        shadow = Image.new("RGBA", rotated.size, (0, 0, 0, 0))
        shadow.putalpha(rotated.getchannel("A").point(lambda v: int(v * 0.25)))
        shadow = shadow.filter(ImageFilter.GaussianBlur(7 * S))
        x = (w * S - rotated.width) // 2 + int(angle * 3.2 * S)
        y = int((h * S - rotated.height) // 2 + (dy - 20) * S / 3)
        canvas.alpha_composite(shadow, (max(0, x), max(0, y + 8 * S)))
        canvas.alpha_composite(rotated, (max(0, x), max(0, y)))
    return canvas.resize((w, h), Image.LANCZOS)


def icon_image(name, color, size):
    from icons import render
    return render(name, color, size, 1.9)


# ======================================================================
#  Inputs
# ======================================================================
class StyledEntry(tk.Entry):
    """Entry with placeholder text, hover color and a green glow when focused.
    bare=True removes the border (used on the glass login card, where the box is drawn by the screen)."""

    def __init__(self, master, placeholder="", password=False, width=30, size=10, bare=False, bg=C.WHITE):
        super().__init__(master, relief="flat", bg=bg, fg=C.TEXT, insertbackground=C.PRIMARY,
                         highlightthickness=0 if bare else 2, highlightbackground=C.BORDER,
                         highlightcolor=C.PRIMARY, font=font(size), width=width, bd=0 if bare else 6)
        self._placeholder, self._password, self._bare = placeholder, password, bare
        self._has_ph, self._anim, self._focused = False, None, False
        self._show_placeholder()
        self.bind("<FocusIn>", self._focus_in)
        self.bind("<FocusOut>", self._focus_out)
        if not bare:
            self.bind("<Enter>", lambda e: self._hover("#A9C2B3"))
            self.bind("<Leave>", lambda e: self._hover(C.BORDER))

    def _hover(self, color):
        if not self._focused:
            stop(self._anim)
            start = self.cget("highlightbackground")
            self._anim = animate(self, 140, lambda t: self.configure(
                highlightbackground=lerp_color(start, color, t)), ease=linear)

    def _focus_in(self, _e):
        self._focused = True
        if not self._bare:
            stop(self._anim)
            self.configure(highlightcolor=C.BORDER)
            self._anim = animate(self, 180, lambda t: self.configure(
                highlightcolor=lerp_color(C.BORDER, C.PRIMARY, t)), ease=linear)
        if self._has_ph:
            self.delete(0, "end")
            self._has_ph = False
            self.configure(fg=C.TEXT, show="\u25CF" if self._password else "")

    def _focus_out(self, _e):
        self._focused = False
        if not self._bare:
            self.configure(highlightbackground=C.BORDER)
        self._show_placeholder()

    def _show_placeholder(self):
        if self._placeholder and not super().get():
            self._has_ph = True
            self.configure(fg="#A3ADA6", show="")
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
                            highlightcolor=C.PRIMARY, bd=8, insertbackground=C.PRIMARY, undo=True)
        self.text.pack(fill="both", expand=True)
        self.counter = tk.Label(self, text=f"0/{limit}", bg=bg, fg=C.MUTED, font=font(8))
        self.counter.pack(anchor="e", pady=(3, 0))
        self._hint = tk.Label(self.text, text=placeholder, bg=C.WHITE, fg="#A3ADA6", font=font(10),
                              cursor="xterm", justify="left", wraplength=420)
        self._hint.bind("<Button-1>", lambda e: self.text.focus_set())
        self.text.bind("<Key>", lambda e: self.after_idle(self._changed))
        self.text.bind("<<Paste>>", lambda e: self.after_idle(self._changed))
        self.text.bind("<<Cut>>", lambda e: self.after_idle(self._changed))
        self.text.bind("<Enter>", lambda e: self.text.configure(highlightbackground="#A9C2B3"))
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
        # Only the WIDTH is fixed. The height follows the content, so this method runs again
        # every time the page becomes taller or shorter (new cards, new rows, charts...).
        self.canvas.itemconfigure(self._win, width=w)
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
        header = tk.Frame(self, bg="#F6F4EF")
        header.pack(fill="x")
        self._grid_columns(header)
        for i, col in enumerate(columns):
            tk.Label(header, text=col.title, bg="#F6F4EF", fg=C.MUTED, font=font(9, "bold"),
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
        tk.Frame(outer, bg="#EEECE6", height=1).pack(fill="x")
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
              "info": (C.PRIMARY, "\u2139"), "warning": (C.ORANGE, "!")}

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
    def __init__(self, root, title, width=520, accent=C.PRIMARY):
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
        self.deiconify()
        self.lift()
        try:                                           # small fade-in (starts visible, always ends fully visible)
            self.attributes("-alpha", 0.3)
            animate(self, 200, lambda t: self.attributes("-alpha", 0.3 + 0.7 * t), done=self._opaque)
        except tk.TclError:
            pass
        self.after(30, self._take_focus)

    def _opaque(self):
        try:
            self.attributes("-alpha", 1.0)
        except tk.TclError:
            pass

    def _take_focus(self, tries=0):
        """Make this window the only one that reacts (modal). Tries again if the window is not ready yet."""
        try:
            self.grab_set()
        except tk.TclError:
            if tries < 6:
                self.after(60, lambda: self._take_focus(tries + 1))
            return
        try:
            self.focus_force()
        except tk.TclError:
            pass

    def close(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


def confirm(root, title, message, on_yes, yes_text="Yes, delete", style="danger"):
    m = Modal(root, title, width=440, accent=C.RED if style == "danger" else C.PRIMARY)
    tk.Label(m.body, text=message, bg=C.WHITE, fg=C.MUTED, font=font(10), wraplength=380,
             justify="left").pack(anchor="w")
    HoverButton(m.footer, yes_text, lambda: (m.close(), on_yes()), style).pack(side="right")
    HoverButton(m.footer, "Cancel", m.close, "gray").pack(side="right", padx=8)
    m.show()


# ======================================================================
#  Sidebar (floating, icons)
# ======================================================================
class Sidebar(tk.Canvas):
    """Floating white sidebar with round icons. It opens wider (and shows the names)
    when the mouse is over it, like a drawer."""
    COLLAPSED, EXPANDED, ROW = 76, 248, 58

    def __init__(self, master, user, on_navigate, on_logout):
        super().__init__(master, bg=bg_of(master), highlightthickness=0, bd=0, width=self.COLLAPSED + 6)
        self.user, self._navigate, self._logout = user, on_navigate, on_logout
        self.cur_w, self._wa, self._hover = float(self.COLLAPSED), None, None
        self._fnt = tkfont.Font(family=FONT, size=10, weight="bold")
        self._fnt_small = tkfont.Font(family=FONT, size=9)
        self._shadow = rounded_rect(self, 3, 5, 80, 100, 38, fill=C.SHADOW, outline="")
        self._pill = rounded_rect(self, 0, 0, 76, 96, 38, fill=C.WHITE, outline="")
        self.items = []
        for key, label, icon_name in user.menu_items():
            if key != "profile":
                self.items.append(self._make_item(key, label, icon_name, "top"))
        self.items.append(self._make_item("logout", "Log out", "logout", "bottom"))
        self.items.append(self._make_item("profile", user.full_name, None, "avatar"))
        self._dot_glow = self.create_oval(0, 0, 1, 1, fill=C.PRIMARY_SOFT, outline="")
        self._dot_core = self.create_oval(0, 0, 1, 1, fill="#35C98F", outline="")
        self._dot_text = self.create_text(78, 0, text="Live sync", anchor="w", fill=C.MUTED, font=font(9))
        self._phase, self._flash = 0.0, 0
        self.bind("<Configure>", lambda e: self._layout())
        self.bind("<Motion>", self._motion)
        self.bind("<Enter>", lambda e: self._expand(self.EXPANDED))
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._click)
        self._pulse()

    # ------------------------------------------------ items
    def _make_item(self, key, label, icon_name, zone):
        item = {"key": key, "label": label, "icon": icon_name, "zone": zone, "y": 0, "h": 0.0,
                "active": False, "anim": None, "state": None}
        item["hl"] = self.create_polygon(pill_points(12, 0, 64, 50), fill=C.WHITE, outline="")
        if zone == "avatar":
            item["ring"] = self.create_oval(0, 0, 1, 1, fill=C.DARK, outline="")
            item["initial"] = self.create_text(0, 0, text=self.user.initial, fill="white", font=font(12, "bold"))
        else:
            item["ic"] = self.create_image(0, 0, image=icon(icon_name, C.MUTED, 22))
        item["tx"] = self.create_text(78, 0, text="", anchor="w", fill=C.TEXT, font=self._fnt)
        self._paint(item)
        return item

    def _paint(self, item):
        active, h = item["active"], item["h"]
        fill = C.PRIMARY if active else lerp_color(C.WHITE, C.PRIMARY_SOFT, h)
        self.itemconfigure(item["hl"], fill=fill)
        self.itemconfigure(item["tx"], fill="#FFFFFF" if active else C.TEXT)
        if item["zone"] == "avatar":
            self.itemconfigure(item["ring"], outline=C.PRIMARY_LIGHT if (active or h > 0.5) else "", width=3)
        else:
            state = "active" if active else ("hover" if h > 0.5 else "normal")
            if state != item["state"]:
                item["state"] = state
                color = {"active": "#FFFFFF", "hover": C.PRIMARY, "normal": C.MUTED}[state]
                self.itemconfigure(item["ic"], image=icon(item["icon"], color, 22))

    def _tween_hover(self, item, target):
        stop(item["anim"])
        start = item["h"]

        def step(t):
            item["h"] = start + (target - start) * t
            self._paint(item)
        item["anim"] = animate(self, 160, step, ease=linear)

    def set_active(self, key):
        for item in self.items:
            item["active"] = item["key"] == key
            self._paint(item)

    # ------------------------------------------------ layout
    def _layout(self):
        h = max(self.winfo_height(), 300)
        w = self.cur_w
        pill_h = h - 6
        r = min(38, w / 2)
        self.coords(self._shadow, *rounded_points(3, 5, w + 3, h - 1, r))
        self.coords(self._pill, *rounded_points(0, 0, w, pill_h, r))
        avatar_y = pill_h - 46
        logout_y = avatar_y - self.ROW
        top_i = 0
        for item in self.items:
            if item["zone"] == "top":
                y = 56 + top_i * self.ROW
                top_i += 1
            elif item["zone"] == "bottom":
                y = logout_y
            else:
                y = avatar_y
            item["y"] = y
            self.coords(item["hl"], *pill_points(12, y - 25, w - 12, y + 25))
            if item["zone"] == "avatar":
                self.coords(item["ring"], 38 - 19, y - 19, 38 + 19, y + 19)
                self.coords(item["initial"], 38, y)
            else:
                self.coords(item["ic"], 38, y)
            self.coords(item["tx"], 78, y)
            self.itemconfigure(item["tx"], text=fit_text(item["label"], self._fnt, w - 78 - 18))
        dot_y = logout_y - 44
        self.coords(self._dot_text, 78, dot_y)
        self.itemconfigure(self._dot_text, text=fit_text("Live sync", self._fnt_small, w - 78 - 18))
        self._dot_y = dot_y
        self._place_dot()

    def _place_dot(self):
        s = (math.sin(self._phase) + 1) / 2
        r = 4 + 4 * s
        y = getattr(self, "_dot_y", 0)
        self.coords(self._dot_glow, 38 - r, y - r, 38 + r, y + r)
        self.coords(self._dot_core, 34, y - 4, 42, y + 4)

    def _pulse(self):
        try:
            self._phase += 0.12
            s = (math.sin(self._phase) + 1) / 2
            color = "#35C98F" if self._flash == 0 else C.ORANGE
            self.itemconfigure(self._dot_glow, fill=lerp_color(C.WHITE, color, 0.12 + 0.3 * (1 - s)))
            self.itemconfigure(self._dot_core, fill=color)
            if self._flash:
                self._flash -= 1
            self._place_dot()
            self.after(40, self._pulse)
        except tk.TclError:
            pass

    def flash_sync(self):
        self._flash = 25

    # ------------------------------------------------ mouse
    def _item_at(self, x, y):
        if not 12 <= x <= self.cur_w - 12:
            return None
        for item in self.items:
            if abs(y - item["y"]) <= 25:
                return item
        return None

    def _motion(self, e):
        item = self._item_at(e.x, e.y)
        if item is not self._hover:
            if self._hover is not None:
                self._tween_hover(self._hover, 0.0)
            if item is not None:
                self._tween_hover(item, 1.0)
            self._hover = item
        self.configure(cursor="hand2" if item else "")

    def _leave(self, _e):
        if self._hover is not None:
            self._tween_hover(self._hover, 0.0)
            self._hover = None
        self.configure(cursor="")
        self._expand(self.COLLAPSED)

    def _click(self, e):
        item = self._item_at(e.x, e.y)
        if item is None:
            return
        if item["key"] == "logout":
            self._logout()
        else:
            self._navigate(item["key"])

    def _expand(self, target):
        stop(self._wa)
        start = self.cur_w

        def step(t):
            self.cur_w = start + (target - start) * t
            try:
                self.place_configure(width=self.cur_w + 6)
            except tk.TclError:
                return
            self._layout()
        self._wa = animate(self, 240, step)


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
    box = rounded_rect(canvas, px, py, px + tw, py + th, 9, fill=C.DARK, outline="")
    canvas.coords(t, px + 11, py + 7)
    canvas.tag_raise(t, box)


class AnimatedBarChart(tk.Canvas):
    """Bars grow up one by one. Hover a bar to make it pop and show its number."""

    def __init__(self, master, height=240):
        super().__init__(master, height=height, bg=bg_of(master), highlightthickness=0)
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
            self.create_line(left, y, w - right, y, fill="#ECEAE4", dash=(3, 3) if i else ())
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
        super().__init__(master, height=height, bg=bg_of(master), highlightthickness=0)
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
    """Smooth line that draws itself from left to right, with a soft area under it."""

    def __init__(self, master, height=240, color=C.PRIMARY, unit="submissions"):
        super().__init__(master, height=height, bg=bg_of(master), highlightthickness=0)
        self.color, self.unit, self.labels, self.values = color, unit, [], []
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
        self._anim = animate(self, 1400, step, ease=ease_in_out)

    def _render(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        n = len(self.values)
        if w < 60 or h < 60:
            return
        if n == 0:
            self.create_text(w / 2, h / 2, text="No data yet", fill=C.MUTED, font=font(10))
            return
        empty = sum(self.values) == 0
        left, right, top, bottom = 38, 22, 24, 34
        pw, ph = w - left - right, h - top - bottom
        base = top + ph
        step_val = 1 if empty else nice_step(max(self.values))
        top_val = step_val * 4
        if empty:
            self.create_text(w / 2, top + ph * 0.35, text="No activity in this period yet", fill=C.MUTED, font=font(10))
        for i in range(5):
            y = base - ph * i / 4
            self.create_line(left, y, w - right, y, fill="#ECEAE4", dash=(3, 3) if i else ())
            self.create_text(left - 8, y, text=str(step_val * i), anchor="e", fill=C.MUTED, font=font(8))
        self._pts = [(left + pw * i / max(1, n - 1), base - ph * v / top_val) for i, v in enumerate(self.values)]
        for i, (x, _y) in enumerate(self._pts):
            self.create_text(x, base + 17, text=self.labels[i], fill=C.MUTED, font=font(8))
        curve = [(x, min(base, max(top, y))) for x, y in catmull(self._pts, 12)]
        x_limit = left + pw * self._progress
        shown = [p for p in curve if p[0] <= x_limit]
        if len(shown) >= 2:
            area = [shown[0][0], base]
            for x, y in shown:
                area += [x, y]
            area += [shown[-1][0], base]
            self.create_polygon(area, fill=lighten(self.color, 0.86), outline="")
            self.create_line([c for p in shown for c in p], fill=self.color, width=3, joinstyle="round",
                             capstyle="round")
        for i, (x, y) in enumerate(self._pts):
            if x <= x_limit + 0.5:
                r = 6 if i == self._hover else 4
                self.create_oval(x - r, y - r, x + r, y + r, fill=C.WHITE, outline=self.color, width=2.5)
        if self._hover is not None and self._pts[self._hover][0] <= x_limit + 0.5:
            x, y = self._pts[self._hover]
            self.create_line(x, top, x, base, fill=self.color, dash=(4, 3))
            draw_tooltip(self, x, y, f"{self.labels[self._hover]}\n{self.values[self._hover]} {self.unit}")

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
        super().__init__(master, height=self.ROW_H, bg=bg_of(master), highlightthickness=0)
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
            rounded_rect(self, x1, by, x2, by + 6, 3, fill="#EEEBE4", outline="")
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
