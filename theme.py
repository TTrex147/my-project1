"""
theme.py
Colors, fonts and small helper functions (animation, colors, dates)
that are used by the whole app.
"""
import math
import time
import tkinter as tk
from datetime import datetime, timezone

# Tk will use a default font automatically if Segoe UI is not installed
FONT = "Segoe UI"


def font(size=10, weight="normal"):
    return (FONT, size, weight)


class C:
    """All the colors of the app in one place (soft beige page, white cards, sage-green brand)."""
    # page and cards
    BG = "#ECEAE4"
    WHITE = "#FFFFFF"
    CARD_BORDER = "#FFFFFF"
    SHADOW = "#DEDBD2"
    TEXT = "#1E2B25"
    MUTED = "#7B877F"
    BORDER = "#DAD7CE"
    ROW_HOVER = "#F2F6F3"
    DARK = "#1F2E27"
    # brand greens
    PRIMARY = "#3E6A53"
    PRIMARY_DARK = "#2C5040"
    PRIMARY_LIGHT = "#7FA48F"
    PRIMARY_SOFT = "#E3EEE6"
    PRIMARY_MIST = "#F0F5F1"
    # extra colors
    BLUE = "#4F8FD8"
    BLUE_SOFT = "#E1EDFB"
    GREEN = "#3E9B6E"
    GREEN_SOFT = "#DDF1E5"
    ORANGE = "#E69B3A"
    ORANGE_SOFT = "#FBEBD3"
    RED = "#D9564F"
    RED_SOFT = "#FBE3E1"
    PURPLE = "#8068C8"
    PURPLE_SOFT = "#ECE7F8"
    TEAL = "#2FA7A0"
    PINK = "#E07A8B"


CATEGORIES = ["Facilities", "Academics", "Teaching", "Technology", "Cafeteria", "Others"]

CATEGORY_COLORS = {
    "Facilities": "#5E8C6F",
    "Academics": "#6FA3D8",
    "Teaching": "#E9A15B",
    "Technology": "#8E7CC3",
    "Cafeteria": "#E07A8B",
    "Others": "#C9B458",
}

FEEDBACK_STATUSES = ["Pending", "In Progress", "Resolved"]
SUGGESTION_STATUSES = ["Pending", "Under Review", "Approved", "Rejected"]

# status name -> (background, text color)
STATUS_STYLES = {
    "Pending": (C.ORANGE_SOFT, "#B3741C"),
    "In Progress": (C.BLUE_SOFT, "#2F6FB8"),
    "Under Review": (C.BLUE_SOFT, "#2F6FB8"),
    "Resolved": (C.GREEN_SOFT, "#23805A"),
    "Approved": (C.GREEN_SOFT, "#23805A"),
    "Rejected": (C.RED_SOFT, "#B8403B"),
    "Active": (C.GREEN_SOFT, "#23805A"),
    "Inactive": ("#ECEAE4", C.MUTED),
    "Admin": (C.PURPLE_SOFT, "#6A52B0"),
    "Student": (C.PRIMARY_SOFT, C.PRIMARY),
    "Feedback": (C.BLUE_SOFT, "#2F6FB8"),
    "Suggestion": (C.PURPLE_SOFT, "#6A52B0"),
}

# colors used for the bars of the status charts
STATUS_COLORS = {
    "Pending": "#E9A15B",
    "In Progress": "#6FA3D8",
    "Under Review": "#6FA3D8",
    "Resolved": "#4E9B73",
    "Approved": "#4E9B73",
    "Rejected": "#D9645F",
}

# colors for the rank lists / extra decoration
PALETTE = ["#3E6A53", "#6FA3D8", "#E9A15B", "#8E7CC3", "#E07A8B", "#4E9B73", "#C9B458"]


# ---------------------------------------------------------------- colors
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def lerp_color(c1, c2, t):
    """Mix two colors. t=0 gives c1, t=1 gives c2."""
    t = max(0.0, min(1.0, t))
    a, b = hex_to_rgb(c1), hex_to_rgb(c2)
    return "#%02x%02x%02x" % tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def lighten(color, amount=0.2):
    return lerp_color(color, "#FFFFFF", amount)


def darken(color, amount=0.2):
    return lerp_color(color, "#000000", amount)


def bg_of(widget):
    """Background color of a widget (white if it has none)."""
    try:
        return widget.cget("bg")
    except tk.TclError:
        return C.WHITE


# ---------------------------------------------------------------- easing
def linear(t):
    return t


def ease_out_cubic(t):
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    return 3 * t * t - 2 * t * t * t


def ease_out_back(t):
    c1, c3 = 1.4, 2.4
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


# ---------------------------------------------------------------- animation
class Animation:
    """Runs update(t) many times (about 60 per second) while t goes from 0 to 1."""

    def __init__(self, widget, duration, update, done=None, ease=ease_out_cubic, delay=0):
        self.widget = widget
        self.duration = max(1, duration)
        self.update = update
        self.done = done
        self.ease = ease
        self.cancelled = False
        self.running = True
        self.start = time.perf_counter()
        if delay > 0:
            try:
                widget.after(delay, self._begin)
            except tk.TclError:
                self.running = False
        else:
            self._begin()

    def _begin(self):
        if self.cancelled:
            return
        self.start = time.perf_counter()
        self._tick()

    def cancel(self):
        self.cancelled = True
        self.running = False

    def _tick(self):
        if self.cancelled:
            return
        try:
            if not self.widget.winfo_exists():
                self.running = False
                return
            t = (time.perf_counter() - self.start) * 1000 / self.duration
            if t >= 1:
                self.running = False
                self.update(self.ease(1.0))
                if self.done:
                    self.done()
                return
            self.update(self.ease(t))
            self.widget.after(16, self._tick)
        except tk.TclError:
            self.running = False


def animate(widget, duration, update, done=None, ease=ease_out_cubic, delay=0):
    return Animation(widget, duration, update, done, ease, delay)


def stop(anim):
    if anim is not None:
        anim.cancel()


# ---------------------------------------------------------------- drawing
def rounded_points(x1, y1, x2, y2, r):
    return [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]


def pill_points(x1, y1, x2, y2, steps=14):
    """Points of a pill / circle shape (ends are exact half circles)."""
    r = (y2 - y1) / 2
    pts = []
    for i in range(steps + 1):                        # right end, top to bottom
        a = -math.pi / 2 + math.pi * i / steps
        pts += [x2 - r + r * math.cos(a), y1 + r + r * math.sin(a)]
    for i in range(steps + 1):                        # left end, bottom to top
        a = math.pi / 2 + math.pi * i / steps
        pts += [x1 + r + r * math.cos(a), y1 + r + r * math.sin(a)]
    return pts


def rounded_rect(canvas, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    return canvas.create_polygon(rounded_points(x1, y1, x2, y2, r), smooth=True, **kw)


def ellipsize(text, tk_font, max_width):
    """Cut a text with '...' so it fits in max_width pixels."""
    if tk_font.measure(text) <= max_width:
        return text
    while text and tk_font.measure(text + "...") > max_width:
        text = text[:-1]
    return text.rstrip() + "..."


# ---------------------------------------------------------------- dates
def to_local(ts):
    """Database dates are saved in UTC. This changes them to the computer's local time."""
    try:
        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return dt.astimezone()
    except (ValueError, TypeError):
        return None


def fmt_date(ts):
    dt = to_local(ts)
    return dt.strftime("%Y-%m-%d") if dt else str(ts or "")


def fmt_datetime(ts):
    dt = to_local(ts)
    return dt.strftime("%b %d, %Y  %I:%M %p") if dt else str(ts or "")
