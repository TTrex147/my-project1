"""
screens.py
Every screen (window page) of the app. Each screen is a class that inherits from BaseScreen.

Student screens : StudentDashboard, SubmitFeedbackScreen, SubmitSuggestionScreen,
                  MySubmissionsScreen, SuggestionBoardScreen, ProfileScreen
Admin screens   : AdminDashboard, ManageFeedbackScreen, RespondScreen,
                  ManageSuggestionsScreen, ManageUsersScreen, ReportsScreen, ProfileScreen
"""
import math
import random
import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import filedialog

from managers import AppError
from theme import (C, CATEGORIES, CATEGORY_COLORS, FEEDBACK_STATUSES, STATUS_COLORS,
                   SUGGESTION_STATUSES, animate, fmt_date, fmt_datetime, font, lerp_color,
                   linear, rounded_rect)
from widgets import (AnimatedBarChart, AnimatedDonutChart, AnimatedLineChart, AnimatedRankList,
                     Badge, Card, Column, DataTable, HoverButton, LinkLabel, Modal, Pager,
                     ScrollFrame, StatCard, StyledEntry, StyledText, category_badge, confirm,
                     form_label, make_combo)


# ======================================================================
#  Small helpers used by many screens
# ======================================================================
def card_title(parent, text, link_text=None, link_cmd=None, bg=C.WHITE):
    row = tk.Frame(parent, bg=bg)
    row.pack(fill="x", pady=(0, 12))
    tk.Label(row, text=text, bg=bg, fg=C.TEXT, font=font(12, "bold")).pack(side="left")
    if link_text:
        LinkLabel(row, link_text, link_cmd).pack(side="right")
    return row


def flash_error(label, message):
    """Show a red message that fades in."""
    label.configure(text=message)
    animate(label, 350, lambda t: label.configure(fg=lerp_color(label.cget("bg"), C.RED, t)), ease=linear)


def submission_row(item, actions):
    return {"cells": {
        "id": item.code, "type": item.kind.capitalize(), "title": item.title, "category": item.category,
        "status": item.status, "date": item.date, "author": item.author,
        "votes": item.votes if item.kind == "suggestion" else ""}, "actions": actions}


def open_details(app, item):
    """Pop-up with all details of a feedback or suggestion."""
    svc = app.services
    accent = C.BLUE if item.kind == "feedback" else C.PURPLE
    m = Modal(app, f"{item.kind.capitalize()} {item.code}", width=600, accent=accent)
    tk.Label(m.body, text=item.title, bg=C.WHITE, fg=C.TEXT, font=font(13, "bold"),
             wraplength=540, justify="left").pack(anchor="w")
    badges = tk.Frame(m.body, bg=C.WHITE)
    badges.pack(anchor="w", pady=(10, 4))
    category_badge(badges, item.category).pack(side="left", padx=(0, 8))
    Badge(badges, item.status).pack(side="left")
    tk.Label(m.body, text=f"Submitted by {item.author} on {fmt_datetime(item.created_at)}",
             bg=C.WHITE, fg=C.MUTED, font=font(9)).pack(anchor="w", pady=(0, 10))
    box = tk.Frame(m.body, bg="#F6F8FC")
    box.pack(fill="x")
    tk.Label(box, text=item.description, bg="#F6F8FC", fg=C.TEXT, font=font(10), wraplength=520,
             justify="left").pack(anchor="w", padx=14, pady=12)
    if item.kind == "suggestion":
        tk.Label(m.body, text=f"\u25B2  {item.votes} votes", bg=C.WHITE, fg=C.PURPLE,
                 font=font(11, "bold")).pack(anchor="w", pady=(12, 0))
    else:
        tk.Label(m.body, text="Admin Responses", bg=C.WHITE, fg=C.TEXT,
                 font=font(11, "bold")).pack(anchor="w", pady=(14, 6))
        responses = svc.responses.for_feedback(item.id)
        if not responses:
            tk.Label(m.body, text="No response yet.", bg=C.WHITE, fg=C.MUTED, font=font(10)).pack(anchor="w")
        for r in responses[:3]:
            card = tk.Frame(m.body, bg=C.BLUE_SOFT)
            card.pack(fill="x", pady=3)
            tk.Label(card, text=f"{r['admin_name']}  \u2022  {fmt_datetime(r['created_at'])}", bg=C.BLUE_SOFT,
                     fg=C.BLUE, font=font(9, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
            tk.Label(card, text=r["response_text"], bg=C.BLUE_SOFT, fg=C.TEXT, font=font(10),
                     wraplength=510, justify="left").pack(anchor="w", padx=12, pady=(2, 8))
    HoverButton(m.footer, "Close", m.close, "gray").pack(side="right")
    m.show()


# ======================================================================
#  Base class for all screens inside the main window
# ======================================================================
class BaseScreen(tk.Frame):
    def __init__(self, parent, app, **params):
        super().__init__(parent, bg=C.BG)
        self.app, self.svc, self.user = app, app.services, app.user
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True)
        self.page = tk.Frame(self.scroll.inner, bg=C.BG)
        self.page.pack(fill="both", expand=True, padx=30, pady=24)
        self.build(**params)

    def build(self, **params):
        raise NotImplementedError

    def on_data_changed(self):
        """Called when another user changed the database (live sync). Override if needed."""

    def header(self, title, subtitle=""):
        box = tk.Frame(self.page, bg=C.BG)
        box.pack(fill="x", pady=(0, 18))
        tk.Label(box, text=title, bg=C.BG, fg=C.TEXT, font=font(20, "bold")).pack(anchor="w")
        if subtitle:
            tk.Label(box, text=subtitle, bg=C.BG, fg=C.MUTED, font=font(10)).pack(anchor="w", pady=(2, 0))
        return box


# ======================================================================
#  LOGIN
# ======================================================================
class LoginScreen(tk.Frame):
    SHOW_DEMO_HINT = True

    def __init__(self, parent, app):
        super().__init__(parent, bg=C.WHITE)
        self.app = app
        self.left = tk.Canvas(self, width=410, highlightthickness=0, bg=C.NAVY)
        self.left.pack(side="left", fill="y")
        self.left.pack_propagate(False)
        self.bubbles = []
        self.left.bind("<Configure>", self._draw_left)
        right = tk.Frame(self, bg=C.WHITE)
        right.pack(side="left", fill="both", expand=True)
        self.form = tk.Frame(right, bg=C.WHITE)
        self.form.place(relx=0.5, rely=0.5, anchor="center")
        self._build_form()
        self._float()

    # ------------------------------------------------ left side (gradient + floating bubbles)
    @staticmethod
    def _grad(y, h):
        return lerp_color("#071E48", "#1F6FEB", (y / max(h, 1)) * 0.9)

    def _draw_left(self, e):
        w, h = e.width, e.height
        c = self.left
        c.delete("all")
        for i in range(70):
            y1, y2 = h * i / 70, h * (i + 1) / 70 + 1
            c.create_rectangle(0, y1, w, y2, fill=self._grad(y1, h), outline="")
        rng = random.Random(8)
        self.bubbles = []
        for _ in range(10):
            r = rng.randint(28, 85)
            x, y = rng.randint(0, w), rng.randint(0, h)
            color = rng.choice(["#7C5CFC", "#14B8C4", "#3B9DF8", "#EC4899", "#FFC53D"])
            item = c.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="")
            self.bubbles.append({"item": item, "x": x, "y": y, "r": r, "color": color,
                                 "vy": rng.uniform(0.35, 0.9), "vx": rng.uniform(-0.25, 0.25)})
        cx, top = w / 2, h / 2 - 150
        # graduation cap logo
        c.create_polygon(cx, top, cx + 48, top + 19, cx, top + 38, cx - 48, top + 19, fill="white", outline="", tags="fg")
        c.create_polygon(cx - 27, top + 30, cx, top + 42, cx + 27, top + 30, cx + 27, top + 49, cx, top + 60,
                         cx - 27, top + 49, fill="#CFE0FF", outline="", tags="fg")
        c.create_line(cx + 40, top + 22, cx + 40, top + 48, fill="#FFC53D", width=3, tags="fg")
        c.create_oval(cx + 36, top + 46, cx + 44, top + 56, fill="#FFC53D", outline="", tags="fg")
        c.create_text(cx, top + 120, text="Integrated Student\nFeedback and Suggestion\nManagement System",
                      fill="white", font=font(17, "bold"), justify="center", tags="fg")
        c.create_text(cx, top + 215, text="Your voice matters. Help us\nbuild a better school.",
                      fill="#BCD3FA", font=font(11), justify="center", tags="fg")
        c.tag_raise("fg")

    def _float(self):
        try:
            h = self.left.winfo_height()
            for b in self.bubbles:
                b["y"] -= b["vy"]
                b["x"] += b["vx"]
                if b["y"] + b["r"] < 0:
                    b["y"] = h + b["r"]
                x, y, r = b["x"], b["y"], b["r"]
                self.left.coords(b["item"], x - r, y - r, x + r, y + r)
                self.left.itemconfigure(b["item"], fill=lerp_color(self._grad(y, h), b["color"], 0.22))
            self.after(33, self._float)
        except tk.TclError:
            pass

    # ------------------------------------------------ right side (form)
    def _build_form(self):
        f = self.form
        tk.Label(f, text="Login", bg=C.WHITE, fg=C.TEXT, font=font(26, "bold")).pack(pady=(0, 4))
        tk.Label(f, text="Welcome back! Please sign in to continue.", bg=C.WHITE, fg=C.MUTED,
                 font=font(10)).pack(pady=(0, 22))
        self.username = StyledEntry(f, placeholder="Username", width=36, size=11)
        self.username.pack(fill="x", ipady=5)
        row = tk.Frame(f, bg=C.WHITE)
        row.pack(fill="x", pady=(14, 0))
        self.password = StyledEntry(row, placeholder="Password", password=True, width=30, size=11)
        self.password.pack(side="left", fill="x", expand=True, ipady=5)
        self._show = False
        self.eye = LinkLabel(row, "Show", self._toggle_password)
        self.eye.pack(side="left", padx=(8, 0))
        tk.Label(f, text="Select Role", bg=C.WHITE, fg=C.TEXT, font=font(10, "bold")).pack(anchor="w", pady=(16, 5))
        self.role = make_combo(f, ["Student", "Admin"], width=36, value="Student")
        self.role.pack(fill="x")
        self.error = tk.Label(f, text="", bg=C.WHITE, fg=C.RED, font=font(9), wraplength=330, justify="left")
        self.error.pack(anchor="w", pady=(10, 0))
        self.button = HoverButton(f, "Login", self._login, "primary", height=44, size=11)
        self.button.pack(fill="x", pady=(8, 0))
        links = tk.Frame(f, bg=C.WHITE)
        links.pack(pady=(16, 0))
        tk.Label(links, text="Don't have an account?", bg=C.WHITE, fg=C.MUTED, font=font(9)).pack(side="left")
        LinkLabel(links, "Register", self._open_register).pack(side="left", padx=(5, 0))
        if self.SHOW_DEMO_HINT:
            tk.Label(f, text="Demo:  admin / admin123   \u2022   juan123 / student123", bg=C.WHITE,
                     fg="#9AA6BE", font=font(8)).pack(pady=(22, 0))
        for w in (self.username, self.password):
            w.bind("<Return>", lambda e: self._login())
        self.after(250, self.username.focus_set)

    def _toggle_password(self):
        self._show = not self._show
        self.password.set_password_visible(self._show)
        self.eye.configure(text="Hide" if self._show else "Show")

    def _shake(self):
        animate(self.form, 450, lambda t: self.form.place_configure(x=math.sin(t * math.pi * 7) * (1 - t) * 14),
                done=lambda: self.form.place_configure(x=0), ease=linear)

    def _login(self):
        try:
            user = self.app.services.auth.login(self.username.value(), self.password.value(strip=False),
                                                self.role.get().lower())
        except AppError as e:
            flash_error(self.error, str(e))
            self._shake()
            return
        self.app.login_success(user)

    def _open_register(self):
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
                flash_error(err, str(e))
                return
            self.username.set_value(entries["user"].value().lower())
            m.close()
            self.app.toast.show("Account created! You can log in now.", "success")

        HoverButton(m.footer, "Create Account", create, "success").pack(side="right")
        HoverButton(m.footer, "Cancel", m.close, "gray").pack(side="right", padx=8)
        m.show()
        entries["name"].focus_set()


# ======================================================================
#  DASHBOARDS
# ======================================================================
class StudentDashboard(BaseScreen):
    def build(self):
        self.header("Dashboard", f"Welcome back, {self.user.first_name}! Here is what is happening with your submissions.")
        row = tk.Frame(self.page, bg=C.BG)
        row.pack(fill="x")
        specs = [("My Feedback", "\u2709", C.BLUE, "#E3EEFF"), ("My Suggestions", "\u2726", C.GREEN, C.GREEN_SOFT),
                 ("Total Votes", "\u25B2", C.PURPLE, C.PURPLE_SOFT), ("Resolved", "\u2713", C.ORANGE, C.ORANGE_SOFT)]
        self.stats = []
        for i, (label, glyph, color, soft) in enumerate(specs):
            row.grid_columnconfigure(i, weight=1, uniform="stat")
            card = StatCard(row, label, glyph, color, soft, delay=i * 130)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0 if i == 3 else 8))
            self.stats.append(card)
        lower = tk.Frame(self.page, bg=C.BG)
        lower.pack(fill="both", expand=True, pady=(18, 0))
        lower.grid_columnconfigure(0, weight=3, uniform="low")
        lower.grid_columnconfigure(1, weight=2, uniform="low")
        recent = Card(lower, accent=C.BLUE)
        recent.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        card_title(recent.body, "Recent Submissions", "View All", lambda: self.app.navigate("my_submissions"))
        self.table = DataTable(recent.body, [Column("Type", "type", 112, "badge"), Column("Title", "title", 160, "title"),
                                             Column("Status", "status", 132, "badge"), Column("Date", "date", 105)],
                               page_size=5, row_height=44, footer=False,
                               empty_text="No submissions yet. Send your first feedback!")
        self.table.pack(fill="x")
        top = Card(lower, accent=C.PURPLE)
        top.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        card_title(top.body, "Top Voted Suggestions", "View All", lambda: self.app.navigate("board"))
        self.rank = AnimatedRankList(top.body, on_click=lambda i: self.app.navigate("board"))
        self.rank.pack(fill="x")
        self.load(first=True)

    def load(self, first=False):
        s = self.svc.reports.student_stats(self.user.user_id)
        for card, value in zip(self.stats, (s["feedback"], s["suggestions"], s["votes"], s["resolved"])):
            card.set_value(value)
        rows = [{"cells": {"type": r["type"], "title": r["title"], "status": r["status"],
                           "date": fmt_date(r["created_at"])}}
                for r in self.svc.reports.recent(self.user.user_id, 5)]
        self.table.set_rows(rows, keep_page=not first)
        self.rank.set_data([(r["title"], r["votes"]) for r in self.svc.reports.top_voted(5)])

    def on_data_changed(self):
        self.load()


class AdminDashboard(BaseScreen):
    def build(self):
        self.header("Dashboard", f"Welcome back, {self.user.first_name}! Here is the overview of the whole system.")
        row = tk.Frame(self.page, bg=C.BG)
        row.pack(fill="x")
        specs = [("Total Feedback", "\u2709", C.BLUE, "#E3EEFF"), ("Total Suggestions", "\u2726", C.PURPLE, C.PURPLE_SOFT),
                 ("Pending Items", "!", C.ORANGE, C.ORANGE_SOFT),
                 ("Active Students", "\u263B", C.GREEN, C.GREEN_SOFT)]
        self.stats = []
        for i, (label, glyph, color, soft) in enumerate(specs):
            row.grid_columnconfigure(i, weight=1, uniform="stat")
            card = StatCard(row, label, glyph, color, soft, delay=i * 130)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0 if i == 3 else 8))
            self.stats.append(card)
        mid = tk.Frame(self.page, bg=C.BG)
        mid.pack(fill="x", pady=(18, 0))
        mid.grid_columnconfigure(0, weight=1, uniform="m")
        mid.grid_columnconfigure(1, weight=1, uniform="m")
        c1 = Card(mid, accent=C.PURPLE)
        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        card_title(c1.body, "Feedback by Category")
        self.donut = AnimatedDonutChart(c1.body, height=230)
        self.donut.pack(fill="x")
        c2 = Card(mid, accent=C.GREEN)
        c2.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        card_title(c2.body, "Feedback Status")
        self.bars = AnimatedBarChart(c2.body, height=230)
        self.bars.pack(fill="x")
        bot = tk.Frame(self.page, bg=C.BG)
        bot.pack(fill="x", pady=(18, 0))
        bot.grid_columnconfigure(0, weight=3, uniform="b")
        bot.grid_columnconfigure(1, weight=2, uniform="b")
        c3 = Card(bot, accent=C.BLUE)
        c3.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        card_title(c3.body, "Submissions \u2013 Last 7 Days")
        self.line = AnimatedLineChart(c3.body, height=250, color=C.BLUE)
        self.line.pack(fill="x")
        c4 = Card(bot, accent=C.PINK)
        c4.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        card_title(c4.body, "Top Voted Suggestions", "Manage", lambda: self.app.navigate("manage_suggestions"))
        self.rank = AnimatedRankList(c4.body)
        self.rank.pack(fill="x")
        self.load()

    def load(self):
        r = self.svc.reports
        s = r.admin_stats()
        for card, value in zip(self.stats, (s["feedback"], s["suggestions"], s["pending"], s["students"])):
            card.set_value(value)
        cats = r.by_category("feedback")
        self.donut.set_data([c for c, _ in cats], [n for _, n in cats], [CATEGORY_COLORS[c] for c, _ in cats])
        st = r.by_status("feedback")
        self.bars.set_data([a for a, _ in st], [n for _, n in st], [STATUS_COLORS[a] for a, _ in st])
        days = r.last_days(7)
        self.line.set_data([d for d, _ in days], [n for _, n in days])
        self.rank.set_data([(t["title"], t["votes"]) for t in r.top_voted(5)])

    def on_data_changed(self):
        self.load()


# ======================================================================
#  SUBMIT FEEDBACK / SUGGESTION (student)
# ======================================================================
class SubmitScreen(BaseScreen):
    kind = "feedback"

    def build(self):
        noun = self.kind.capitalize()
        sub = ("Tell the school about a problem or complaint." if self.kind == "feedback"
               else "Share an idea that can make the school better.")
        self.header(f"Submit {noun}", sub)
        accent = C.BLUE if self.kind == "feedback" else C.PURPLE
        card = Card(self.page, accent=accent, pad=28)
        card.pack(fill="x")
        b = card.body
        form_label(b, "Title", True).pack(anchor="w")
        self.title_entry = StyledEntry(b, placeholder=f"Enter {noun.lower()} title", width=60)
        self.title_entry.pack(fill="x", pady=(6, 16), ipady=4)
        form_label(b, "Category", True).pack(anchor="w")
        self.category = make_combo(b, CATEGORIES, width=40, value="Select category")
        self.category.pack(fill="x", pady=(6, 16), ipady=3)
        form_label(b, "Description", True).pack(anchor="w")
        placeholder = ("Write your feedback or complaint here..." if self.kind == "feedback"
                       else "Write your suggestion here...")
        self.desc = StyledText(b, height=8, limit=500, placeholder=placeholder)
        self.desc.pack(fill="x", pady=(6, 4))
        self.error = tk.Label(b, text="", bg=C.WHITE, fg=C.RED, font=font(10), wraplength=700, justify="left")
        self.error.pack(anchor="w", pady=(4, 0))
        row = tk.Frame(b, bg=C.WHITE)
        row.pack(fill="x", pady=(12, 0))
        self.submit_btn = HoverButton(row, "Submit", self.submit, "primary", width=130)
        self.submit_btn.pack(side="right")
        HoverButton(row, "Cancel", lambda: self.app.navigate("dashboard"), "gray", width=110).pack(side="right", padx=10)

    def submit(self):
        try:
            self.svc.submissions.create(self.kind, self.user.user_id, self.title_entry.value(),
                                        self.category.get(), self.desc.value())
        except AppError as e:
            flash_error(self.error, str(e))
            return
        self.submit_btn.flash(C.GREEN, "\u2713 Sent!")
        self.app.toast.show(f"Your {self.kind} was submitted. Thank you!", "success")
        self.after(750, lambda: self.app.navigate("my_submissions"))


class SubmitFeedbackScreen(SubmitScreen):
    kind = "feedback"


class SubmitSuggestionScreen(SubmitScreen):
    kind = "suggestion"


# ======================================================================
#  MY SUBMISSIONS (student CRUD)
# ======================================================================
class MySubmissionsScreen(BaseScreen):
    def build(self):
        self.filter, self._job = "All", None
        self.header("My Submissions", "See everything you sent. You can edit or delete items that are still Pending.")
        bar = tk.Frame(self.page, bg=C.BG)
        bar.pack(fill="x", pady=(0, 14))
        self.chips = {}
        for name in ("All", "Feedback", "Suggestions"):
            chip = HoverButton(bar, name, lambda n=name: self.set_filter(n), "primary" if name == "All" else "gray",
                               height=34, radius=17)
            chip.pack(side="left", padx=(0, 8))
            self.chips[name] = chip
        self.search = StyledEntry(bar, placeholder="Search my submissions...", width=30)
        self.search.pack(side="right", ipady=3)
        self.search.bind("<KeyRelease>", lambda e: self._debounce())
        card = Card(self.page, accent=C.BLUE, pad=14)
        card.pack(fill="x")
        self.table = DataTable(card.body, [
            Column("Type", "type", 110, "badge"), Column("Title", "title", 190, "title"),
            Column("Category", "category", 130, "category"), Column("Status", "status", 130, "badge"),
            Column("Votes", "votes", 70, "votes"), Column("Date", "date", 105),
            Column("Actions", None, 200, "actions")], page_size=6, row_height=48,
            empty_text="Nothing here yet. Use Submit Feedback or Submit Suggestion to start!")
        self.table.pack(fill="x")
        self.load()

    def _debounce(self):
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(250, self.load)

    def set_filter(self, name):
        self.filter = name
        for n, chip in self.chips.items():
            chip.set_style("primary" if n == name else "gray")
        self.load()

    def load(self, keep_page=False):
        q, uid = self.search.value(), self.user.user_id
        items = []
        if self.filter in ("All", "Feedback"):
            items += self.svc.submissions.list("feedback", user_id=uid, search=q)
        if self.filter in ("All", "Suggestions"):
            items += self.svc.submissions.list("suggestion", user_id=uid, search=q)
        items.sort(key=lambda i: i.created_at, reverse=True)
        rows = []
        for item in items:
            actions = [("View", "soft", lambda i=item: open_details(self.app, i))]
            if item.can_be_changed_by_student:
                actions += [("Edit", "soft_orange", lambda i=item: self.edit(i)),
                            ("Delete", "soft_red", lambda i=item: self.delete(i))]
            rows.append(submission_row(item, actions))
        self.table.set_rows(rows, keep_page=keep_page)

    def on_data_changed(self):
        self.load(keep_page=True)

    def delete(self, item):
        def go():
            try:
                self.svc.submissions.delete(item.kind, item.id, self.user.user_id)
            except AppError as e:
                self.app.toast.show(str(e), "error")
            else:
                self.app.toast.show("Deleted successfully.", "success")
            self.load(keep_page=True)
        confirm(self.app, "Delete this item?", f"\"{item.title}\" will be removed. This cannot be undone.", go)

    def edit(self, item):
        m = Modal(self.app, f"Edit {item.kind.capitalize()}", width=560, accent=C.ORANGE)
        form_label(m.body, "Title", True).pack(anchor="w", pady=(0, 4))
        title = StyledEntry(m.body, width=50)
        title.set_value(item.title)
        title.pack(fill="x", ipady=3)
        form_label(m.body, "Category", True).pack(anchor="w", pady=(12, 4))
        cat = make_combo(m.body, CATEGORIES, width=30, value=item.category)
        cat.pack(fill="x", ipady=2)
        form_label(m.body, "Description", True).pack(anchor="w", pady=(12, 4))
        desc = StyledText(m.body, height=6, limit=500)
        desc.set_value(item.description)
        desc.pack(fill="x")
        err = tk.Label(m.body, text="", bg=C.WHITE, fg=C.RED, font=font(9), wraplength=500, justify="left")
        err.pack(anchor="w")

        def save():
            try:
                self.svc.submissions.update(item.kind, item.id, self.user.user_id, title.value(), cat.get(), desc.value())
            except AppError as e:
                flash_error(err, str(e))
                return
            m.close()
            self.app.toast.show("Changes saved.", "success")
            self.load(keep_page=True)

        HoverButton(m.footer, "Save Changes", save, "primary").pack(side="right")
        HoverButton(m.footer, "Cancel", m.close, "gray").pack(side="right", padx=8)
        m.show()


# ======================================================================
#  SUGGESTION BOARD (students vote here)
# ======================================================================
class SuggestionBoardScreen(BaseScreen):
    PER_PAGE = 6

    def build(self):
        self.page_no, self._job, self.items = 0, None, []
        self.header("Suggestion Board", "Vote for the ideas you support. The most popular ideas stand out!")
        bar = tk.Frame(self.page, bg=C.BG)
        bar.pack(fill="x", pady=(0, 12))
        self.sort = make_combo(bar, ["Most Voted", "Newest"], width=14, value="Most Voted")
        self.sort.pack(side="left", padx=(0, 10), ipady=2)
        self.category = make_combo(bar, ["All"] + CATEGORIES, width=14, value="All")
        self.category.pack(side="left", ipady=2)
        for combo in (self.sort, self.category):
            combo.bind("<<ComboboxSelected>>", lambda e: self.reload(reset=True), add="+")
        self.search = StyledEntry(bar, placeholder="Search suggestions...", width=30)
        self.search.pack(side="right", ipady=3)
        self.search.bind("<KeyRelease>", lambda e: self._debounce())
        self.cards = tk.Frame(self.page, bg=C.BG)
        self.cards.pack(fill="x")
        for c in range(2):
            self.cards.grid_columnconfigure(c, weight=1, uniform="b")
        self.pager = Pager(self.page, self._go, bg=C.BG)
        self.pager.pack(fill="x", pady=(10, 0))
        self.reload(reset=True)

    def _debounce(self):
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(250, lambda: self.reload(reset=True))

    def _go(self, page):
        self.page_no = page
        self.render()

    def reload(self, reset=False):
        if reset:
            self.page_no = 0
        self.items = self.svc.submissions.list(
            "suggestion", category=self.category.get(), search=self.search.value(),
            viewer_id=self.user.user_id, order="votes" if self.sort.get() == "Most Voted" else "newest")
        self.render()

    def on_data_changed(self):
        self.reload()

    def render(self):
        for child in self.cards.winfo_children():
            child.destroy()
        self.pager.update_state(self.page_no, self.PER_PAGE, len(self.items))
        self.page_no = self.pager.page
        chunk = self.items[self.page_no * self.PER_PAGE:(self.page_no + 1) * self.PER_PAGE]
        if not chunk:
            tk.Label(self.cards, text="No suggestions found.", bg=C.BG, fg=C.MUTED, font=font(11)).grid(pady=50, columnspan=2)
            return
        for i, item in enumerate(chunk):
            card = self._card(item)
            card.grid(row=i // 2, column=i % 2, sticky="nsew", padx=6, pady=6)

    def _card(self, s):
        color = CATEGORY_COLORS.get(s.category, C.BLUE)
        card = Card(self.cards, accent=color, pad=16)
        b = card.body
        top = tk.Frame(b, bg=C.WHITE)
        top.pack(fill="x")
        category_badge(top, s.category).pack(side="left")
        Badge(top, s.status).pack(side="left", padx=(8, 0))
        tk.Label(b, text=s.title, bg=C.WHITE, fg=C.TEXT, font=font(12, "bold"), wraplength=340,
                 justify="left", anchor="w").pack(anchor="w", pady=(12, 4))
        text = s.description if len(s.description) <= 110 else s.description[:107].rstrip() + "..."
        tk.Label(b, text=text, bg=C.WHITE, fg=C.MUTED, font=font(10), wraplength=340, justify="left",
                 anchor="w").pack(anchor="w", fill="x")
        foot = tk.Frame(b, bg=C.WHITE)
        foot.pack(fill="x", pady=(14, 0), side="bottom")
        tk.Label(foot, text=f"{s.author}  \u2022  {s.date}", bg=C.WHITE, fg=C.MUTED, font=font(9)).pack(side="left")
        if s.user_id == self.user.user_id:
            tk.Label(foot, text=f"\u25B2 {s.votes}  (yours)", bg=C.WHITE, fg=C.PURPLE, font=font(10, "bold")).pack(side="right")
        else:
            voted = s.voted_by_me
            btn = HoverButton(foot, f"\u25B2  {'Voted' if voted else 'Vote'}  {s.votes}", lambda i=s: self.vote(i),
                              "primary" if voted else "soft", height=32, radius=16, size=9)
            btn.pack(side="right")
            if s.status == "Rejected" and not voted:
                btn.set_enabled(False)
        return card

    def vote(self, s):
        try:
            now_voted = self.svc.votes.toggle(self.user.user_id, s.id)
        except AppError as e:
            self.app.toast.show(str(e), "error")
            return
        self.app.toast.show("Vote added \u25B2" if now_voted else "Vote removed", "success" if now_voted else "info", 1500)
        self.reload()


# ======================================================================
#  PROFILE
# ======================================================================
class ProfileScreen(BaseScreen):
    def build(self):
        self.header("Profile", "Your account details and password.")
        row = tk.Frame(self.page, bg=C.BG)
        row.pack(fill="x")
        row.grid_columnconfigure(0, weight=1, uniform="p")
        row.grid_columnconfigure(1, weight=1, uniform="p")
        # --- account card
        c1 = Card(row, accent=C.BLUE, pad=24)
        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        av = tk.Canvas(c1.body, width=84, height=84, bg=C.WHITE, highlightthickness=0)
        av.create_oval(2, 2, 82, 82, fill=C.BLUE, outline="#BCD3FA", width=4)
        av.create_text(42, 42, text=self.user.initial, fill="white", font=font(30, "bold"))
        av.pack(anchor="w")
        Badge(c1.body, self.user.role.capitalize()).pack(anchor="w", pady=(12, 4))
        tk.Label(c1.body, text=f"@{self.user.username}   \u2022   Member since {fmt_date(self.user.created_at)}",
                 bg=C.WHITE, fg=C.MUTED, font=font(9)).pack(anchor="w", pady=(0, 14))
        form_label(c1.body, "Full Name").pack(anchor="w", pady=(0, 4))
        self.name = StyledEntry(c1.body, width=34)
        self.name.set_value(self.user.full_name)
        self.name.pack(fill="x", ipady=3)
        self.name_msg = tk.Label(c1.body, text="", bg=C.WHITE, fg=C.RED, font=font(9))
        self.name_msg.pack(anchor="w", pady=(6, 0))
        HoverButton(c1.body, "Save Name", self.save_name, "primary", width=130).pack(anchor="e", pady=(6, 0))
        # --- password card
        c2 = Card(row, accent=C.PURPLE, pad=24)
        c2.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        tk.Label(c2.body, text="Change Password", bg=C.WHITE, fg=C.TEXT, font=font(12, "bold")).pack(anchor="w", pady=(0, 10))
        self.pw = {}
        for key, label in (("old", "Current Password"), ("new", "New Password"), ("conf", "Confirm New Password")):
            form_label(c2.body, label).pack(anchor="w", pady=(8, 4))
            self.pw[key] = StyledEntry(c2.body, password=True, width=34)
            self.pw[key].pack(fill="x", ipady=3)
        self.pw_msg = tk.Label(c2.body, text="", bg=C.WHITE, fg=C.RED, font=font(9), wraplength=360, justify="left")
        self.pw_msg.pack(anchor="w", pady=(8, 0))
        HoverButton(c2.body, "Update Password", self.save_password, "primary", width=160).pack(anchor="e", pady=(6, 0))

    def save_name(self):
        try:
            self.svc.users.update_name(self.user.user_id, self.name.value())
        except AppError as e:
            flash_error(self.name_msg, str(e))
            return
        self.user.rename(self.name.value())
        self.app.toast.show("Your name was updated.", "success")
        self.app.refresh_sidebar()

    def save_password(self):
        try:
            self.svc.users.change_password(self.user.user_id, self.pw["old"].value(False),
                                           self.pw["new"].value(False), self.pw["conf"].value(False))
        except AppError as e:
            flash_error(self.pw_msg, str(e))
            return
        for e in self.pw.values():
            e.clear()
        self.pw_msg.configure(text="")
        self.app.toast.show("Password changed successfully.", "success")


# ======================================================================
#  ADMIN: MANAGE FEEDBACK / SUGGESTIONS
# ======================================================================
class ManageScreen(BaseScreen):
    kind = "feedback"
    statuses = FEEDBACK_STATUSES
    title_text = "Manage Feedback"
    subtitle = ""

    def columns(self):
        raise NotImplementedError

    def actions_for(self, item):
        raise NotImplementedError

    def build(self):
        self._job = None
        self.header(self.title_text, self.subtitle)
        bar = tk.Frame(self.page, bg=C.BG)
        bar.pack(fill="x", pady=(0, 12))
        left = tk.Frame(bar, bg=C.BG)
        left.pack(side="left")
        tk.Label(left, text="Category", bg=C.BG, fg=C.MUTED, font=font(9, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(left, text="Status", bg=C.BG, fg=C.MUTED, font=font(9, "bold")).grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.category = make_combo(left, ["All"] + CATEGORIES, width=16, value="All")
        self.category.grid(row=1, column=0, ipady=2)
        self.status = make_combo(left, ["All"] + self.statuses, width=16, value="All")
        self.status.grid(row=1, column=1, padx=(10, 0), ipady=2)
        for combo in (self.category, self.status):
            combo.bind("<<ComboboxSelected>>", lambda e: self.load(), add="+")
        self.search = StyledEntry(bar, placeholder=f"Search {self.kind}...", width=30)
        self.search.pack(side="right", ipady=3, anchor="s")
        HoverButton(bar, "Reset", self.reset, "gray", height=34, width=80).pack(side="right", padx=(0, 10), anchor="s")
        self.search.bind("<KeyRelease>", lambda e: self._debounce())
        card = Card(self.page, accent=C.BLUE, pad=14)
        card.pack(fill="x")
        self.table = DataTable(card.body, self.columns(), page_size=7, row_height=48,
                               empty_text="No records match your filters.")
        self.table.pack(fill="x")
        self.load()

    def _debounce(self):
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(250, self.load)

    def reset(self):
        self.category.set("All")
        self.status.set("All")
        self.search.clear()
        self.load()

    def load(self, keep_page=False):
        items = self.svc.submissions.list(self.kind, category=self.category.get(), status=self.status.get(),
                                          search=self.search.value())
        self.table.set_rows([submission_row(i, self.actions_for(i)) for i in items], keep_page=keep_page)

    def on_data_changed(self):
        self.load(keep_page=True)


class ManageFeedbackScreen(ManageScreen):
    kind, statuses = "feedback", FEEDBACK_STATUSES
    title_text = "Manage Feedback"
    subtitle = "Read what students sent and respond to them."

    def columns(self):
        return [Column("ID", "id", 70, "id"), Column("Title", "title", 270, "title"),
                Column("Category", "category", 130, "category"), Column("Status", "status", 130, "badge"),
                Column("Date", "date", 110), Column("Actions", None, 190, "actions")]

    def actions_for(self, item):
        return [("View", "soft", lambda i=item: self.app.navigate("respond", feedback_id=i.id, readonly=True)),
                ("Respond", "soft", lambda i=item: self.app.navigate("respond", feedback_id=i.id))]


class ManageSuggestionsScreen(ManageScreen):
    kind, statuses = "suggestion", SUGGESTION_STATUSES
    title_text = "Manage Suggestions"
    subtitle = "Review the ideas of students and decide what happens to them."

    def columns(self):
        return [Column("ID", "id", 70, "id"), Column("Title", "title", 280, "title"),
                Column("Category", "category", 130, "category"), Column("Status", "status", 130, "badge"),
                Column("Votes", "votes", 90, "votes"), Column("Actions", None, 190, "actions")]

    def actions_for(self, item):
        return [("View", "soft", lambda i=item: open_details(self.app, i)),
                ("Update", "soft_orange", lambda i=item: self.update_status(i))]

    def update_status(self, item):
        m = Modal(self.app, "Update Suggestion Status", width=480, accent=C.ORANGE)
        tk.Label(m.body, text=item.title, bg=C.WHITE, fg=C.TEXT, font=font(11, "bold"), wraplength=420,
                 justify="left").pack(anchor="w")
        tk.Label(m.body, text=f"\u25B2 {item.votes} votes", bg=C.WHITE, fg=C.PURPLE, font=font(10, "bold")).pack(anchor="w", pady=(4, 12))
        form_label(m.body, "New Status", True).pack(anchor="w", pady=(0, 4))
        combo = make_combo(m.body, SUGGESTION_STATUSES, width=30, value=item.status)
        combo.pack(fill="x", ipady=3)

        def save():
            try:
                self.svc.submissions.set_status("suggestion", item.id, combo.get())
            except AppError as e:
                self.app.toast.show(str(e), "error")
                return
            m.close()
            self.app.toast.show(f"Status changed to {combo.get()}.", "success")
            self.load(keep_page=True)

        HoverButton(m.footer, "Save", save, "primary").pack(side="right")
        HoverButton(m.footer, "Cancel", m.close, "gray").pack(side="right", padx=8)
        m.show()


class RespondScreen(BaseScreen):
    def build(self, feedback_id=0, readonly=False):
        item = self.svc.submissions.get("feedback", feedback_id)
        back = LinkLabel(self.page, "\u2190  Back to Manage Feedback", lambda: self.app.navigate("manage_feedback"), size=10)
        back.pack(anchor="w", pady=(0, 8))
        if item is None:
            self.header("Feedback not found", "This feedback was deleted by the student.")
            return
        self.item = item
        self.header("Feedback Details" if readonly else "Respond to Feedback",
                    "Read the feedback, then write your response and update the status.")
        row = tk.Frame(self.page, bg=C.BG)
        row.pack(fill="both", expand=True)
        row.grid_columnconfigure(0, weight=1, uniform="r")
        row.grid_columnconfigure(1, weight=1, uniform="r")
        # --- details
        left = Card(row, accent=C.BLUE, pad=22)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        tk.Label(left.body, text="Feedback Details", bg=C.WHITE, fg=C.TEXT, font=font(12, "bold")).pack(anchor="w", pady=(0, 12))
        info = tk.Frame(left.body, bg=C.WHITE)
        info.pack(fill="x")
        info.grid_columnconfigure(1, weight=1)
        facts = [("ID", item.code), ("Title", item.title), ("Category", category_badge),
                 ("Status", Badge), ("Date Submitted", fmt_datetime(item.created_at)),
                 ("Submitted By", f"{item.author} (Student)")]
        for r, (label, value) in enumerate(facts):
            tk.Label(info, text=label, bg=C.WHITE, fg=C.MUTED, font=font(10), anchor="w").grid(row=r, column=0, sticky="nw", pady=6, padx=(0, 18))
            if value is category_badge:
                category_badge(info, item.category).grid(row=r, column=1, sticky="w")
            elif value is Badge:
                Badge(info, item.status).grid(row=r, column=1, sticky="w")
            else:
                tk.Label(info, text=value, bg=C.WHITE, fg=C.TEXT, font=font(10, "bold"), wraplength=260,
                         justify="left", anchor="w").grid(row=r, column=1, sticky="w")
        tk.Label(left.body, text="Description", bg=C.WHITE, fg=C.TEXT, font=font(10, "bold")).pack(anchor="w", pady=(14, 6))
        box = tk.Frame(left.body, bg="#F6F8FC")
        box.pack(fill="x")
        tk.Label(box, text=item.description, bg="#F6F8FC", fg=C.TEXT, font=font(10), wraplength=360,
                 justify="left").pack(anchor="w", padx=14, pady=12)
        # --- response
        right = Card(row, accent=C.GREEN, pad=22)
        right.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        if not readonly:
            tk.Label(right.body, text="Admin Response", bg=C.WHITE, fg=C.TEXT, font=font(12, "bold")).pack(anchor="w", pady=(0, 8))
            self.response = StyledText(right.body, height=6, limit=500, placeholder="Write your response here...")
            self.response.pack(fill="x")
            form_label(right.body, "Update Status").pack(anchor="w", pady=(10, 4))
            self.status = make_combo(right.body, FEEDBACK_STATUSES, width=28, value=item.status)
            self.status.pack(fill="x", ipady=3)
            self.error = tk.Label(right.body, text="", bg=C.WHITE, fg=C.RED, font=font(9), wraplength=380, justify="left")
            self.error.pack(anchor="w", pady=(6, 0))
            btns = tk.Frame(right.body, bg=C.WHITE)
            btns.pack(fill="x", pady=(8, 14))
            self.send_btn = HoverButton(btns, "Send Response", self.send, "success", width=150)
            self.send_btn.pack(side="right")
            HoverButton(btns, "Cancel", lambda: self.app.navigate("manage_feedback"), "gray", width=100).pack(side="right", padx=10)
        tk.Label(right.body, text="Previous Responses", bg=C.WHITE, fg=C.TEXT, font=font(12, "bold")).pack(anchor="w", pady=(4, 8))
        responses = self.svc.responses.for_feedback(item.id)
        if not responses:
            tk.Label(right.body, text="No response yet.", bg=C.WHITE, fg=C.MUTED, font=font(10)).pack(anchor="w")
        for r in responses[:4]:
            c = tk.Frame(right.body, bg=C.BLUE_SOFT)
            c.pack(fill="x", pady=3)
            tk.Label(c, text=f"{r['admin_name']}  \u2022  {fmt_datetime(r['created_at'])}", bg=C.BLUE_SOFT, fg=C.BLUE,
                     font=font(9, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
            tk.Label(c, text=r["response_text"], bg=C.BLUE_SOFT, fg=C.TEXT, font=font(10), wraplength=370,
                     justify="left").pack(anchor="w", padx=12, pady=(2, 8))

    def send(self):
        try:
            self.svc.responses.add(self.item.id, self.user.user_id, self.response.value(), self.status.get())
        except AppError as e:
            flash_error(self.error, str(e))
            return
        self.send_btn.flash(C.GREEN, "\u2713 Sent!")
        self.app.toast.show("Your response was sent to the student.", "success")
        self.after(750, lambda: self.app.navigate("manage_feedback"))


# ======================================================================
#  ADMIN: MANAGE USERS
# ======================================================================
class ManageUsersScreen(BaseScreen):
    def build(self):
        self._job = None
        self.header("Manage Users", "Add, edit or deactivate student and admin accounts.")
        bar = tk.Frame(self.page, bg=C.BG)
        bar.pack(fill="x", pady=(0, 12))
        HoverButton(bar, "+  Add User", self.add_user, "primary", height=38).pack(side="right")
        self.search = StyledEntry(bar, placeholder="Search users...", width=32)
        self.search.pack(side="left", ipady=3)
        self.search.bind("<KeyRelease>", lambda e: self._debounce())
        card = Card(self.page, accent=C.GREEN, pad=14)
        card.pack(fill="x")
        self.table = DataTable(card.body, [
            Column("ID", "id", 60, "id"), Column("Full Name", "name", 220, "title"), Column("Username", "username", 150),
            Column("Role", "role", 110, "badge"), Column("Status", "status", 110, "badge"),
            Column("Actions", None, 220, "actions")], page_size=7, row_height=48,
            empty_text="No users found.")
        self.table.pack(fill="x")
        self.load()

    def _debounce(self):
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(250, self.load)

    def load(self, keep_page=False):
        rows = []
        for u in self.svc.users.list(self.search.value()):
            actions = [("Edit", "soft", lambda x=u: self.edit_user(x))]
            if u.user_id != self.user.user_id:
                if u.is_active:
                    actions.append(("Deactivate", "soft_red", lambda x=u: self.toggle(x)))
                else:
                    actions.append(("Activate", "soft_green", lambda x=u: self.toggle(x)))
            rows.append({"cells": {"id": f"#{u.user_id:03d}", "name": u.full_name, "username": u.username,
                                   "role": u.role.capitalize(), "status": "Active" if u.is_active else "Inactive"},
                         "actions": actions})
        self.table.set_rows(rows, keep_page=keep_page)

    def on_data_changed(self):
        self.load(keep_page=True)

    def toggle(self, u):
        def go():
            self.svc.users.set_active(u.user_id, not u.is_active)
            self.app.toast.show(f"{u.full_name} is now {'inactive' if u.is_active else 'active'}.", "info")
            self.load(keep_page=True)
        if u.is_active:
            confirm(self.app, "Deactivate this account?", f"{u.full_name} will not be able to log in until you activate the account again.",
                    go, "Yes, deactivate")
        else:
            go()

    def add_user(self):
        self._dialog(None)

    def edit_user(self, u):
        self._dialog(u)

    def _dialog(self, u):
        editing = u is not None
        m = Modal(self.app, "Edit User" if editing else "Add New User", width=480, accent=C.GREEN)
        fields = {}
        for key, label, pw in (("name", "Full Name", False), ("user", "Username", False), ("pass", "Password", True)):
            form_label(m.body, label, not (editing and key == "pass")).pack(anchor="w", pady=(8, 4))
            fields[key] = StyledEntry(m.body, password=pw, width=40,
                                      placeholder="Leave empty to keep the current password" if (pw and editing) else "")
            fields[key].pack(fill="x", ipady=3)
        form_label(m.body, "Role", True).pack(anchor="w", pady=(10, 4))
        role = make_combo(m.body, ["Student", "Admin"], width=20, value="Student")
        role.pack(fill="x", ipady=2)
        if editing:
            fields["name"].set_value(u.full_name)
            fields["user"].set_value(u.username)
            role.set(u.role.capitalize())
            if u.user_id == self.user.user_id:
                role.configure(state="disabled")
        err = tk.Label(m.body, text="", bg=C.WHITE, fg=C.RED, font=font(9), wraplength=420, justify="left")
        err.pack(anchor="w", pady=(10, 0))

        def save():
            try:
                if editing:
                    self.svc.users.update(u.user_id, fields["name"].value(), fields["user"].value(),
                                          role.get().lower(), fields["pass"].value(False) or None)
                else:
                    self.svc.users.create(fields["name"].value(), fields["user"].value(),
                                          fields["pass"].value(False), role.get().lower())
            except AppError as e:
                flash_error(err, str(e))
                return
            m.close()
            self.app.toast.show("User saved.", "success")
            self.load(keep_page=True)

        HoverButton(m.footer, "Save User", save, "primary").pack(side="right")
        HoverButton(m.footer, "Cancel", m.close, "gray").pack(side="right", padx=8)
        m.show()


# ======================================================================
#  ADMIN: REPORTS
# ======================================================================
class ReportsScreen(BaseScreen):
    TABS = [("feedback", "Feedback Report"), ("suggestion", "Suggestion Report"), ("top", "Top Voted Suggestions")]

    def build(self):
        self.tab = "feedback"
        self.header("Reports", "See the trends in feedback and suggestions. Export them as CSV or PDF.")
        tabs = tk.Frame(self.page, bg=C.BG)
        tabs.pack(fill="x", pady=(0, 12))
        self.tab_buttons = {}
        for key, label in self.TABS:
            b = HoverButton(tabs, label, lambda k=key: self.set_tab(k), "primary" if key == self.tab else "gray",
                            height=36, radius=18)
            b.pack(side="left", padx=(0, 8))
            self.tab_buttons[key] = b
        rng = Card(self.page, accent=C.BLUE, pad=14)
        rng.pack(fill="x", pady=(0, 14))
        r = tk.Frame(rng.body, bg=C.WHITE)
        r.pack(fill="x")
        tk.Label(r, text="Date Range", bg=C.WHITE, fg=C.TEXT, font=font(10, "bold")).pack(side="left", padx=(0, 12))
        today = date.today()
        self.start = StyledEntry(r, width=12)
        self.start.set_value((today - timedelta(days=30)).isoformat())
        self.start.pack(side="left", ipady=3)
        tk.Label(r, text="to", bg=C.WHITE, fg=C.MUTED, font=font(10)).pack(side="left", padx=8)
        self.end = StyledEntry(r, width=12)
        self.end.set_value(today.isoformat())
        self.end.pack(side="left", ipady=3)
        tk.Label(r, text="(YYYY-MM-DD)", bg=C.WHITE, fg=C.MUTED, font=font(8)).pack(side="left", padx=8)
        HoverButton(r, "Export PDF", lambda: self.export("pdf"), "outline", height=36).pack(side="right")
        HoverButton(r, "Export CSV", lambda: self.export("csv"), "outline", height=36).pack(side="right", padx=8)
        HoverButton(r, "Generate Report", self.generate, "primary", height=36).pack(side="right", padx=(0, 8))
        self.content = tk.Frame(self.page, bg=C.BG)
        self.content.pack(fill="both", expand=True)
        self.render()

    def set_tab(self, key):
        self.tab = key
        for k, b in self.tab_buttons.items():
            b.set_style("primary" if k == key else "gray")
        self.render()

    def _range(self):
        try:
            s = datetime.strptime(self.start.value(), "%Y-%m-%d").date()
            e = datetime.strptime(self.end.value(), "%Y-%m-%d").date()
        except ValueError:
            raise AppError("Please write the dates like this: 2026-10-31")
        if s > e:
            raise AppError("The start date must be before the end date.")
        return s.isoformat(), e.isoformat()

    def generate(self):
        if self.render():
            self.app.toast.show("Report generated.", "success", 1800)

    def render(self):
        try:
            s, e = self._range()
        except AppError as err:
            self.app.toast.show(str(err), "error")
            return False
        for child in self.content.winfo_children():
            child.destroy()
        rep = self.svc.reports
        grid = tk.Frame(self.content, bg=C.BG)
        grid.pack(fill="x")
        grid.grid_columnconfigure(0, weight=1, uniform="g")
        grid.grid_columnconfigure(1, weight=1, uniform="g")
        if self.tab in ("feedback", "suggestion"):
            noun = "Feedback" if self.tab == "feedback" else "Suggestions"
            c1 = Card(grid, accent=C.PURPLE)
            c1.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
            card_title(c1.body, f"{noun} by Category")
            donut = AnimatedDonutChart(c1.body, height=250)
            donut.pack(fill="x")
            cats = rep.by_category(self.tab, s, e)
            donut.set_data([c for c, _ in cats], [n for _, n in cats], [CATEGORY_COLORS[c] for c, _ in cats])
            c2 = Card(grid, accent=C.GREEN)
            c2.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
            card_title(c2.body, f"{noun} Status")
            bars = AnimatedBarChart(c2.body, height=250)
            bars.pack(fill="x")
            st = rep.by_status(self.tab, s, e)
            bars.set_data([a for a, _ in st], [n for _, n in st], [STATUS_COLORS[a] for a, _ in st])
        else:
            c1 = Card(grid, accent=C.PINK)
            c1.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
            card_title(c1.body, "Most Voted Suggestions")
            ranks = AnimatedRankList(c1.body, empty_text="No votes in this date range.")
            ranks.pack(fill="x")
            ranks.set_data([(t["title"], t["votes"]) for t in rep.top_voted(8, s, e)])
            c2 = Card(grid, accent=C.PURPLE)
            c2.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
            card_title(c2.body, "Votes by Category")
            donut = AnimatedDonutChart(c2.body, height=250)
            donut.pack(fill="x")
            cats = rep.votes_by_category(s, e)
            donut.set_data([c for c, _ in cats], [n for _, n in cats], [CATEGORY_COLORS[c] for c, _ in cats])
        return True

    def export(self, fmt):
        try:
            s, e = self._range()
        except AppError as err:
            self.app.toast.show(str(err), "error")
            return
        report = self.svc.reports.build_report(self.tab, s, e)
        name = report.title.lower().replace(" ", "_") + f"_{s}_to_{e}"
        path = filedialog.asksaveasfilename(parent=self.app, defaultextension=f".{fmt}", initialfile=f"{name}.{fmt}",
                                            filetypes=[(fmt.upper() + " file", f"*.{fmt}")])
        if not path:
            return
        try:
            if fmt == "csv":
                self.svc.reports.export_csv(report, path)
            else:
                self.svc.reports.export_pdf(report, path)
        except AppError as err:
            self.app.toast.show(str(err), "error")
        except OSError as err:
            self.app.toast.show(f"Could not save the file: {err.strerror}", "error")
        else:
            self.app.toast.show(f"{fmt.upper()} saved successfully.", "success")
