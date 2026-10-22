"""
login_glass.py
The login page: a see-through "glass" card on top of a full-window picture.

How the glass works (simple idea):
  1. the background picture is cut to fit the window
  2. the part behind the card is blurred and covered with a little white
  3. that result is drawn as the card, and the text/buttons are put on top of it
Change GLASS_BLUR and GLASS_TINT below to make the glass more or less see-through.
"""
import json
import math
import os
import tkinter as tk
import tkinter.font as tkfont

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageStat, ImageTk

from database import app_folder, resource_path
from icons import icon
from managers import AppError
from theme import FONT, C, animate, font, lerp_color, linear, rounded_points, rounded_rect, stop
from widgets import CanvasButton, Modal, StyledEntry, canvas_link, form_label, rr_mask

REMEMBER_FILE = os.path.join(app_folder(), "remember.json")


def cover_crop(img, width, height, anchor_y=0.5):
    """Scale the picture so it covers the whole window, then cut the extra parts away."""
    scale = max(width / img.width, height / img.height)
    big = img.resize((math.ceil(img.width * scale), math.ceil(img.height * scale)), Image.BICUBIC)
    left = (big.width - width) // 2
    top = int((big.height - height) * anchor_y)
    return big.crop((left, top, left + width, top + height))


def hex_of(rgb):
    return "#%02x%02x%02x" % tuple(int(v) for v in rgb)


def put_rounded(img, x, y, w, h, radius, fill, ring=None):
    """Draw a smooth rounded box (and an optional thin border) on a Pillow image."""
    layer = Image.new("RGBA", (w, h), fill)
    layer.putalpha(rr_mask(w, h, radius))
    img.alpha_composite(layer, (x, y))
    if ring:
        inner = Image.new("L", (w, h), 0)
        inner.paste(rr_mask(w - 3, h - 3, max(1, radius - 1.5)), (1, 1))
        edge = Image.new("RGBA", (w, h), ring)
        edge.putalpha(ImageChops.subtract(rr_mask(w, h, radius), inner))
        img.alpha_composite(edge, (x, y))


class GlassLoginScreen(tk.Canvas):
    CARD_W, CARD_H, MARGIN = 420, 540, 70
    GLASS_BLUR = 20          # bigger number = more frosted
    GLASS_TINT = 84          # 0-255, how white the glass is (smaller = more see-through)
    SHOW_DEMO_HINT = True

    def __init__(self, parent, app):
        super().__init__(parent, bg="#CFE0EC", highlightthickness=0, bd=0)
        self.app = app
        self.src = Image.open(resource_path("assets", "login_bg.jpg")).convert("RGB")
        self.role, self.remember, self.show_pw, self.error_text = "student", False, False, ""
        self._size, self._job, self._first, self._seg_x = (0, 0), None, True, 0.0
        self._photos, self._rings, self._anim = None, {}, None
        self.user_entry = StyledEntry(self, placeholder="Username", width=24, size=11, bare=True)
        self.pass_entry = StyledEntry(self, placeholder="Password", password=True, width=24, size=11, bare=True)
        self._load_remembered()
        for name, entry in (("user", self.user_entry), ("pass", self.pass_entry)):
            entry.bind("<Return>", lambda e: self._login())
            entry.bind("<FocusIn>", lambda e, n=name: self._ring(n, True), add="+")
            entry.bind("<FocusOut>", lambda e, n=name: self._ring(n, False), add="+")
        self.bind("<Configure>", self._on_configure)

    # ------------------------------------------------------------ remember me
    def _load_remembered(self):
        try:
            with open(REMEMBER_FILE, encoding="utf-8") as f:
                data = json.load(f)
            self.user_entry.set_value(data.get("username", ""))
            self.role = data.get("role", "student") if data.get("role") in ("student", "admin") else "student"
            self.remember = bool(data.get("username"))
            self._seg_x = 161.0 if self.role == "admin" else 0.0
        except (OSError, ValueError):
            pass

    def _save_remembered(self, username):
        try:
            if self.remember:
                with open(REMEMBER_FILE, "w", encoding="utf-8") as f:
                    json.dump({"username": username, "role": self.role}, f)
            elif os.path.exists(REMEMBER_FILE):
                os.remove(REMEMBER_FILE)
        except OSError:
            pass

    # ------------------------------------------------------------ pictures
    def _on_configure(self, e):
        if (e.width, e.height) == self._size or e.width < 300 or e.height < 300:
            return
        self._size = (e.width, e.height)
        if self._job:
            self.after_cancel(self._job)
        if self._first:
            self._build()
        else:
            self._job = self.after(90, self._build)       # wait until the window stops changing size

    def _make_images(self, W, H):
        cw, ch, m = self.CARD_W, self.CARD_H, self.MARGIN
        cover = cover_crop(self.src, W, H, 0.58)
        left, top = W // 2 - cw // 2, H // 2 + 20 - ch // 2
        # --- the glass: blurred copy of what is behind the card + a little white
        blur = cover.crop((left, top, left + cw, top + ch)).filter(
            ImageFilter.GaussianBlur(self.GLASS_BLUR)).convert("RGBA")
        glass = Image.alpha_composite(blur, Image.new("RGBA", (cw, ch), (255, 255, 255, self.GLASS_TINT)))
        sheen = Image.new("RGBA", (cw, ch), (255, 255, 255, 0))
        sheen.putalpha(ImageOps.invert(Image.linear_gradient("L").resize((cw, ch))).point(lambda v: int(v * 0.25)))
        glass = Image.alpha_composite(glass, sheen)
        mean = ImageStat.Stat(glass.convert("RGB").crop((45, 190, 375, 300))).mean
        pill_fill = lerp_color(hex_of(mean), "#FFFFFF", 0.58)
        track_fill = lerp_color(hex_of(mean), "#FFFFFF", 0.40)
        # --- the card picture (shadow + glass + border + the two input boxes)
        card = Image.new("RGBA", (cw + 2 * m, ch + 2 * m), (0, 0, 0, 0))
        shadow = Image.new("RGBA", card.size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle([m, m + 20, m + cw, m + ch + 20], radius=30, fill=(25, 45, 40, 95))
        card.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(26)))
        glass.putalpha(rr_mask(cw, ch, 30))
        card.alpha_composite(glass, (m, m))
        outer = rr_mask(cw, ch, 30)
        inner = Image.new("L", (cw, ch), 0)
        inner.paste(rr_mask(cw - 4, ch - 4, 28), (2, 2))
        border = Image.new("RGBA", (cw, ch), (255, 255, 255, 235))
        border.putalpha(ImageChops.subtract(outer, inner).point(lambda v: int(v * 0.85)))
        card.alpha_composite(border, (m, m))
        ring = lerp_color(pill_fill, "#FFFFFF", 0.6)
        for py in (190, 252):
            put_rounded(card, m + 45, m + py, 330, 48, 24, pill_fill, ring)
        return ImageTk.PhotoImage(cover.convert("RGB")), ImageTk.PhotoImage(card), pill_fill, track_fill, ring

    # ------------------------------------------------------------ drawing
    def _build(self):
        self._job = None
        W, H = self.winfo_width(), self.winfo_height()
        bg, card, pill_fill, track_fill, ring_col = self._make_images(W, H)
        self._photos = (bg, card)
        self.delete("all")
        self.create_image(0, 0, anchor="nw", image=bg)
        self._draw_nav(W)
        cx, cy = W // 2, H // 2 + 20
        L, T = cx - self.CARD_W // 2, cy - self.CARD_H // 2
        self.create_image(cx, cy, image=card, tags="card")
        self._draw_card(L, T, pill_fill, track_fill, ring_col)
        if self._first:
            self._first = False
            self._slide_in()
            self.after(500, (self.pass_entry if self.user_entry.value() else self.user_entry).focus_set)

    def _draw_nav(self, W):
        # little graduation-cap logo + name
        x, y = 62, 46
        self.create_polygon(x, y - 14, x + 20, y - 6, x, y + 2, x - 20, y - 6, fill=C.PRIMARY_DARK, outline="")
        self.create_polygon(x - 11, y - 1, x, y + 5, x + 11, y - 1, x + 11, y + 8, x, y + 13, x - 11, y + 8,
                            fill=C.PRIMARY, outline="")
        self.create_line(x + 17, y - 5, x + 17, y + 8, fill="#E9B949", width=2)
        self.create_text(x + 36, y - 8, text="Student Feedback", anchor="w", fill=C.DARK, font=font(13, "bold"))
        self.create_text(x + 36, y + 11, text="Suggestion Management System", anchor="w", fill="#4B5A52", font=font(9))
        CanvasButton(self, (W - 62 - 130, 26, W - 62, 68), "Register", self._open_register, fill="#F5F9F6",
                     hover=C.PRIMARY_SOFT, fg=C.PRIMARY, outline=C.PRIMARY, radius=14, size=11, tag="nav")

    def _draw_card(self, L, T, pill_fill, track_fill, ring_col):
        X, Y = (lambda v: L + v), (lambda v: T + v)
        cx = L + self.CARD_W / 2
        dark, soft = C.DARK, "#4B5A52"
        self.create_text(cx, Y(62), text="Login", fill=dark, font=font(28, "bold"), tags="card")
        self.create_text(cx, Y(98), text="Welcome back! Please sign in to continue.", fill=soft,
                         font=font(10), tags="card")
        # ---- role switch (Student | Admin) with a sliding dark button
        self._seg_geo = (X(49), Y(132))
        track = rounded_rect(self, X(45), Y(128), X(375), Y(168), 20, fill=track_fill, outline="", tags="card")
        self._seg = rounded_rect(self, X(49) + self._seg_x, Y(132), X(49) + self._seg_x + 161, Y(164), 16,
                                 fill=dark, outline="", tags="card")
        self._role_labels = {}
        for name, label, mid in (("student", "Student", X(49) + 80.5), ("admin", "Admin", X(49) + 161 + 80.5)):
            self._role_labels[name] = self.create_text(mid, Y(148), text=label, font=font(10, "bold"),
                                                       fill="#FFFFFF" if self.role == name else dark, tags="card")
        for item in (track, self._seg, *self._role_labels.values()):
            self.tag_bind(item, "<Button-1>", lambda e, L=L: self._set_role("admin" if e.x > L + 210 else "student"))
        # ---- input boxes
        self._rings = {}
        for name, py, ico in (("user", 190, "user"), ("pass", 252, "lock")):
            self._rings[name] = [rounded_rect(self, X(45) + 1, Y(py) + 1, X(375) - 1, Y(py + 48) - 1, 23, fill="",
                                              outline=ring_col, width=2, tags="card"), ring_col, None]
            self.create_image(X(45) + 28, Y(py + 24), image=icon(ico, "#5C6B63", 20), tags="card")
        self.user_entry.configure(bg=pill_fill)
        self.pass_entry.configure(bg=pill_fill)
        self.create_window(X(45) + 50, Y(190 + 24), window=self.user_entry, anchor="w", width=330 - 50 - 20,
                           height=32, tags="card")
        self.create_window(X(45) + 50, Y(252 + 24), window=self.pass_entry, anchor="w", width=330 - 50 - 52,
                           height=32, tags="card")
        self._eye = self.create_image(X(375) - 28, Y(252 + 24), image=icon("eye" if self.show_pw else "eye_off",
                                                                          "#5C6B63", 20), tags="card")
        self.tag_bind(self._eye, "<Button-1>", lambda e: self._toggle_password())
        self.tag_bind(self._eye, "<Enter>", lambda e: self.configure(cursor="hand2"))
        self.tag_bind(self._eye, "<Leave>", lambda e: self.configure(cursor=""))
        # ---- message
        self._error = self.create_text(cx, Y(318), text=self.error_text, fill="#C23B40", font=font(9, "bold"),
                                       width=320, justify="center", tags="card")
        # ---- remember me + forgot password
        self._box = rounded_rect(self, X(45), Y(334), X(63), Y(352), 5, fill=pill_fill if not self.remember else C.PRIMARY,
                                 outline="#5C6B63" if not self.remember else C.PRIMARY, width=1.5, tags="card")
        self._tick = self.create_image(X(54), Y(343), image=icon("check", "#FFFFFF", 14),
                                       state="normal" if self.remember else "hidden", tags="card")
        self._pill_fill = pill_fill
        remember = self.create_text(X(72), Y(343), text="Remember me", anchor="w", fill=dark, font=font(10), tags="card")
        for item in (self._box, self._tick, remember):
            self.tag_bind(item, "<Button-1>", lambda e: self._toggle_remember())
            self.tag_bind(item, "<Enter>", lambda e: self.configure(cursor="hand2"))
            self.tag_bind(item, "<Leave>", lambda e: self.configure(cursor=""))
        canvas_link(self, X(375), Y(343), "Forgot Password?", self._forgot, color=dark, hover=C.PRIMARY,
                    size=10, anchor="e", bold=False, tag="card")
        # ---- login button
        CanvasButton(self, (X(45), Y(372), X(375), Y(420)), "Login", self._login, fill=dark, hover="#35483D",
                     press="#111C17", radius=16, size=12, tag="card")
        # ---- register line
        f = tkfont.Font(family=FONT, size=10)
        f2 = tkfont.Font(family=FONT, size=10, weight="bold")
        a, b = "Don't have an account?", "Register"
        total = f.measure(a) + 6 + f2.measure(b)
        x0 = cx - total / 2
        self.create_text(x0, Y(452), text=a, anchor="w", fill=soft, font=font(10), tags="card")
        canvas_link(self, x0 + f.measure(a) + 6, Y(452), b, self._open_register, color=dark, hover=C.PRIMARY,
                    anchor="w", tag="card")
        if self.SHOW_DEMO_HINT:
            self.create_text(cx, Y(498), text="Demo:  admin / admin123   \u2022   tungtungsahur / student123",
                             fill="#5C6B63", font=font(8), tags="card")

    # ------------------------------------------------------------ small actions
    def _slide_in(self):
        self.move("card", 0, 34)
        last = [34.0]

        def step(t):
            now = 34 * (1 - t)
            self.move("card", 0, now - last[0])
            last[0] = now
        animate(self, 650, step)

    def _shake(self):
        last = [0.0]

        def step(t):
            now = math.sin(t * math.pi * 7) * (1 - t) * 14
            self.move("card", now - last[0], 0)
            last[0] = now
        animate(self, 450, step, ease=linear)

    def _ring(self, name, focused):
        """Glow around the input box while you type in it."""
        ring = self._rings.get(name)
        if not ring:
            return
        item, base, anim = ring
        stop(anim)
        start = self.itemcget(item, "outline")
        target = C.PRIMARY if focused else base

        def step(t):
            self.itemconfigure(item, outline=lerp_color(start, target, t))
        ring[2] = animate(self, 180, step, ease=linear)

    def _set_role(self, role):
        if role == self.role:
            return
        self.role = role
        if not hasattr(self, "_seg_geo"):              # card not drawn yet: just remember the choice
            self._seg_x = 161.0 if role == "admin" else 0.0
            return
        stop(self._anim)
        start, end = self._seg_x, (161.0 if role == "admin" else 0.0)
        left, top = self._seg_geo

        def step(t):
            self._seg_x = start + (end - start) * t
            x1 = left + self._seg_x
            self.coords(self._seg, *rounded_points(x1, top, x1 + 161, top + 32, 16))
            self.itemconfigure(self._role_labels["student"], fill=self._mix(role == "student", t))
            self.itemconfigure(self._role_labels["admin"], fill=self._mix(role == "admin", t))
        self._anim = animate(self, 260, step)

    @staticmethod
    def _mix(becoming_selected, t):
        return lerp_color(C.DARK, "#FFFFFF", t) if becoming_selected else lerp_color("#FFFFFF", C.DARK, t)

    def _toggle_password(self):
        self.show_pw = not self.show_pw
        self.pass_entry.set_password_visible(self.show_pw)
        self.itemconfigure(self._eye, image=icon("eye" if self.show_pw else "eye_off", "#5C6B63", 20))

    def _toggle_remember(self):
        self.remember = not self.remember
        self.itemconfigure(self._box, fill=C.PRIMARY if self.remember else self._pill_fill,
                           outline=C.PRIMARY if self.remember else "#5C6B63")
        self.itemconfigure(self._tick, state="normal" if self.remember else "hidden")

    def _show_error(self, message):
        self.error_text = message
        self.itemconfigure(self._error, text=message)
        animate(self, 350, lambda t: self.itemconfigure(self._error, fill=lerp_color("#E9B3B0", "#C23B40", t)),
                ease=linear)

    # ------------------------------------------------------------ login
    def _login(self):
        username = self.user_entry.value()
        try:
            user = self.app.services.auth.login(username, self.pass_entry.value(strip=False), self.role)
        except AppError as e:
            self._show_error(str(e))
            self._shake()
            return
        self._save_remembered(username)
        self.app.login_success(user)

    def _forgot(self):
        m = Modal(self.app, "Forgot your password?", width=470, accent=C.PRIMARY)
        tk.Label(m.body, text="This system does not send emails. To get back into your account:",
                 bg=C.WHITE, fg=C.TEXT, font=font(10), wraplength=410, justify="left").pack(anchor="w")
        for line in ("1.  Ask a school admin to open  Manage Users.",
                     "2.  The admin clicks  Edit  on your account.",
                     "3.  The admin types a new password and saves.",
                     "4.  Log in with the new password, then change it in Profile."):
            tk.Label(m.body, text=line, bg=C.WHITE, fg=C.MUTED, font=font(10), wraplength=410,
                     justify="left").pack(anchor="w", pady=(6, 0))
        from widgets import HoverButton
        HoverButton(m.footer, "Got it", m.close, "primary").pack(side="right")
        m.show()

    def _open_register(self):
        from widgets import HoverButton
        m = Modal(self.app, "Create Student Account", width=480, accent=C.GREEN)
        tk.Label(m.body, text="Fill in the form below to join the system.", bg=C.WHITE, fg=C.MUTED,
                 font=font(10)).pack(anchor="w", pady=(0, 10))
        entries = {}
        for key, label, ph, pw in (("name", "Full Name", "e.g. Juan Dela Cruz", False),
                                   ("user", "Username", "4-20 letters or numbers", False),
                                   ("pass", "Password", "At least 6 characters", True),
                                   ("conf", "Confirm Password", "Type the password again", True)):
            form_label(m.body, label, True).pack(anchor="w", pady=(8, 4))
            entries[key] = StyledEntry(m.body, placeholder=ph, password=pw, width=40)
            entries[key].pack(fill="x", ipady=3)
        err = tk.Label(m.body, text="", bg=C.WHITE, fg=C.RED, font=font(9), wraplength=420, justify="left")
        err.pack(anchor="w", pady=(10, 0))

        def create():
            try:
                self.app.services.auth.register_student(entries["name"].value(), entries["user"].value(),
                                                        entries["pass"].value(False), entries["conf"].value(False))
            except AppError as e:
                err.configure(text=str(e))
                return
            self.user_entry.set_value(entries["user"].value().lower())
            self.role = "student"
            m.close()
            self._build()
            self.app.toast.show("Account created! You can log in now.", "success")

        HoverButton(m.footer, "Create Account", create, "success").pack(side="right")
        HoverButton(m.footer, "Cancel", m.close, "gray").pack(side="right", padx=8)
        m.show()
        entries["name"].focus_set()
