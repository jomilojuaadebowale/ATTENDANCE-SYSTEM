# User guide

Three kinds of people use the system. You only see the screens for your role.

## Students

**Before you start:** an administrator must have added you (with your university email) and enrolled you in your
courses. Sign in with that email.

**Marking attendance**
1. Open **Scan** on your phone. Allow camera and location when asked.
2. Point the camera at the lecturer's QR code (it changes every 20 seconds, so scan it live).
3. Wait for the result:
   * **Attendance recorded** — you are marked present.
   * **Saved, needs review** — a lecturer will check it (for example weak GPS or a different phone).
   * **Already recorded** — you were already marked; nothing more to do.
   * **Not accepted** — read the message (outside the class area, session ended, QR not valid).
4. No network? The scan is saved on your phone and sent automatically when you are back online. It only counts once
   the app says it was recorded. Keep the app open or reopen it when you have signal.
5. If the camera does not work, the scanner has a "paste the code text" box. The lecturer screen does not display the code as text, so in practice this is a fallback for testing; otherwise ask the lecturer to mark you manually.

**History** shows your courses and percentages. Percentages count only finished sessions, and unreviewed flagged
scans do not count yet.

**Problems**
* New phone: ask an administrator to reset your device.
* No phone or dead battery: tell the lecturer; they can mark you manually with a reason.
* Location blocked: allow location for the site in your browser settings.

## Lecturers

1. **Courses** lists courses you are assigned to.
2. **New session:** choose the course, venue (or use your current location), duration and radius. The session starts.
3. **Session console:** show the QR on the projector. It rotates by itself. The live roster shows who is present,
   flagged or not yet marked.
4. **Flagged scans:** review each one and approve or reject with a short reason.
5. **No phone / problem:** use manual marking, pick a reason. It is recorded with your name.
6. **Close** the session when done (this finalizes it). You can still correct for 24 hours after it ends.
7. **Course report:** percentages per student, who is below 75 %, and a CSV export.

## Administrators (super admin)

* **Users:** create users (or import a list), set roles, deactivate accounts, reset a student's device.
* **Courses:** create courses, assign lecturers, enrol students (also by list).
* **Venues:** create venues with coordinates and a default radius.
* **Audit:** read the log of sensitive actions. **Overview** shows totals.
* Admins can correct attendance at any time.

## FAQ

**Why was I flagged?** Usually weak GPS indoors, a different phone than before, or a late sync. A lecturer decides.

**Can I scan from the hostel using a photo of the QR?** No: it expires within seconds and your location must be near
the venue.

**Is my location tracked?** No. It is read once when you scan.
