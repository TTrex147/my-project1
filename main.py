"""
main.py  -  run this file to start the app:   python main.py

Integrated Student Feedback and Suggestion Management System
SDF04 - Object-Oriented Programming (Python & Database)
"""
import sys
import tkinter as tk

try:
    from PIL import Image  # noqa: F401  (Pillow draws the pictures, icons and the glass login)
except ImportError:
    from tkinter import messagebox
    _root = tk.Tk()
    _root.withdraw()
    messagebox.showerror("Pillow is missing", "This program needs the Pillow library.\n\n"
                         "Open a terminal and type:\n\n    pip install pillow")
    sys.exit(1)

from database import Database
from login_glass import GlassLoginScreen
from managers import Services
from screens import (AdminDashboard, ManageFeedbackScreen, ManageSuggestionsScreen,
                     ManageUsersScreen, MySubmissionsScreen, ProfileScreen, ReportsScreen,
                     RespondScreen, StudentDashboard, SubmitFeedbackScreen, SubmitSuggestionScreen,
                     SuggestionBoardScreen)
from seed import seed_if_empty
from theme import C, animate, ease_out_cubic
from widgets import Sidebar, Toast, destroy_tree, find_scroll_parent, setup_styles, wheel_units

# screens that belong to a role: key -> screen class
SCREENS = {
    "student": {
        "dashboard": StudentDashboard,
        "submit_feedback": SubmitFeedbackScreen,
        "submit_suggestion": SubmitSuggestionScreen,
        "my_submissions": MySubmissionsScreen,
        "board": SuggestionBoardScreen,
        "profile": ProfileScreen,
    },
    "admin": {
        "dashboard": AdminDashboard,
        "manage_feedback": ManageFeedbackScreen,
        "manage_suggestions": ManageSuggestionsScreen,
        "manage_users": ManageUsersScreen,
        "reports": ReportsScreen,
        "profile": ProfileScreen,
        "respond": RespondScreen,
    },
}
# a screen that should highlight another menu item
NAV_PARENT = {"respond": "manage_feedback"}

SYNC_EVERY_MS = 1500        # how often we check if another user changed the database
SIDEBAR_SPACE = 112         # room on the left for the floating sidebar


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Integrated Student Feedback and Suggestion Management System")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(1280, sw - 60), min(800, sh - 90)
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 2 - 20)}")
        self.minsize(1060, 620)
        self.configure(bg=C.BG)
        setup_styles(self)

        self.db = Database()
        seed_if_empty(self.db)
        self.services = Services(self.db)
        self.user = None
        self.sidebar = None
        self.current = None
        self.toast = Toast(self)
        self._last_version = self.db.data_version()

        self.container = tk.Frame(self, bg=C.BG)
        self.container.pack(fill="both", expand=True)
        self.bind_all("<MouseWheel>", self._wheel)
        self.bind_all("<Button-4>", self._wheel)
        self.bind_all("<Button-5>", self._wheel)
        self.protocol("WM_DELETE_WINDOW", self._quit)
        self.show_login()
        self.after(SYNC_EVERY_MS, self._poll)

    # ------------------------------------------------------------ login / logout
    def _clear(self):
        for child in self.container.winfo_children():
            destroy_tree(child)
        self.sidebar = self.current = None

    def show_login(self):
        self.user = None
        self._clear()
        GlassLoginScreen(self.container, self).pack(fill="both", expand=True)

    def login_success(self, user):
        self.user = user
        self._clear()
        self._build_shell()
        self.navigate("dashboard")
        self.toast.show(f"Welcome, {user.first_name}!", "success", 2200)

    def _build_shell(self):
        self.content = tk.Frame(self.container, bg=C.BG)
        self.content.pack(fill="both", expand=True, padx=(SIDEBAR_SPACE, 0))
        self._make_sidebar()

    def _make_sidebar(self):
        self.sidebar = Sidebar(self.container, self.user, self.navigate, self.logout)
        self.sidebar.place(x=22, y=22, width=Sidebar.COLLAPSED + 6, relheight=1.0, height=-44)

    def refresh_sidebar(self):
        """Rebuild the sidebar (used after the user changes the name)."""
        key = getattr(self, "current_key", "dashboard")
        destroy_tree(self.sidebar)
        self._make_sidebar()
        self.sidebar.set_active(NAV_PARENT.get(key, key))

    def logout(self):
        self.show_login()
        self.toast.show("You have been logged out.", "info", 2000)

    # ------------------------------------------------------------ navigation
    def navigate(self, key, **params):
        if self.current is not None:
            destroy_tree(self.current)
        screen_class = SCREENS[self.user.role][key]
        screen = screen_class(self.content, self, **params)
        self.current, self.current_key = screen, key
        screen.place(x=0, y=24, relwidth=1, relheight=1)          # slide up animation
        animate(screen, 300, lambda t: screen.place_configure(y=round(24 * (1 - t))), ease=ease_out_cubic)
        self.sidebar.set_active(NAV_PARENT.get(key, key))
        tk.Misc.lift(self.sidebar)          # keep the sidebar on top of the page

    def global_search(self, query):
        """The search box on the dashboard: opens the list screen with the text already typed."""
        if self.user.role == "student":
            self.navigate("my_submissions", query=query)
        else:
            self.navigate("manage_feedback", query=query)

    # ------------------------------------------------------------ live sync
    def _poll(self):
        try:
            version = self.db.data_version()
            if version != self._last_version:
                self._last_version = version
                if self.user is not None:
                    if not self.services.users.is_active(self.user.user_id):
                        self.show_login()
                        self.toast.show("Your account was deactivated by an admin.", "warning", 4000)
                    elif self.current is not None:
                        self.sidebar.flash_sync()
                        self.current.on_data_changed()
        finally:
            self.after(SYNC_EVERY_MS, self._poll)

    # ------------------------------------------------------------ mouse wheel
    def _wheel(self, event):
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
        except (KeyError, tk.TclError):
            return
        if widget is None or isinstance(widget, tk.Text) or widget.winfo_toplevel() is not self:
            return
        scroller = find_scroll_parent(widget)
        if scroller:
            scroller.scroll(wheel_units(event))

    def _quit(self):
        self.db.close()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
