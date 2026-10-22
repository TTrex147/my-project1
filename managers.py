"""
managers.py
The "worker" classes. Each one handles one job and talks to the database,
so the screens (GUI) do not need to write any SQL.

    AuthManager        - login, register
    UserManager        - add / edit / deactivate users, change password
    SubmissionManager  - create / read / update / delete feedback AND suggestions
    VoteManager        - vote / un-vote on suggestions
    ResponseManager    - admin responses to feedback
    ReportGenerator    - numbers for the charts + CSV / PDF export
"""
import csv
import re
from datetime import date, datetime, timedelta
from xml.sax.saxutils import escape

from models import SUBMISSION_TYPES, Suggestion, User
from security import ContentFilter, PasswordHasher
from theme import CATEGORIES, FEEDBACK_STATUSES, SUGGESTION_STATUSES, fmt_date, fmt_datetime


class AppError(Exception):
    """An error with a message that is safe to show to the user."""


# ======================================================================
class UserManager:
    def __init__(self, db):
        self.db = db

    def get(self, user_id):
        row = self.db.query_one("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return User.from_row(row) if row else None

    def list(self, search=""):
        sql = "SELECT * FROM users"
        params = ()
        if search:
            sql += " WHERE full_name LIKE ? OR username LIKE ?"
            params = (f"%{search}%", f"%{search}%")
        sql += " ORDER BY user_id"
        return [User.from_row(r) for r in self.db.query(sql, params)]

    def is_active(self, user_id):
        row = self.db.query_one("SELECT is_active FROM users WHERE user_id = ?", (user_id,))
        return bool(row and row["is_active"])

    # ---- checks
    def _check(self, full_name, username, password, role, user_id=None):
        if len(full_name.strip()) < 2:
            raise AppError("Please enter the full name.")
        if not re.fullmatch(r"[A-Za-z0-9_]{4,20}", username):
            raise AppError("Username must be 4-20 letters, numbers or underscore.")
        if password is not None and len(password) < 6:
            raise AppError("Password must be at least 6 characters.")
        if role not in ("student", "admin"):
            raise AppError("Please choose a role.")
        taken = self.db.query_one("SELECT user_id FROM users WHERE username = ?", (username,))
        if taken and taken["user_id"] != user_id:
            raise AppError("That username is already taken.")

    # ---- create / update
    def create(self, full_name, username, password, role="student"):
        username = username.strip().lower()
        self._check(full_name, username, password, role)
        return self.db.execute(
            "INSERT INTO users (full_name, username, password_hash, role) VALUES (?,?,?,?)",
            (full_name.strip(), username, PasswordHasher.hash(password), role))

    def update(self, user_id, full_name, username, role, new_password=None):
        username = username.strip().lower()
        self._check(full_name, username, new_password or None, role, user_id)
        self.db.execute("UPDATE users SET full_name=?, username=?, role=? WHERE user_id=?",
                        (full_name.strip(), username, role, user_id))
        if new_password:
            self.db.execute("UPDATE users SET password_hash=? WHERE user_id=?",
                            (PasswordHasher.hash(new_password), user_id))

    def update_name(self, user_id, full_name):
        if len(full_name.strip()) < 2:
            raise AppError("Please enter your full name.")
        self.db.execute("UPDATE users SET full_name=? WHERE user_id=?", (full_name.strip(), user_id))

    def set_active(self, user_id, active):
        self.db.execute("UPDATE users SET is_active=? WHERE user_id=?", (1 if active else 0, user_id))

    def change_password(self, user_id, old, new, confirm):
        row = self.db.query_one("SELECT password_hash FROM users WHERE user_id=?", (user_id,))
        if not row or not PasswordHasher.verify(old, row["password_hash"]):
            raise AppError("Your current password is not correct.")
        if len(new) < 6:
            raise AppError("New password must be at least 6 characters.")
        if new != confirm:
            raise AppError("The new passwords do not match.")
        self.db.execute("UPDATE users SET password_hash=? WHERE user_id=?",
                        (PasswordHasher.hash(new), user_id))


# ======================================================================
class AuthManager:
    def __init__(self, db, users):
        self.db = db
        self.users = users

    def login(self, username, password, role):
        username = username.strip().lower()
        if not username or not password:
            raise AppError("Please enter your username and password.")
        row = self.db.query_one("SELECT * FROM users WHERE username = ?", (username,))
        if (not row or row["role"] != role
                or not PasswordHasher.verify(password, row["password_hash"])):
            raise AppError("Wrong username, password or role. Please try again.")
        if not row["is_active"]:
            raise AppError("This account is deactivated. Please contact the admin.")
        return User.from_row(row)

    def register_student(self, full_name, username, password, confirm):
        if password != confirm:
            raise AppError("The passwords do not match.")
        self.users.create(full_name, username, password, "student")


# ======================================================================
class SubmissionManager:
    """Works for both feedback and suggestions (polymorphism: kind -> class)."""

    def __init__(self, db):
        self.db = db
        self.filter = ContentFilter()

    # ---- validation
    def _validate(self, title, category, description):
        title, description = title.strip(), description.strip()
        if not title:
            raise AppError("Please enter a title.")
        if len(title) > 100:
            raise AppError("The title is too long (maximum 100 characters).")
        if category not in CATEGORIES:
            raise AppError("Please choose a category.")
        if len(description) < 10:
            raise AppError("Please write at least 10 characters in the description.")
        if len(description) > 500:
            raise AppError("The description is too long (maximum 500 characters).")
        if self.filter.find_bad_words(f"{title} {description}"):
            raise AppError("Your message has words that are not allowed. Please rewrite it politely.")
        return title, description

    # ---- create
    def create(self, kind, user_id, title, category, description):
        title, description = self._validate(title, category, description)
        cls = SUBMISSION_TYPES[kind]
        return self.db.execute(
            f"INSERT INTO {cls.TABLE} (user_id, title, description, category) VALUES (?,?,?,?)",
            (user_id, title, description, category))

    # ---- read
    def _select(self, kind, viewer_id):
        cls = SUBMISSION_TYPES[kind]
        sql = f"SELECT t.*, u.full_name AS author"
        if kind == "suggestion":
            sql += (", (SELECT COUNT(*) FROM votes v WHERE v.suggestion_id = t.suggestion_id) AS votes"
                    ", EXISTS(SELECT 1 FROM votes v WHERE v.suggestion_id = t.suggestion_id"
                    f" AND v.user_id = {int(viewer_id)}) AS voted_by_me")
        sql += f" FROM {cls.TABLE} t JOIN users u ON u.user_id = t.user_id"
        return cls, sql

    def list(self, kind, user_id=None, category=None, status=None, search=None,
             viewer_id=0, order="newest"):
        cls, sql = self._select(kind, viewer_id)
        sql += " WHERE 1=1"
        params = []
        if user_id:
            sql += " AND t.user_id = ?"
            params.append(user_id)
        if category and category != "All":
            sql += " AND t.category = ?"
            params.append(category)
        if status and status != "All":
            sql += " AND t.status = ?"
            params.append(status)
        if search:
            sql += " AND (t.title LIKE ? OR t.description LIKE ? OR u.full_name LIKE ?)"
            params += [f"%{search}%"] * 3
        if order == "votes" and kind == "suggestion":
            sql += f" ORDER BY votes DESC, t.created_at DESC, t.{cls.ID_COLUMN} DESC"
        else:
            sql += f" ORDER BY t.created_at DESC, t.{cls.ID_COLUMN} DESC"
        return [cls(r) for r in self.db.query(sql, params)]

    def get(self, kind, item_id, viewer_id=0):
        cls, sql = self._select(kind, viewer_id)
        row = self.db.query_one(sql + f" WHERE t.{cls.ID_COLUMN} = ?", (item_id,))
        return cls(row) if row else None

    # ---- update
    def update(self, kind, item_id, user_id, title, category, description):
        item = self.get(kind, item_id)
        if item is None:
            raise AppError("This item no longer exists.")
        if item.user_id != user_id or not item.can_be_changed_by_student:
            raise AppError("This item can no longer be edited.")
        title, description = self._validate(title, category, description)
        cls = SUBMISSION_TYPES[kind]
        extra = ", updated_at = CURRENT_TIMESTAMP" if kind == "feedback" else ""
        self.db.execute(
            f"UPDATE {cls.TABLE} SET title=?, description=?, category=?{extra} WHERE {cls.ID_COLUMN}=?",
            (title, description, category, item_id))

    def set_status(self, kind, item_id, status):
        cls = SUBMISSION_TYPES[kind]
        allowed = FEEDBACK_STATUSES if kind == "feedback" else SUGGESTION_STATUSES
        if status not in allowed:
            raise AppError("Please choose a valid status.")
        extra = ", updated_at = CURRENT_TIMESTAMP" if kind == "feedback" else ""
        self.db.execute(f"UPDATE {cls.TABLE} SET status=?{extra} WHERE {cls.ID_COLUMN}=?",
                        (status, item_id))

    # ---- delete
    def delete(self, kind, item_id, user_id):
        item = self.get(kind, item_id)
        if item is None:
            return
        if item.user_id != user_id or not item.can_be_changed_by_student:
            raise AppError("This item can no longer be deleted.")
        cls = SUBMISSION_TYPES[kind]
        child = ("DELETE FROM responses WHERE feedback_id = ?" if kind == "feedback"
                 else "DELETE FROM votes WHERE suggestion_id = ?")
        self.db.transaction([
            (child, (item_id,)),
            (f"DELETE FROM {cls.TABLE} WHERE {cls.ID_COLUMN} = ?", (item_id,)),
        ])


# ======================================================================
class VoteManager:
    def __init__(self, db, submissions):
        self.db = db
        self.submissions = submissions

    def toggle(self, user_id, suggestion_id):
        """Vote if not voted yet, remove the vote if already voted. Returns True if now voted."""
        item = self.submissions.get("suggestion", suggestion_id)
        if item is None:
            raise AppError("This suggestion no longer exists.")
        if item.user_id == user_id:
            raise AppError("You cannot vote for your own suggestion.")
        if item.status == "Rejected":
            raise AppError("Voting is closed for rejected suggestions.")
        found = self.db.query_one("SELECT vote_id FROM votes WHERE user_id=? AND suggestion_id=?",
                                  (user_id, suggestion_id))
        if found:
            self.db.execute("DELETE FROM votes WHERE vote_id = ?", (found["vote_id"],))
            return False
        self.db.execute("INSERT INTO votes (user_id, suggestion_id) VALUES (?,?)",
                        (user_id, suggestion_id))
        return True


# ======================================================================
class ResponseManager:
    def __init__(self, db):
        self.db = db
        self.filter = ContentFilter()

    def add(self, feedback_id, admin_id, text, new_status):
        text = text.strip()
        if len(text) < 5:
            raise AppError("Please write your response first.")
        if len(text) > 500:
            raise AppError("The response is too long (maximum 500 characters).")
        if self.filter.find_bad_words(text):
            raise AppError("Your response has words that are not allowed.")
        if new_status not in FEEDBACK_STATUSES:
            raise AppError("Please choose a status.")
        self.db.transaction([
            ("INSERT INTO responses (feedback_id, admin_id, response_text) VALUES (?,?,?)",
             (feedback_id, admin_id, text)),
            ("UPDATE feedback SET status=?, updated_at=CURRENT_TIMESTAMP WHERE feedback_id=?",
             (new_status, feedback_id)),
        ])

    def for_feedback(self, feedback_id):
        return self.db.query(
            "SELECT r.*, u.full_name AS admin_name FROM responses r "
            "JOIN users u ON u.user_id = r.admin_id WHERE r.feedback_id = ? "
            "ORDER BY r.created_at DESC, r.response_id DESC", (feedback_id,))


# ======================================================================
class ReportData:
    """A report that is ready to be shown or exported."""

    def __init__(self, title, date_range, summary, columns, rows):
        self.title = title
        self.date_range = date_range
        self.summary = summary          # list of (label, value)
        self.columns = columns
        self.rows = rows


class ReportGenerator:
    def __init__(self, db, submissions):
        self.db = db
        self.submissions = submissions

    # ---- small helper to filter by date
    @staticmethod
    def _range(column, start, end):
        if start and end:
            return f" AND date({column}, 'localtime') BETWEEN ? AND ?", [start, end]
        return "", []

    # ---- dashboard numbers
    def student_stats(self, user_id):
        one = lambda sql, p=(): self.db.query_one(sql, p)[0]
        return {
            "feedback": one("SELECT COUNT(*) FROM feedback WHERE user_id=?", (user_id,)),
            "suggestions": one("SELECT COUNT(*) FROM suggestions WHERE user_id=?", (user_id,)),
            "votes": one("SELECT COUNT(*) FROM votes v JOIN suggestions s "
                         "ON s.suggestion_id = v.suggestion_id WHERE s.user_id=?", (user_id,)),
            "resolved": one("SELECT COUNT(*) FROM feedback WHERE user_id=? AND status='Resolved'",
                            (user_id,)),
        }

    def admin_stats(self):
        one = lambda sql: self.db.query_one(sql)[0]
        return {
            "feedback": one("SELECT COUNT(*) FROM feedback"),
            "suggestions": one("SELECT COUNT(*) FROM suggestions"),
            "pending": one("SELECT (SELECT COUNT(*) FROM feedback WHERE status='Pending')"
                           " + (SELECT COUNT(*) FROM suggestions WHERE status='Pending')"),
            "students": one("SELECT COUNT(*) FROM users WHERE role='student' AND is_active=1"),
        }

    def recent(self, user_id=None, limit=5):
        where = "WHERE f.user_id = ?" if user_id else ""
        where_s = "WHERE s.user_id = ?" if user_id else ""
        p = (user_id,) if user_id else ()
        sql = ("SELECT 'Feedback' AS type, f.title AS title, f.status AS status, f.created_at AS created_at, u.full_name AS author "
               f"FROM feedback f JOIN users u ON u.user_id = f.user_id {where} "
               "UNION ALL SELECT 'Suggestion', s.title, s.status, s.created_at, u.full_name "
               f"FROM suggestions s JOIN users u ON u.user_id = s.user_id {where_s} "
               f"ORDER BY created_at DESC LIMIT {int(limit)}")
        return self.db.query(sql, p + p)

    def top_voted(self, limit=5, start=None, end=None):
        cond, params = self._range("t.created_at", start, end)
        sql = ("SELECT t.title, t.category, "
               "(SELECT COUNT(*) FROM votes v WHERE v.suggestion_id = t.suggestion_id) AS votes "
               f"FROM suggestions t WHERE 1=1 {cond} "
               "ORDER BY votes DESC, t.created_at DESC LIMIT ?")
        return [r for r in self.db.query(sql, params + [limit]) if r["votes"] > 0]

    # ---- chart data
    def by_category(self, kind, start=None, end=None):
        cls = SUBMISSION_TYPES[kind]
        cond, params = self._range("created_at", start, end)
        rows = self.db.query(f"SELECT category, COUNT(*) AS n FROM {cls.TABLE} WHERE 1=1 {cond} "
                             "GROUP BY category", params)
        counts = {r["category"] or "Others": r["n"] for r in rows}
        return [(c, counts[c]) for c in CATEGORIES if counts.get(c)]

    def by_status(self, kind, start=None, end=None):
        cls = SUBMISSION_TYPES[kind]
        cond, params = self._range("created_at", start, end)
        rows = self.db.query(f"SELECT status, COUNT(*) AS n FROM {cls.TABLE} WHERE 1=1 {cond} "
                             "GROUP BY status", params)
        counts = {r["status"]: r["n"] for r in rows}
        order = FEEDBACK_STATUSES if kind == "feedback" else SUGGESTION_STATUSES
        return [(s, counts.get(s, 0)) for s in order]

    def votes_by_category(self, start=None, end=None):
        cond, params = self._range("s.created_at", start, end)
        rows = self.db.query("SELECT s.category, COUNT(v.vote_id) AS n FROM suggestions s "
                             f"JOIN votes v ON v.suggestion_id = s.suggestion_id WHERE 1=1 {cond} "
                             "GROUP BY s.category", params)
        counts = {r["category"] or "Others": r["n"] for r in rows}
        return [(c, counts[c]) for c in CATEGORIES if counts.get(c)]

    def last_days(self, days=7, user_id=None):
        """Number of submissions (feedback + suggestions) for each of the last days."""
        today = date.today()
        first = today - timedelta(days=days - 1)
        who = " WHERE user_id = ?" if user_id else ""
        p = (user_id,) if user_id else ()
        rows = self.db.query(
            "SELECT d, SUM(n) AS n FROM ("
            f" SELECT date(created_at,'localtime') AS d, COUNT(*) AS n FROM feedback{who} GROUP BY d"
            " UNION ALL"
            f" SELECT date(created_at,'localtime'), COUNT(*) FROM suggestions{who} GROUP BY 1"
            ") WHERE d >= ? GROUP BY d", p + p + (first.isoformat(),))
        counts = {r["d"]: r["n"] for r in rows}
        result = []
        for i in range(days):
            day = first + timedelta(days=i)
            result.append((day.strftime("%b %d").replace(" 0", " "), counts.get(day.isoformat(), 0)))
        return result

    def daily_series(self, kind, user_id=None, days=7):
        """Small list of numbers (oldest first) for the mini charts on the KPI cards.
        kind: 'feedback', 'suggestion', 'votes' (votes received) or 'resolved'."""
        first = date.today() - timedelta(days=days - 1)
        params = []
        if kind == "votes":
            sql = ("SELECT date(v.created_at,'localtime') AS d, COUNT(*) AS n FROM votes v "
                   "JOIN suggestions s ON s.suggestion_id = v.suggestion_id WHERE 1=1")
            if user_id:
                sql += " AND s.user_id = ?"
                params.append(user_id)
            sql += " AND date(v.created_at,'localtime') >= ? GROUP BY d"
        else:
            table, column, extra = {
                "feedback": ("feedback", "created_at", ""),
                "suggestion": ("suggestions", "created_at", ""),
                "resolved": ("feedback", "updated_at", " AND status = 'Resolved'"),
            }[kind]
            sql = f"SELECT date({column},'localtime') AS d, COUNT(*) AS n FROM {table} WHERE 1=1{extra}"
            if user_id:
                sql += " AND user_id = ?"
                params.append(user_id)
            sql += f" AND date({column},'localtime') >= ? GROUP BY d"
        params.append(first.isoformat())
        counts = {r["d"]: r["n"] for r in self.db.query(sql, params)}
        return [counts.get((first + timedelta(days=i)).isoformat(), 0) for i in range(days)]

    def resolution(self, user_id=None):
        """(resolved feedback, all feedback)"""
        where = " WHERE user_id = ?" if user_id else ""
        p = (user_id,) if user_id else ()
        total = self.db.query_one(f"SELECT COUNT(*) FROM feedback{where}", p)[0]
        done = self.db.query_one(f"SELECT COUNT(*) FROM feedback{where}{' AND' if where else ' WHERE'} status = 'Resolved'", p)[0]
        return done, total

    def notifications(self, user):
        """(list of (heading, text, date), show_red_dot) for the bell button."""
        if user.role == "student":
            rows = self.db.query(
                "SELECT f.title, r.response_text, r.created_at, u.full_name FROM responses r "
                "JOIN feedback f ON f.feedback_id = r.feedback_id JOIN users u ON u.user_id = r.admin_id "
                "WHERE f.user_id = ? ORDER BY r.created_at DESC, r.response_id DESC LIMIT 5", (user.user_id,))
            items = [(f"{r['full_name']} replied to \"{r['title']}\"", r["response_text"], r["created_at"])
                     for r in rows]
            week_ago = (date.today() - timedelta(days=7)).isoformat()
            return items, any(fmt_date(i[2]) >= week_ago for i in items)
        rows = self.db.query(
            "SELECT 'Feedback' AS type, title, created_at FROM feedback WHERE status='Pending' "
            "UNION ALL SELECT 'Suggestion', title, created_at FROM suggestions WHERE status='Pending' "
            "ORDER BY created_at DESC LIMIT 6")
        items = [(f"New {r['type'].lower()} waiting", r["title"], r["created_at"]) for r in rows]
        return items, bool(items)

    # ---- full reports (for export)
    def build_report(self, kind, start, end):
        range_text = f"{start} to {end}"
        if kind in ("feedback", "suggestion"):
            items = [i for i in self.submissions.list(kind)
                     if start <= to_iso(i.created_at) <= end]
            cols = ["ID", "Title", "Category", "Status", "Submitted By", "Date"]
            rows = [[i.code, i.title, i.category, i.status, i.author, i.date] for i in items]
            if kind == "suggestion":
                cols.insert(5, "Votes")
                for r, i in zip(rows, items):
                    r.insert(5, i.votes)
            statuses = self.by_status(kind, start, end)
            summary = [("Total", len(items))] + [(s, n) for s, n in statuses]
            name = "Feedback Report" if kind == "feedback" else "Suggestion Report"
            return ReportData(name, range_text, summary, cols, rows)
        top = self.top_voted(10, start, end)
        rows = [[i + 1, r["title"], r["category"], r["votes"]] for i, r in enumerate(top)]
        summary = [("Suggestions with votes", len(top)),
                   ("Total votes", sum(r["votes"] for r in top))]
        return ReportData("Top Voted Suggestions", range_text, summary,
                          ["Rank", "Title", "Category", "Votes"], rows)

    @staticmethod
    def export_csv(report, path):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow([report.title])
            w.writerow(["Date range", report.date_range])
            w.writerow([])
            for label, value in report.summary:
                w.writerow([label, value])
            w.writerow([])
            w.writerow(report.columns)
            w.writerows(report.rows)

    @staticmethod
    def export_pdf(report, path):
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except ImportError:
            raise AppError("PDF export needs reportlab. Install it with: pip install reportlab")
        styles = getSampleStyleSheet()
        small = styles["BodyText"]
        small.fontSize = 8
        small.leading = 10
        story = [Paragraph(escape(report.title), styles["Title"]),
                 Paragraph(f"Date range: {escape(report.date_range)}", styles["Normal"]),
                 Paragraph("Generated: " + datetime.now().strftime("%B %d, %Y %I:%M %p"),
                           styles["Normal"]), Spacer(1, 14)]
        summary = Table([[str(a), str(b)] for a, b in report.summary], hAlign="LEFT", colWidths=[130, 60])
        summary.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
                                     ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E7F0FF"))]))
        story += [summary, Spacer(1, 14)]
        data = [report.columns] + [[Paragraph(escape(str(c)), small) for c in r] for r in report.rows]
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A2A63")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F5FA")]),
        ]))
        story.append(table)
        SimpleDocTemplate(path, pagesize=A4, leftMargin=30, rightMargin=30,
                          topMargin=30, bottomMargin=30).build(story)


def to_iso(ts):
    """'2026-10-12 03:15:00' (UTC, from database) -> '2026-10-12' (local date)."""
    return fmt_date(ts)


# ======================================================================
class Services:
    """One object that holds all managers, so screens can reach them easily."""

    def __init__(self, db):
        self.db = db
        self.users = UserManager(db)
        self.auth = AuthManager(db, self.users)
        self.submissions = SubmissionManager(db)
        self.votes = VoteManager(db, self.submissions)
        self.responses = ResponseManager(db)
        self.reports = ReportGenerator(db, self.submissions)
