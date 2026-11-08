
from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from pathlib import Path
from datetime import date


app = Flask(__name__)

DATABASE = Path(__file__).parent / "jobtrack.db"


# DATABASE CONNECTION
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn




# CREATE DATABASE TABLE
def init_db():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            job_title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Applied',
            date_applied TEXT NOT NULL,
            location TEXT,
            notes TEXT
        )
    """)


    conn.execute("""
        CREATE TABLE IF NOT EXISTS interviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            job_title TEXT NOT NULL,
            interview_date TEXT NOT NULL,
            interview_time TEXT,
            location TEXT,
            notes TEXT,
            follow_up_date TEXT
        )
    """)


    conn.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            reminder_date TEXT NOT NULL,
            notes TEXT,
            completed INTEGER DEFAULT 0
        )
    """)



    # CREATE APPLICATION HISTORY TABLE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS application_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            changed_at TEXT NOT NULL,
            FOREIGN KEY (application_id) REFERENCES applications(id)
        )
    """)



    # ADD PREVIOUS STATUS COLUMN IF MISSING
    history_columns = [
        column[1]
        for column in conn.execute("PRAGMA table_info(application_history)")
    ]

    if "previous_status" not in history_columns:
        conn.execute(
            "ALTER TABLE application_history ADD COLUMN previous_status TEXT"
        )



    # ADD RESPONSE DATE COLUMN IF MISSING
    columns = [
        column[1]
        for column in conn.execute("PRAGMA table_info(applications)").fetchall()
    ]

    if "response_date" not in columns:
        conn.execute(
            "ALTER TABLE applications ADD COLUMN response_date TEXT"
        )




    conn.commit()
    conn.close()




# ADD NEW APPLICATION
@app.route("/add", methods=["GET", "POST"])
def add_application():

    if request.method == "POST":

        company = request.form.get("company", "").strip()
        job_title = request.form.get("job_title", "").strip()
        status = request.form.get("status", "Applied")
        date_applied = request.form.get("date_applied", "")
        location = request.form.get("location", "").strip()
        notes = request.form.get("notes", "").strip()

        if not company or not job_title or not date_applied:
            return "Company, job title, and date are required.", 400

        if status not in ["Applied", "Interview", "Offer", "Rejected"]:
            return "Invalid application status.", 400

        conn = get_db_connection()

        conn.execute("""
            INSERT INTO applications
            (company, job_title, status, date_applied, location, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (company, job_title, status, date_applied, location, notes))

        conn.commit()
        conn.close()

        return redirect(url_for("dashboard"))

    return render_template("add_application.html")




# DASHBOARD
@app.route("/")
def dashboard():
    conn = get_db_connection()

    applications = conn.execute(
        "SELECT * FROM applications ORDER BY id DESC"
    ).fetchall()

    total = len(applications)
    interviews = sum(a["status"] == "Interview" for a in applications)
    offers = sum(a["status"] == "Offer" for a in applications)
    rejected = sum(a["status"] == "Rejected" for a in applications)
    pending = total - interviews - offers - rejected


    # APPLICATION INSIGHTS
    success_rate = (offers / total * 100) if total else 0

    responses = interviews + offers + rejected
    response_rate = (responses / total * 100) if total else 0



    # AVERAGE EMPLOYER RESPONSE TIME
    response_times = []

    for application in applications:
        if application["response_date"]:
            applied = date.fromisoformat(application["date_applied"])
            responded = date.fromisoformat(application["response_date"])

            days = (responded - applied).days

            if days >= 0:
                response_times.append(days)

    average_response_time = (
        round(sum(response_times) / len(response_times), 1)
        if response_times else 0
    )



    upcoming_interviews = conn.execute(
        """
        SELECT * FROM interviews
        WHERE interview_date >= date('now')
        ORDER BY interview_date ASC
        LIMIT 5
        """
    ).fetchall()

    upcoming_reminders = conn.execute(
        """
        SELECT * FROM reminders
        WHERE completed = 0
        AND reminder_date >= date('now')
        ORDER BY reminder_date ASC
        LIMIT 5
        """
    ).fetchall()


    goal = 20
    progress = min((total / goal) * 100, 100)
    remaining = max(goal - total, 0)

    




    # APPLICATION ACTIVITY TIMELINE
    activity_timeline = conn.execute("""
        SELECT
            'Application Submitted' AS activity_type,
            company,
            job_title,
            'Application submitted' AS details,
            date_applied AS activity_date
        FROM applications

        UNION ALL

        SELECT
            'Status Change' AS activity_type,
            applications.company,
            applications.job_title,
            COALESCE(application_history.previous_status, 'Initial')
                || ' → ' || application_history.status AS details,
            application_history.changed_at AS activity_date
        FROM application_history
        JOIN applications
            ON application_history.application_id = applications.id

        UNION ALL

        SELECT
            'Interview Scheduled' AS activity_type,
            company,
            job_title,
            'Interview scheduled' AS details,
            interview_date AS activity_date
        FROM interviews

        ORDER BY activity_date DESC
    """).fetchall()

    conn.close()


    
    return render_template(
    "dashboard.html",
    applications=applications,
    total=total,
    goal=goal,
    progress=progress,
    remaining=remaining,
    interviews=interviews,
    offers=offers,
    rejected=rejected,
    pending=pending,
    success_rate=success_rate,
    response_rate=response_rate,
    average_response_time=average_response_time,
        upcoming_interviews=upcoming_interviews,
        upcoming_reminders=upcoming_reminders,
        activity_timeline=activity_timeline
)




# APPLICATIONS PAGE
@app.route("/applications")
def applications():
    conn = get_db_connection()

    applications = conn.execute(
        "SELECT * FROM applications ORDER BY id DESC"
    ).fetchall()


    application_history = conn.execute("""
        SELECT
            application_history.*,
            applications.company,
            applications.job_title
        FROM application_history
        JOIN applications
            ON application_history.application_id = applications.id
        ORDER BY application_history.changed_at DESC
    """).fetchall()



    # APPLICATION ACTIVITY TIMELINE
    activity_timeline = conn.execute("""
        SELECT
            'Application Submitted' AS activity_type,
            company,
            job_title,
            'Application submitted' AS details,
            date_applied AS activity_date
        FROM applications

        UNION ALL

        SELECT
            'Status Change' AS activity_type,
            applications.company,
            applications.job_title,
            COALESCE(application_history.previous_status, 'Initial')
                || ' → ' || application_history.status AS details,
            application_history.changed_at AS activity_date
        FROM application_history
        JOIN applications
            ON application_history.application_id = applications.id

        UNION ALL

        SELECT
            'Interview Scheduled' AS activity_type,
            company,
            job_title,
            'Interview scheduled' AS details,
            interview_date AS activity_date
        FROM interviews

        ORDER BY activity_date DESC
    """).fetchall()


    conn.close()

    return render_template(
    "applications.html",
    applications=applications,
    application_history=application_history,
    activity_timeline=activity_timeline
)


# UPDATE APPLICATION STATUS
@app.route("/update-application/<int:application_id>", methods=["POST"])
def update_application(application_id):
    new_status = request.form.get("status", "").strip()

    if new_status not in ["Applied", "Interview", "Offer", "Rejected"]:
        return "Invalid application status.", 400

    conn = get_db_connection()

    existing_application = conn.execute(
        "SELECT status FROM applications WHERE id = ?",
        (application_id,)
    ).fetchone()

    if existing_application is None:
        conn.close()
        return "Application not found.", 404

    response_date = None if new_status == "Applied" else date.today().isoformat()

    conn.execute(
        """
        UPDATE applications
        SET status = ?, response_date = ?
        WHERE id = ?
        """,
        (new_status, response_date, application_id)
    )


    if existing_application["status"] != new_status:
        conn.execute(
        """
        INSERT INTO application_history
        (application_id, previous_status, status, changed_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            application_id,
            existing_application["status"],
            new_status,
            date.today().isoformat()
        )
    )

    conn.commit()
    conn.close()

    return redirect(url_for("applications"))


# INTERVIEWS PAGE
@app.route("/interviews")
def interviews():
    conn = get_db_connection()

    interviews = conn.execute(
        "SELECT * FROM interviews ORDER BY interview_date ASC"
    ).fetchall()

    conn.close()

    return render_template(
        "interviews.html",
        interviews=interviews
    )



# ADD INTERVIEW PAGE
@app.route("/add-interview", methods=["GET", "POST"])
def add_interview():
    if request.method == "POST":
        company = request.form.get("company")
        job_title = request.form.get("job_title")
        interview_date = request.form.get("interview_date")
        interview_time = request.form.get("interview_time")
        location = request.form.get("location")
        notes = request.form.get("notes")
        follow_up_date = request.form.get("follow_up_date")

        conn = get_db_connection()

        conn.execute("""
            INSERT INTO interviews (
                company, job_title, interview_date,
                interview_time, location, notes, follow_up_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            company, job_title, interview_date,
            interview_time, location, notes, follow_up_date
        ))

        conn.commit()
        conn.close()

        return redirect(url_for("interviews"))

    return render_template("add_interview.html")



# REMINDERS PAGE
@app.route("/reminders")
def reminders():
    conn = get_db_connection()

    reminders = conn.execute(
        "SELECT * FROM reminders ORDER BY reminder_date ASC"
    ).fetchall()

    conn.close()

    return render_template(
        "reminders.html",
        reminders=reminders
    )


# ADD REMINDER
@app.route("/add-reminder", methods=["GET", "POST"])
def add_reminder():
    if request.method == "POST":
        title = request.form.get("title")
        reminder_date = request.form.get("reminder_date")
        notes = request.form.get("notes")

        conn = get_db_connection()

        conn.execute(
            """
            INSERT INTO reminders (title, reminder_date, notes)
            VALUES (?, ?, ?)
            """,
            (title, reminder_date, notes)
        )

        conn.commit()
        conn.close()

        return redirect(url_for("reminders"))

    return render_template("add_reminder.html")


# COMPLETE REMINDER
@app.route("/complete-reminder/<int:reminder_id>", methods=["POST"])
def complete_reminder(reminder_id):
    conn = get_db_connection()

    conn.execute(
        "UPDATE reminders SET completed = 1 WHERE id = ?",
        (reminder_id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("reminders"))


# DELETE REMINDER
@app.route("/delete-reminder/<int:reminder_id>", methods=["POST"])
def delete_reminder(reminder_id):
    conn = get_db_connection()

    conn.execute(
        "DELETE FROM reminders WHERE id = ?",
        (reminder_id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("reminders"))



if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5001)


