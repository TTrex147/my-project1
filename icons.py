"""
icons.py
Small, sharp line icons drawn with Pillow (no image files needed).
Use:  photo = icon("mail", "#7B877F", 22)     -> a PhotoImage you can put on a Canvas / Label

Every icon is drawn on a 24 x 24 grid, 6 times bigger, then shrunk. That keeps the edges smooth.
"""
import math

from PIL import Image, ImageDraw, ImageTk

SS = 6              # drawing is made 6x bigger, then shrunk (smooth edges)
_cache = {}         # keeps the PhotoImages alive (Tk forgets images that are not stored)


def _rgba(color, alpha=255):
    return (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16), alpha)


class _Pen:
    def __init__(self, draw, k, color, width):
        self.d, self.k = draw, k
        self.fill = _rgba(color)
        self.w = max(1, int(round(width * k)))

    def _pts(self, pts):
        return [(x * self.k, y * self.k) for x, y in pts]

    def line(self, pts):
        p = self._pts(pts)
        self.d.line(p, fill=self.fill, width=self.w, joint="curve")
        r = self.w / 2
        for x, y in (p[0], p[-1]):                      # round line ends
            self.d.ellipse((x - r, y - r, x + r, y + r), fill=self.fill)

    def circle(self, cx, cy, r, filled=False):
        k = self.k
        box = ((cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k)
        if filled:
            self.d.ellipse(box, fill=self.fill)
        else:
            self.d.ellipse(box, outline=self.fill, width=self.w)

    def rrect(self, x1, y1, x2, y2, r):
        k = self.k
        self.d.rounded_rectangle([x1 * k, y1 * k, x2 * k, y2 * k], radius=r * k,
                                 outline=self.fill, width=self.w)

    def arc(self, box, start, end):
        self.d.arc([v * self.k for v in box], start, end, fill=self.fill, width=self.w)


def _draw(name, p):
    if name == "dashboard":
        for x, y in ((4, 4), (13.5, 4), (4, 13.5), (13.5, 13.5)):
            p.rrect(x, y, x + 6.5, y + 6.5, 2)
    elif name == "edit":
        p.line([(4, 20), (5, 15), (16, 4), (20, 8), (9, 19), (4, 20)])
        p.line([(13, 7), (17, 11)])
    elif name == "bulb":
        p.circle(12, 10, 6.2)
        p.line([(9.5, 17), (14.5, 17)])
        p.line([(10.3, 20), (13.7, 20)])
        p.line([(9, 14.5), (9.5, 17)])
        p.line([(15, 14.5), (14.5, 17)])
    elif name == "list":
        for y in (7, 12, 17):
            p.line([(9.5, y), (20, y)])
            p.circle(5, y, 0.9, filled=True)
    elif name == "vote":
        p.circle(12, 12, 9)
        p.line([(12, 16.5), (12, 8)])
        p.line([(8.5, 11.5), (12, 8), (15.5, 11.5)])
    elif name == "user":
        p.circle(12, 8, 3.8)
        p.arc((4.5, 14.5, 19.5, 29.5), 180, 360)
    elif name == "users":
        p.circle(9, 8.5, 3.3)
        p.arc((3, 14.5, 15, 26.5), 180, 360)
        p.circle(16.5, 8, 2.7)
        p.arc((13, 13.5, 22, 22.5), 200, 360)
    elif name == "mail":
        p.rrect(3, 5.5, 21, 18.5, 3)
        p.line([(3.8, 7.8), (12, 13.5), (20.2, 7.8)])
    elif name == "star":
        pts = []
        for i in range(10):
            r = 9.3 if i % 2 == 0 else 4.2
            a = -math.pi / 2 + i * math.pi / 5
            pts.append((12 + r * math.cos(a), 12.8 + r * math.sin(a)))
        p.line(pts + [pts[0]])
    elif name == "chart":
        p.rrect(4.5, 12, 8.5, 20, 1.2)
        p.rrect(10, 5.5, 14, 20, 1.2)
        p.rrect(15.5, 9, 19.5, 20, 1.2)
    elif name == "logout":
        p.line([(10, 4), (5, 4), (5, 20), (10, 20)])
        p.line([(9, 12), (20, 12)])
        p.line([(16, 8), (20, 12), (16, 16)])
    elif name == "search":
        p.circle(10.5, 10.5, 6.5)
        p.line([(15.5, 15.5), (20.5, 20.5)])
    elif name == "bell":
        p.arc((6, 3, 18, 15), 180, 360)
        p.line([(6, 9), (6, 14), (4, 17.5)])
        p.line([(18, 9), (18, 14), (20, 17.5)])
        p.line([(4, 17.5), (20, 17.5)])
        p.arc((9.5, 16.5, 14.5, 22), 0, 180)
    elif name == "check":
        p.line([(5, 12.5), (10, 17.5), (19, 7)])
    elif name == "clock":
        p.circle(12, 12, 9)
        p.line([(12, 7), (12, 12), (15.5, 14)])
    elif name == "plus":
        p.line([(12, 5), (12, 19)])
        p.line([(5, 12), (19, 12)])
    elif name == "lock":
        p.rrect(5, 11, 19, 21, 3)
        p.arc((8, 4, 16, 12), 180, 360)
        p.line([(8, 8), (8, 11)])
        p.line([(16, 8), (16, 11)])
    elif name in ("eye", "eye_off"):
        p.arc((2, 5, 22, 25), 220, 320)
        p.arc((2, -1, 22, 19), 40, 140)
        p.circle(12, 12, 3)
        if name == "eye_off":
            p.line([(4, 20), (20, 4)])
    elif name == "send":
        p.line([(21, 3), (3, 10.5), (10, 13.5), (13, 21), (21, 3)])
        p.line([(10, 13.5), (21, 3)])
    elif name == "close":
        p.line([(6, 6), (18, 18)])
        p.line([(18, 6), (6, 18)])


def render(name, color="#7B877F", size=22, width=1.9):
    """Same as icon() but returns a Pillow image (no Tk window needed)."""
    big = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
    _draw(name, _Pen(ImageDraw.Draw(big), size * SS / 24, color, width))
    return big.resize((size, size), Image.LANCZOS)


def icon(name, color="#7B877F", size=22, width=1.9):
    """Returns a PhotoImage of the icon. Needs a Tk window to exist already."""
    key = (name, color, size, width)
    if key not in _cache:
        _cache[key] = ImageTk.PhotoImage(render(name, color, size, width))
    return _cache[key]
