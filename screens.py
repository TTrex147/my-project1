"""
screens.py
Every screen (window page) of the app. Each screen is a class that inherits from BaseScreen.

Student screens : StudentDashboard, SubmitFeedbackScreen, SubmitSuggestionScreen,
                  MySubmissionsScreen, SuggestionBoardScreen, ProfileScreen
Admin screens   : AdminDashboard, ManageFeedbackScreen, RespondScreen,
                  ManageSuggestionsScreen, ManageUsersScreen, ReportsScreen, ProfileScreen
"""
import tkinter as tk
import tkinter.font as tkfont
from datetime import date, datetime, timedelta
from tkinter import filedialog

from PIL import ImageTk

from icons import icon
from managers import AppError
from theme import (C, CATEGORIES, CATEGORY_COLORS, FEEDBACK_STATUSES, FONT, STATUS_COLORS,
                   SUGGESTION_STATUSES, animate, bg_of, darken, ellipsize, fmt_date, fmt_datetime,
                   font, lerp_color, lighten, linear, rounded_rect)
from widgets import (AnimatedBarChart, AnimatedDonutChart, AnimatedGauge, AnimatedLineChart,
                     AnimatedRankList, Badge, Card, Column, DataTable, HoverArea, HoverButton,
                     KpiCard, LinkLabel, Modal, Pager, PillSearch, RoundIconButton, ScrollFrame,
                     StyledEntry, StyledText, card_fan_image, category_badge, confirm, form_label,
                     make_combo, set_bg_tree)


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
    accent = C.PRIMARY if item.kind == "feedback" else C.PURPLE
    m = Modal(app, f"{item.kind.capitalize()} {item.code}", width=600, accent=accent)
    tk.Label(m.body, text=item.title, bg=C.WHITE, fg=C.TEXT, font=font(13, "bold"),
             wraplength=540, justify="left").pack(anchor="w")
    badges = tk.Frame(m.body, bg=C.WHITE)
    badges.pack(anchor="w", pady=(10, 4))
    category_badge(badges, item.category).pack(side="left", padx=(0, 8))
    Badge(badges, item.status).pack(side="left")
    tk.Label(m.body, text=f"Submitted by {item.author} on {fmt_datetime(item.created_at)}",
             bg=C.WHITE, fg=C.MUTED, font=font(9)).pack(anchor="w", pady=(0, 10))
    box = tk.Frame(m.body, bg="#F5F3EE")
    box.pack(fill="x")
    tk.Label(box, text=item.description, bg="#F5F3EE", fg=C.TEXT, font=font(10), wraplength=520,
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
            card = tk.Frame(m.body, bg=C.PRIMARY_SOFT)
            card.pack(fill="x", pady=3)
            tk.Label(card, text=f"{r['admin_name']}  \u2022  {fmt_datetime(r['created_at'])}", bg=C.PRIMARY_SOFT,
                     fg=C.PRIMARY, font=font(9, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
            tk.Label(card, text=r["response_text"], bg=C.PRIMARY_SOFT, fg=C.TEXT, font=font(10),
                     wraplength=510, justify="left").pack(anchor="w", padx=12, pady=(2, 8))
    HoverButton(m.footer, "Close", m.close, "gray").pack(side="right")
    m.show()


# ======================================================================
#  Small building blocks used by the dashboards
# ======================================================================
GUTTER = 8            # half of the space between two cards


def card_row(parent):
    """A row with 4 equal columns. Put cards in it with put()."""
    row = tk.Frame(parent, bg=C.BG)
    row.pack(fill="x", pady=(0, 18))
    for i in range(4):
        row.grid_columnconfigure(i, weight=1, uniform="col")
    return row


def put(row, widget, col, span=1):
    widget.grid(row=0, column=col, columnspan=span, sticky="nsew",
                padx=(0 if col == 0 else GUTTER, 0 if col + span == 4 else GUTTER))


class StatTile(tk.Canvas):
    """Small rounded tile: label, number and a tiny colored tag."""

    def __init__(self, master, label, tag, tag_color, width=190, height=70):
        super().__init__(master, width=width, height=height, bg=bg_of(master), highlightthickness=0, bd=0)
        rounded_rect(self, 0, 0, width, height, 16, fill=C.PRIMARY_MIST, outline="")
        self.create_text(16, 21, text=label, anchor="w", fill=C.MUTED, font=font(9, "bold"))
        self._value = self.create_text(16, 48, text="0", anchor="w", fill=C.TEXT, font=font(18, "bold"))
        tw = tkfont.Font(family=FONT, size=8, weight="bold").measure(tag) + 18
        rounded_rect(self, width - 14 - tw, 38, width - 14, 58, 10, fill=lighten(tag_color, 0.8), outline="")
        self.create_text(width - 14 - tw / 2, 48, text=tag, fill=darken(tag_color, 0.25), font=font(8, "bold"))

    def set(self, value):
        self.itemconfigure(self._value, text=str(value))


def recent_list(parent, rows, title_px=150, empty="Nothing here yet."):
    """Compact list: colored bar, title, date and a status badge. rows = (title, sub, status)"""
    for child in parent.winfo_children():
        child.destroy()
    if not rows:
        tk.Label(parent, text=empty, bg=C.WHITE, fg=C.MUTED, font=font(10)).pack(pady=24)
        return
    fnt = tkfont.Font(family=FONT, size=10, weight="bold")
    bar_colors = {"Pending": "#E9A15B", "In Progress": "#6FA3D8", "Under Review": "#6FA3D8",
                  "Resolved": "#4E9B73", "Approved": "#4E9B73", "Rejected": "#D9645F"}
    for title, sub, status in rows:
        row = tk.Frame(parent, bg=C.WHITE)
        row.pack(fill="x", pady=5)
        tk.Frame(row, bg=bar_colors.get(status, C.PRIMARY), width=4, height=38).pack(side="left", padx=(0, 10))
        inner = tk.Frame(row, bg=C.WHITE)
        inner.pack(side="left", fill="x", expand=True)
        Badge(inner, status, height=22, size=8).pack(side="right")
        texts = tk.Frame(inner, bg=C.WHITE)
        texts.pack(side="left")
        tk.Label(texts, text=ellipsize(title, fnt, title_px), bg=C.WHITE, fg=C.TEXT, font=fnt,
                 anchor="w").pack(anchor="w")
        tk.Label(texts, text=ellipsize(sub, tkfont.Font(family=FONT, size=8), title_px), bg=C.WHITE,
                 fg=C.MUTED, font=font(8), anchor="w").pack(anchor="w")
        HoverArea(inner, lambda i=inner: set_bg_tree(i, C.ROW_HOVER), lambda i=inner: set_bg_tree(i, C.WHITE))


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
        self.page.pack(fill="both", expand=True, padx=(8, 30), pady=24)
        self.bell = None
        self.build(**params)

    def build(self, **params):
        raise NotImplementedError

    def on_data_changed(self):
        """Called when another user changed the database (live sync). Override if needed."""

    def header(self, title, subtitle=""):
        box = tk.Frame(self.page, bg=C.BG)
        box.pack(fill="x", pady=(0, 20))
        tk.Label(box, text=title, bg=C.BG, fg=C.TEXT, font=font(22, "bold")).pack(anchor="w")
        if subtitle:
            tk.Label(box, text=subtitle, bg=C.BG, fg=C.MUTED, font=font(10)).pack(anchor="w", pady=(2, 0))
        return box

    def greeting_header(self, title, subtitle):
        """Big hello on the left, search box and bell on the right (dashboard top)."""
        row = tk.Frame(self.page, bg=C.BG)
        row.pack(fill="x", pady=(0, 22))
        left = tk.Frame(row, bg=C.BG)
        left.pack(side="left")
        tk.Label(left, text=title, bg=C.BG, fg=C.TEXT, font=font(22, "bold")).pack(anchor="w")
        tk.Label(left, text=subtitle, bg=C.BG, fg=C.MUTED, font=font(10)).pack(anchor="w", pady=(2, 0))
        right = tk.Frame(row, bg=C.BG)
        right.pack(side="right")
        self.bell = RoundIconButton(right, "bell", self.show_notifications)
        self.bell.pack(side="right", padx=(12, 0))
        PillSearch(right, placeholder="Search...", command=self.app.global_search).pack(side="right")
        self.update_bell()

    def update_bell(self):
        if self.bell is not None:
            self.bell.set_dot(self.svc.reports.notifications(self.user)[1])

    def show_notifications(self):
        items, _dot = self.svc.reports.notifications(self.user)
        m = Modal(self.app, "Notifications", width=500, accent=C.PRIMARY)
        if not items:
            tk.Label(m.body, text="You are all caught up. Nothing new!", bg=C.WHITE, fg=C.MUTED,
                     font=font(10)).pack(anchor="w", pady=6)
        for heading, text, when in items:
            box = tk.Frame(m.body, bg=C.PRIMARY_MIST)
            box.pack(fill="x", pady=4)
            tk.Label(box, text=f"{heading}   \u2022   {fmt_date(when)}", bg=C.PRIMARY_MIST, fg=C.PRIMARY,
                     font=font(9, "bold"), wraplength=430, justify="left").pack(anchor="w", padx=14, pady=(10, 0))
            tk.Label(box, text=text, bg=C.PRIMARY_MIST, fg=C.TEXT, font=font(10), wraplength=430,
                     justify="left").pack(anchor="w", padx=14, pady=(2, 10))
        HoverButton(m.footer, "Close", m.close, "gray").pack(side="right")
        m.show()


# ======================================================================
#  DASHBOARDS
# ======================================================================
class DashboardBase(BaseScreen):
    """Shared pieces of the student and admin dashboards."""

    def kpi_row(self, specs):
        row = card_row(self.page)
        self.kpis = []
        for i, (label, icon_name, color, variant) in enumerate(specs):
            card = KpiCard(row, label, icon_name, color, variant, delay=i * 130)
            put(row, card, i)
            self.kpis.append(card)

    def profile_card(self, parent, stats):
        card = Card(parent, accent=C.PRIMARY, pad=20)
        b = card.body
        av = tk.Canvas(b, width=96, height=96, bg=C.WHITE, highlightthickness=0)
        av.create_oval(2, 2, 94, 94, fill=C.PRIMARY_SOFT, outline="")
        av.create_oval(10, 10, 86, 86, fill=C.PRIMARY, outline="")
        av.create_text(48, 48, text=self.user.initial, fill="white", font=font(30, "bold"))
        av.pack(pady=(4, 10))
        tk.Label(b, text=self.user.full_name, bg=C.WHITE, fg=C.TEXT, font=font(14, "bold")).pack()
        tk.Label(b, text=f"@{self.user.username}", bg=C.WHITE, fg=C.MUTED, font=font(10)).pack()
        Badge(b, self.user.role.capitalize()).pack(pady=(8, 0))
        row = tk.Frame(b, bg=C.WHITE)
        row.pack(fill="x", pady=(16, 4))
        labels = {}
        for i, (label, key) in enumerate(stats):
            row.grid_columnconfigure(i, weight=1, uniform="ps")
            cell = tk.Frame(row, bg=C.WHITE)
            cell.grid(row=0, column=i)
            tk.Label(cell, text=label, bg=C.WHITE, fg=C.MUTED, font=font(8)).pack()
            labels[key] = tk.Label(cell, text="0", bg=C.WHITE, fg=C.TEXT, font=font(15, "bold"))
            labels[key].pack()
        return card, labels

    def activity_card(self, parent, title, tiles):
        card = Card(parent, accent=C.PRIMARY, pad=20)
        top = tk.Frame(card.body, bg=C.WHITE)
        top.pack(fill="x")
        tk.Label(top, text=title, bg=C.WHITE, fg=C.TEXT, font=font(13, "bold")).pack(side="left")
        tk.Label(top, text="\u25CF On track", bg=C.WHITE, fg=C.GREEN, font=font(9, "bold")).pack(side="left", padx=10)
        tk.Label(top, text="Last 7 days", bg=C.WHITE, fg=C.MUTED, font=font(9)).pack(side="right")
        tile_row = tk.Frame(card.body, bg=C.WHITE)
        tile_row.pack(fill="x", pady=(14, 6))
        made = []
        for label, tag, color in tiles:
            t = StatTile(tile_row, label, tag, color)
            t.pack(side="left", padx=(0, 12))
            made.append(t)
        chart = AnimatedLineChart(card.body, height=200, color=C.PRIMARY)
        chart.pack(fill="x")
        return card, made, chart

    def gauge_card(self, parent, title, subtitle):
        card = Card(parent, accent=C.PRIMARY, pad=20)
        tk.Label(card.body, text=title, bg=C.WHITE, fg=C.TEXT, font=font(13, "bold")).pack(anchor="w")
        sub = tk.Label(card.body, text=subtitle, bg=C.WHITE, fg=C.MUTED, font=font(9), wraplength=170,
                       justify="left")
        sub.pack(anchor="w", pady=(2, 0))
        card.body.bind("<Configure>", lambda e: sub.configure(wraplength=max(80, e.width - 4)))
        gauge = AnimatedGauge(card.body, height=190)
        gauge.pack(fill="x", pady=(8, 0))
        return card, gauge


class StudentDashboard(DashboardBase):
    def build(self):
        self.greeting_header(f"Hello, {self.user.first_name}!", "Explore information and activity about your feedback")
        self.kpi_row([("My Feedback", "mail", C.PRIMARY, "bars"), ("My Suggestions", "bulb", "#8E7CC3", "wave"),
                      ("Total Votes", "vote", "#E9A15B", "plain"), ("Resolved", "check", "#FFFFFF", "accent")])
        r2 = card_row(self.page)
        c, self.tiles, self.line = self.activity_card(r2, "My Activity", [
            ("Feedback sent", "this week", C.PRIMARY), ("Suggestions sent", "this week", "#8E7CC3")])
        put(r2, c, 0, 2)
        c, self.gauge = self.gauge_card(r2, "Resolution Rate", "How much of your feedback was resolved")
        put(r2, c, 2)
        c, self.pstats = self.profile_card(r2, [("Feedback", "f"), ("Ideas", "s"), ("Votes", "v")])
        put(r2, c, 3)
        r3 = card_row(self.page)
        top = Card(r3, accent="#8E7CC3", pad=20)
        card_title(top.body, "Top Voted Suggestions", "View All", lambda: self.app.navigate("board"))
        self.rank = AnimatedRankList(top.body, on_click=lambda i: self.app.navigate("board"))
        self.rank.pack(fill="x")
        put(r3, top, 0, 2)
        rec = Card(r3, accent=C.PRIMARY, pad=20)
        card_title(rec.body, "Recent", "View All", lambda: self.app.navigate("my_submissions"))
        self.recent = tk.Frame(rec.body, bg=C.WHITE)
        self.recent.pack(fill="x")
        put(r3, rec, 2)
        put(r3, self.security_card(r3), 3)
        r4 = card_row(self.page)
        put(r4, self.promo_card(r4), 0, 4)
        self.load()

    def security_card(self, parent):
        card = Card(parent, accent=C.PRIMARY, pad=20)
        b = card.body
        badge = tk.Canvas(b, width=84, height=84, bg=C.WHITE, highlightthickness=0)
        badge.create_oval(2, 2, 82, 82, fill=C.PRIMARY_SOFT, outline="")
        badge.create_image(42, 42, image=icon("lock", C.PRIMARY, 38, 1.7))
        badge.pack(pady=(6, 12))
        tk.Label(b, text="Keep you safe!", bg=C.WHITE, fg=C.TEXT, font=font(13, "bold")).pack()
        tk.Label(b, text="Update your password\nfrom time to time", bg=C.WHITE, fg=C.MUTED, font=font(9),
                 justify="center").pack(pady=(4, 14))
        HoverButton(b, "Update Security", lambda: self.app.navigate("profile"), "primary", height=36).pack()
        return card

    def promo_card(self, parent):
        card = Card(parent, accent=C.PRIMARY, pad=26, bg="#E3EEE6")
        card.body.configure(bg="#E3EEE6")
        row = tk.Frame(card.body, bg="#E3EEE6")
        row.pack(fill="x")
        left = tk.Frame(row, bg="#E3EEE6")
        left.pack(side="left", anchor="w")
        tk.Label(left, text="Have an idea for the school?", bg="#E3EEE6", fg=C.TEXT, font=font(17, "bold")).pack(anchor="w")
        tk.Label(left, text="Suggestions with the most votes get noticed first.\nShare yours, or tell the school about a problem.",
                 bg="#E3EEE6", fg="#4B5A52", font=font(10), justify="left").pack(anchor="w", pady=(6, 16))
        btns = tk.Frame(left, bg="#E3EEE6")
        btns.pack(anchor="w")
        HoverButton(btns, "Add Suggestion  +", lambda: self.app.navigate("submit_suggestion"), "primary").pack(side="left")
        HoverButton(btns, "Send Feedback", lambda: self.app.navigate("submit_feedback"), "outline").pack(side="left", padx=10)
        self._fan = ImageTk.PhotoImage(card_fan_image(300, 170))
        art = tk.Canvas(row, width=300, height=170, bg="#E3EEE6", highlightthickness=0)
        art.create_image(150, 85, image=self._fan)
        art.pack(side="right")
        return card

    def load(self):
        r, uid = self.svc.reports, self.user.user_id
        s = r.student_stats(uid)
        for card, value in zip(self.kpis, (s["feedback"], s["suggestions"], s["votes"], s["resolved"])):
            card.set_value(value)
        for card, kind in zip(self.kpis, ("feedback", "suggestion", "votes", "resolved")):
            card.set_series(r.daily_series(kind, uid))
        days = r.last_days(7, uid)
        self.line.set_data([d for d, _ in days], [n for _, n in days])
        self.tiles[0].set(sum(r.daily_series("feedback", uid)))
        self.tiles[1].set(sum(r.daily_series("suggestion", uid)))
        done, total = r.resolution(uid)
        self.gauge.set_value(done * 100 / total if total else 0, f"{done} of {total} resolved")
        self.pstats["f"].configure(text=str(s["feedback"]))
        self.pstats["s"].configure(text=str(s["suggestions"]))
        self.pstats["v"].configure(text=str(s["votes"]))
        recent_list(self.recent, [(x["title"], f"{x['type']}  \u2022  {fmt_date(x['created_at'])}", x["status"])
                                  for x in r.recent(uid, 4)], 105, "No submissions yet.")
        self.rank.set_data([(t["title"], t["votes"]) for t in r.top_voted(5)])
        self.update_bell()

    def on_data_changed(self):
        self.load()


class AdminDashboard(DashboardBase):
    def build(self):
        self.greeting_header(f"Hello, {self.user.first_name}!", "Explore information and activity about the whole system")
        self.kpi_row([("Total Feedback", "mail", C.PRIMARY, "bars"), ("Total Suggestions", "bulb", "#8E7CC3", "wave"),
                      ("Pending Items", "clock", "#E9A15B", "plain"), ("Active Students", "users", "#FFFFFF", "accent")])
        r2 = card_row(self.page)
        c, self.tiles, self.line = self.activity_card(r2, "Submissions", [
            ("Feedback", "this week", C.PRIMARY), ("Suggestions", "this week", "#8E7CC3")])
        put(r2, c, 0, 2)
        c, self.gauge = self.gauge_card(r2, "Resolution Rate", "Share of all feedback marked as resolved")
        put(r2, c, 2)
        c, self.pstats = self.profile_card(r2, [("Pending", "p"), ("Active", "i"), ("Done", "r")])
        put(r2, c, 3)
        r3 = card_row(self.page)
        c1 = Card(r3, accent="#8E7CC3", pad=20)
        card_title(c1.body, "Feedback by Category")
        self.donut = AnimatedDonutChart(c1.body, height=230)
        self.donut.pack(fill="x")
        put(r3, c1, 0, 2)
        c2 = Card(r3, accent=C.GREEN, pad=20)
        card_title(c2.body, "Feedback Status")
        self.bars = AnimatedBarChart(c2.body, height=230)
        self.bars.pack(fill="x")
        put(r3, c2, 2, 2)
        r4 = card_row(self.page)
        c3 = Card(r4, accent=C.PINK, pad=20)
        card_title(c3.body, "Top Voted Suggestions", "Manage", lambda: self.app.navigate("manage_suggestions"))
        self.rank = AnimatedRankList(c3.body)
        self.rank.pack(fill="x")
        put(r4, c3, 0, 2)
        c4 = Card(r4, accent=C.PRIMARY, pad=20)
        card_title(c4.body, "Latest Submissions", "Review", lambda: self.app.navigate("manage_feedback"))
        self.recent = tk.Frame(c4.body, bg=C.WHITE)
        self.recent.pack(fill="x")
        put(r4, c4, 2, 2)
        self.load()

    def load(self):
        r = self.svc.reports
        s = r.admin_stats()
        for card, value in zip(self.kpis, (s["feedback"], s["suggestions"], s["pending"], s["students"])):
            card.set_value(value)
        for card, kind in zip(self.kpis, ("feedback", "suggestion", "resolved", "feedback")):
            card.set_series(r.daily_series(kind))
        days = r.last_days(7)
        self.line.set_data([d for d, _ in days], [n for _, n in days])
        self.tiles[0].set(sum(r.daily_series("feedback")))
        self.tiles[1].set(sum(r.daily_series("suggestion")))
        done, total = r.resolution()
        self.gauge.set_value(done * 100 / total if total else 0, f"{done} of {total} resolved")
        counts = dict(r.by_status("feedback"))
        self.pstats["p"].configure(text=str(counts.get("Pending", 0)))
        self.pstats["i"].configure(text=str(counts.get("In Progress", 0)))
        self.pstats["r"].configure(text=str(counts.get("Resolved", 0)))
        cats = r.by_category("feedback")
        self.donut.set_data([c for c, _ in cats], [n for _, n in cats], [CATEGORY_COLORS[c] for c, _ in cats])
        st = r.by_status("feedback")
        self.bars.set_data([a for a, _ in st], [n for _, n in st], [STATUS_COLORS[a] for a, _ in st])
        self.rank.set_data([(t["title"], t["votes"]) for t in r.top_voted(5)])
        recent_list(self.recent, [(x["title"], f"{x['type']} by {x['author']}  \u2022  {fmt_date(x['created_at'])}",
                                   x["status"]) for x in r.recent(None, 5)], 260, "Nothing submitted yet.")
        self.update_bell()

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
        accent = C.PRIMARY if self.kind == "feedback" else C.PURPLE
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
        self.app.after(750, lambda: self.app.navigate("my_submissions"))


class SubmitFeedbackScreen(SubmitScreen):
    kind = "feedback"


class SubmitSuggestionScreen(SubmitScreen):
    kind = "suggestion"


# ======================================================================
#  MY SUBMISSIONS (student CRUD)
# ======================================================================
class MySubmissionsScreen(BaseScreen):
    def build(self, query=""):
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
        if query:
            self.search.set_value(query)
        self.search.bind("<KeyRelease>", lambda e: self._debounce())
        card = Card(self.page, accent=C.PRIMARY, pad=14)
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
        color = CATEGORY_COLORS.get(s.category, C.PRIMARY)
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
        c1 = Card(row, accent=C.PRIMARY, pad=24)
        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        av = tk.Canvas(c1.body, width=84, height=84, bg=C.WHITE, highlightthickness=0)
        av.create_oval(2, 2, 82, 82, fill=C.PRIMARY, outline="#CFE0D5", width=4)
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

    def build(self, query=""):
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
        if query:
            self.search.set_value(query)
        HoverButton(bar, "Reset", self.reset, "gray", height=34, width=80).pack(side="right", padx=(0, 10), anchor="s")
        self.search.bind("<KeyRelease>", lambda e: self._debounce())
        card = Card(self.page, accent=C.PRIMARY, pad=14)
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
        left = Card(row, accent=C.PRIMARY, pad=22)
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
        box = tk.Frame(left.body, bg="#F5F3EE")
        box.pack(fill="x")
        tk.Label(box, text=item.description, bg="#F5F3EE", fg=C.TEXT, font=font(10), wraplength=360,
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
            c = tk.Frame(right.body, bg=C.PRIMARY_SOFT)
            c.pack(fill="x", pady=3)
            tk.Label(c, text=f"{r['admin_name']}  \u2022  {fmt_datetime(r['created_at'])}", bg=C.PRIMARY_SOFT, fg=C.PRIMARY,
                     font=font(9, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
            tk.Label(c, text=r["response_text"], bg=C.PRIMARY_SOFT, fg=C.TEXT, font=font(10), wraplength=370,
                     justify="left").pack(anchor="w", padx=12, pady=(2, 8))

    def send(self):
        try:
            self.svc.responses.add(self.item.id, self.user.user_id, self.response.value(), self.status.get())
        except AppError as e:
            flash_error(self.error, str(e))
            return
        self.send_btn.flash(C.GREEN, "\u2713 Sent!")
        self.app.toast.show("Your response was sent to the student.", "success")
        self.app.after(750, lambda: self.app.navigate("manage_feedback"))


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
        rng = Card(self.page, accent=C.PRIMARY, pad=14)
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
