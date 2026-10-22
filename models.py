"""
models.py
The main classes of the system. This is where the OOP ideas are used:

* Abstraction   - User and Submission are abstract classes (cannot be used alone)
* Inheritance   - Student and Admin inherit from User
                  Feedback and Suggestion inherit from Submission
* Polymorphism  - each child class answers the same methods in its own way
                  (menu_items(), kind, statuses ...)
* Encapsulation - data is private (_name) and read through properties
"""
from abc import ABC, abstractmethod

from theme import FEEDBACK_STATUSES, SUGGESTION_STATUSES, fmt_date


# ======================================================================
#  USERS
# ======================================================================
class User(ABC):
    def __init__(self, user_id, full_name, username, is_active=True, created_at=""):
        self._user_id = user_id
        self._full_name = full_name
        self._username = username
        self._is_active = bool(is_active)
        self._created_at = created_at

    # ---- read-only properties (encapsulation)
    @property
    def user_id(self):
        return self._user_id

    @property
    def full_name(self):
        return self._full_name

    @property
    def username(self):
        return self._username

    @property
    def is_active(self):
        return self._is_active

    @property
    def created_at(self):
        return self._created_at

    @property
    def first_name(self):
        return self._full_name.split()[0] if self._full_name else ""

    @property
    def initial(self):
        return self._full_name[:1].upper() if self._full_name else "?"

    def rename(self, new_name):
        self._full_name = new_name.strip()

    # ---- each child class must answer these (abstraction)
    @property
    @abstractmethod
    def role(self):
        ...

    @abstractmethod
    def menu_items(self):
        """List of (screen_key, label, icon_name) for the sidebar. Icon names come from icons.py."""

    # ---- build the right child class from a database row
    @staticmethod
    def from_row(row):
        cls = Admin if row["role"] == "admin" else Student
        return cls(row["user_id"], row["full_name"], row["username"],
                   row["is_active"], row["created_at"])


class Student(User):
    @property
    def role(self):
        return "student"

    def menu_items(self):
        return [
            ("dashboard", "Dashboard", "dashboard"),
            ("submit_feedback", "Submit Feedback", "edit"),
            ("submit_suggestion", "Submit Suggestion", "bulb"),
            ("my_submissions", "My Submissions", "list"),
            ("board", "Suggestion Board", "vote"),
            ("profile", "Profile", "user"),
        ]


class Admin(User):
    @property
    def role(self):
        return "admin"

    def menu_items(self):
        return [
            ("dashboard", "Dashboard", "dashboard"),
            ("manage_feedback", "Manage Feedback", "mail"),
            ("manage_suggestions", "Manage Suggestions", "star"),
            ("manage_users", "Manage Users", "users"),
            ("reports", "Reports", "chart"),
            ("profile", "Profile", "user"),
        ]


# ======================================================================
#  SUBMISSIONS (feedback and suggestions)
# ======================================================================
class Submission(ABC):
    TABLE = ""
    ID_COLUMN = ""

    def __init__(self, row):
        keys = row.keys()
        self._id = row[self.ID_COLUMN]
        self._user_id = row["user_id"]
        self._title = row["title"]
        self._description = row["description"]
        self._category = row["category"] or "Others"
        self._status = row["status"]
        self._created_at = row["created_at"]
        self._author = row["author"] if "author" in keys else ""

    @property
    def id(self):
        return self._id

    @property
    def user_id(self):
        return self._user_id

    @property
    def title(self):
        return self._title

    @property
    def description(self):
        return self._description

    @property
    def category(self):
        return self._category

    @property
    def status(self):
        return self._status

    @property
    def created_at(self):
        return self._created_at

    @property
    def date(self):
        return fmt_date(self._created_at)

    @property
    def author(self):
        return self._author

    @property
    def code(self):
        return f"#{self._id:03d}"

    @property
    def can_be_changed_by_student(self):
        """Students can only edit or delete while the status is still Pending."""
        return self._status == "Pending"

    @property
    @abstractmethod
    def kind(self):
        ...

    @property
    @abstractmethod
    def statuses(self):
        ...


class Feedback(Submission):
    TABLE = "feedback"
    ID_COLUMN = "feedback_id"

    @property
    def kind(self):
        return "feedback"

    @property
    def statuses(self):
        return FEEDBACK_STATUSES


class Suggestion(Submission):
    TABLE = "suggestions"
    ID_COLUMN = "suggestion_id"

    def __init__(self, row):
        super().__init__(row)
        keys = row.keys()
        self._votes = row["votes"] if "votes" in keys else 0
        self._voted_by_me = bool(row["voted_by_me"]) if "voted_by_me" in keys else False

    @property
    def kind(self):
        return "suggestion"

    @property
    def statuses(self):
        return SUGGESTION_STATUSES

    @property
    def votes(self):
        return self._votes

    @property
    def voted_by_me(self):
        return self._voted_by_me


SUBMISSION_TYPES = {"feedback": Feedback, "suggestion": Suggestion}
