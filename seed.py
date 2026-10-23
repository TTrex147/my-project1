"""
seed.py
Fills an empty database on the first run:
  * always: one admin account
  * if SEED_DEMO_DATA is True: sample students, feedback, suggestions, votes
    (so the charts and tables are not empty during your demo).

Set SEED_DEMO_DATA = False if you want a clean database.
"""
import random
from datetime import datetime, timedelta, timezone

from security import PasswordHasher

SEED_DEMO_DATA = True

ADMIN = ("Admin User", "admin", "admin123")
STUDENT_PASSWORD = "student123"

STUDENTS = [
    ("Juan Dela Cruz", "juan123"), ("Maria Santos", "maria456"), ("Carlo Reyes", "carlo789"),
    ("Ana Garcia", "ana123"), ("Paolo Mendoza", "paolo123"), ("Bea Ramirez", "bea123"),
    ("Luis Navarro", "luis123"), ("Kyla Bautista", "kyla123"), ("Rico Fernandez", "rico123"),
    ("Sofia Castillo", "sofia123"), ("Miguel Aquino", "miguel123"), ("Trisha Domingo", "trisha123"),
    ("tung tung sahur", "tungtungsahur")
]

FEEDBACK = [
    ("Library is too noisy", "Facilities", "Pending", "The library is too noisy, especially during group study. It is hard to focus."),
    ("Slow internet in the lab", "Technology", "In Progress", "The Wi-Fi in the computer lab keeps disconnecting during our online exams."),
    ("Unfair grading", "Teaching", "Resolved", "Some quizzes were checked without a clear rubric. Please explain how we are graded."),
    ("Broken chairs", "Facilities", "Pending", "Many chairs in Room 204 are broken and some students have to stand."),
    ("Too cold in classrooms", "Facilities", "In Progress", "The aircon in the 3rd floor rooms is too cold, we need jackets during class."),
    ("Long enrollment lines", "Academics", "Resolved", "The enrollment line takes more than two hours. Please add more counters."),
    ("Projector not working", "Technology", "Pending", "The projector in Room 310 has not worked for two weeks already."),
    ("Dirty comfort rooms", "Facilities", "Pending", "The comfort rooms near the gym are not cleaned regularly."),
    ("Lack of lab equipment", "Academics", "In Progress", "We are sharing one microscope for five students in Biology lab."),
    ("Expensive cafeteria meals", "Cafeteria", "Pending", "The meals in the cafeteria are too expensive for a student budget."),
    ("Schedule conflicts", "Academics", "Resolved", "Two of our required subjects are scheduled at the same time."),
    ("Teacher always late", "Teaching", "Pending", "Our professor in Math 2 is often 30 minutes late to class."),
    ("Printer is always out of ink", "Technology", "Resolved", "The student printer on the 2nd floor has no ink most of the time."),
    ("Not enough outlets", "Facilities", "Pending", "There are not enough power outlets in the study area for our laptops."),
    ("Unclear class announcements", "Others", "Pending", "Announcements are posted in many different places, it is confusing."),
    ("Water dispenser is empty", "Cafeteria", "In Progress", "The water dispenser on the 4th floor is empty almost every afternoon."),
]

SUGGESTIONS = [
    ("More study areas", "Facilities", "Approved", "Please add more quiet study areas with tables and chairs for students."),
    ("Extend library hours", "Facilities", "Under Review", "Open the library until 9 PM during exam weeks so we can study longer."),
    ("Better Wi-Fi", "Technology", "Pending", "Install more access points so the Wi-Fi is strong in all buildings."),
    ("More trash bins", "Facilities", "Approved", "Add trash bins and recycling bins around the campus to keep it clean."),
    ("Affordable food options", "Cafeteria", "Rejected", "Add a budget meal for 50 pesos in the cafeteria every day."),
    ("Online consultation hours", "Academics", "Under Review", "Let professors hold consultation hours online for students who commute far."),
    ("Student lounge", "Facilities", "Pending", "A lounge where students can rest between classes would be very helpful."),
    ("Free tutorial sessions", "Academics", "Approved", "Senior students can give free tutorial sessions on weekends."),
    ("Charging stations", "Technology", "Pending", "Add phone and laptop charging stations in the hallways."),
    ("Suggestion box app day", "Others", "Under Review", "Hold a monthly open forum where the school answers student concerns."),
]

RESPONSES = {
    "Slow internet in the lab": "Thank you for reporting. IT staff is checking the access points in the lab.",
    "Unfair grading": "We talked to the instructor. A clear rubric will now be shared before every quiz.",
    "Long enrollment lines": "Two more enrollment counters will open starting next semester.",
    "Too cold in classrooms": "Facilities will adjust the aircon settings this week.",
    "Schedule conflicts": "The registrar fixed the schedule. Please check your updated class list.",
    "Printer is always out of ink": "New ink cartridges were installed. We will check the printer weekly.",
    "Lack of lab equipment": "Purchase of three more microscopes is already in the budget plan.",
    "Water dispenser is empty": "The janitorial team will refill it every morning and noon.",
}


def _utc(days_ago, rng):
    when = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=rng.randint(0, 11),
                                                  minutes=rng.randint(0, 59))
    return when.strftime("%Y-%m-%d %H:%M:%S")


def seed_if_empty(db):
    if db.query_one("SELECT COUNT(*) FROM users")[0] > 0:
        return
    name, username, password = ADMIN
    admin_id = db.execute("INSERT INTO users (full_name, username, password_hash, role) "
                          "VALUES (?,?,?, 'admin')", (name, username, PasswordHasher.hash(password)))
    if not SEED_DEMO_DATA:
        return

    rng = random.Random(2026)
    hashed = PasswordHasher.hash(STUDENT_PASSWORD)     
    ids = []
    for full_name, uname in STUDENTS:
        ids.append(db.execute("INSERT INTO users (full_name, username, password_hash, role, created_at) "
                              "VALUES (?,?,?, 'student', ?)", (full_name, uname, hashed, _utc(25, rng))))

    feedback_ids = {}
    for title, cat, status, desc in FEEDBACK:
        created = _utc(rng.randint(0, 13), rng)
        feedback_ids[title] = db.execute(
            "INSERT INTO feedback (user_id, title, description, category, status, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)", (rng.choice(ids), title, desc, cat, status, created, created))
    for title, text in RESPONSES.items():
        db.execute("INSERT INTO responses (feedback_id, admin_id, response_text, created_at) VALUES (?,?,?,?)",
                   (feedback_ids[title], admin_id, text, _utc(rng.randint(0, 3), rng)))

    popularity = [11, 9, 8, 6, 5, 7, 4, 6, 3, 2]      
    for (title, cat, status, desc), n_votes in zip(SUGGESTIONS, popularity):
        owner = rng.choice(ids)
        sid = db.execute("INSERT INTO suggestions (user_id, title, description, category, status, created_at) "
                         "VALUES (?,?,?,?,?,?)", (owner, title, desc, cat, status, _utc(rng.randint(1, 13), rng)))
        voters = rng.sample([i for i in ids if i != owner], n_votes)
        for v in voters:
            db.execute("INSERT INTO votes (user_id, suggestion_id, created_at) VALUES (?,?,?)",
                       (v, sid, _utc(rng.randint(0, 10), rng)))
