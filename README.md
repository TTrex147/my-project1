# Integrated Student Feedback and Suggestion Management System
SDF04 - Object-Oriented Programming (Python & Database)

## How to run
1. Install Python 3.10 or newer (Tkinter is included on Windows/macOS).
2. Open a terminal in this folder and run:
       pip install -r requirements.txt
       python main.py
3. The first run creates `student_feedback.db` (SQLite) with demo data.

## Demo accounts
| Role    | Username       | Password   |
|---------|----------------|------------|
| Admin   | admin          | admin123   |
| Student | tungtungsahur  | student123 |
(other demo students: maria456, carlo789, ana123 ... all use `student123`)

To start with an EMPTY database: set `SEED_DEMO_DATA = False` in `seed.py`
and delete `student_feedback.db` (and the `-wal` / `-shm` files next to it).

## What the look is made of
- `assets/login_bg.jpg`  the picture behind the login page. Replace it with another
  picture to change the background (keep the name, or change it in `login_glass.py`).
- `login_glass.py`       the transparent "glass" login card.
  `GLASS_BLUR` (bigger = more frosted) and `GLASS_TINT` (smaller = more see-through) at the top of the class.
- `icons.py`             the line icons are drawn by code (no image files).
- Colors are all in `theme.py` (class `C`).

## Files
| File           | What it does                                                         |
|----------------|----------------------------------------------------------------------|
| main.py        | Starts the app, login/logout, menu navigation, live-sync checker     |
| login_glass.py | The glass login page (background picture, blur, remember me)         |
| screens.py     | All screens (dashboards, forms, tables, board, reports, users)       |
| widgets.py     | Animated parts: cards, KPI cards, sidebar, tables, charts, gauge, toast |
| icons.py       | Line icons drawn with Pillow                                         |
| theme.py       | Colors, fonts, animation helper                                      |
| models.py      | OOP classes: User/Student/Admin, Submission/Feedback/Suggestion      |
| managers.py    | AuthManager, UserManager, SubmissionManager, VoteManager, ResponseManager, ReportGenerator |
| database.py    | SQLite connection + the 5 tables from your schema                    |
| security.py    | Password hashing + offensive-word filter                             |
| seed.py        | Demo data                                                            |

## OOP used in the code
- Abstraction: `User` and `Submission` are abstract classes (`abc.ABC`)
- Inheritance: `Student`/`Admin` extend `User`; `Feedback`/`Suggestion` extend `Submission`; every screen extends `BaseScreen`
- Polymorphism: `menu_items()` is different for Student and Admin; `SubmissionManager` works for both feedback and suggestions
- Encapsulation: private attributes (`_title`) with read-only properties

## Live sync (multi-user)
Open the app in two windows and log in as different users. When one window
saves something, the other updates by itself within about 1.5 seconds
(the green dot in the sidebar blinks orange). Uses SQLite `PRAGMA data_version`.

## Make an .exe (Windows)
    pip install pyinstaller pillow reportlab
    python -m PyInstaller --clean --noconsole --onefile --name FeedbackSystem --add-data "assets;assets" --hidden-import PIL._tkinter_finder main.py
The file will be in the `dist` folder. The database is created next to the .exe.
- `--add-data "assets;assets"` puts the login picture inside the .exe
- `--hidden-import PIL._tkinter_finder` lets Pillow draw pictures inside the .exe
(On macOS/Linux use `:` instead of `;` in `--add-data`.)

## Notes about the schema
- `users.is_active` was added (needed for the "Deactivate" button in Manage Users).
- Dates are saved in UTC (CURRENT_TIMESTAMP) and shown in the computer's local time.
