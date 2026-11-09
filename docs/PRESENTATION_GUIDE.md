# Presentation guide

How to explain this project to a lecturer, a classmate or a panel.

## 30-second pitch

"Paper registers and shared QR codes are easy to cheat. Our system lets a lecturer open a class session that shows a
QR code that changes every 20 seconds. A student scans it on their phone, and the server checks the signature, the
time, whether the student is enrolled, whether it is the student's usual phone, and whether they are within the
venue's radius. It works on bad campus networks because scans are saved on the phone and synced later, and lecturers
can mark students without phones with an audited reason."

## 2-minute script

1. **Problem (20 s):** proxy attendance and unreliable network.
2. **Idea (30 s):** signed rotating QR + location check + server decides.
3. **Offline (20 s):** scan saved locally, sent when online; server treats repeats as one.
4. **Fairness (20 s):** weak GPS or a new phone is *flagged* for a human, not silently rejected; manual marking for
   students without phones, always with a reason and audit log.
5. **Reports (10 s):** percentages from finished sessions, 75 % eligibility, CSV export.
6. **Honest limits (20 s):** GPS can be spoofed and a QR can be relayed live; we make it harder and traceable.

## 5-minute walkthrough (live demo)

1. Run the stack (see README) and seed the dev data.
2. Sign in as a lecturer, create a session, show the rotating QR.
3. Sign in as a student (second browser/phone), scan; show "recorded".
4. Scan again → "already recorded".
5. Use a location outside the radius → "not accepted".
6. As the lecturer, manually mark another student with a reason; show the audit log as admin.
7. Close the session; open the course report and export CSV.
8. Turn off the network, scan, show the queued banner, turn it on and show it syncing.

Say clearly that the demo uses the **development login** and seeded fictional data.

## Questions you will get

**Can students cheat?** Yes, with effort: a friend relaying the QR plus a spoofed GPS. We do not claim otherwise; we
add expiry, geofence, device binding, flags, and an audit trail.

**Why does the server decide?** The phone is controlled by the student. It reports; the server verifies.

**Why not just a short code?** Codes can be shared by message; a signed 20 s slot plus location raises the cost.

**What if the network is down?** The scan is stored in IndexedDB and synced later; offline timing is checked against
the phone's reported time, which is a known weaker check.

**Why Firebase?** We avoid writing password handling; roles stay in our database so we control them.

**Why PostgreSQL constraints?** Correctness under concurrency should not depend on application code alone.

**Is it deployed?** No. It runs locally and in CI-style tests; see the README for what was and was not verified.

## Glossary

* **Slot:** a 20-second window of the QR code.
* **HMAC:** a keyed hash proving the QR was made by someone with the secret.
* **Geofence:** a circle around the venue.
* **Haversine:** the formula for distance between two coordinates.
* **Idempotent:** repeating the request gives the same result.
* **Flagged:** accepted for review, not yet counted.
* **Finalized:** the session is closed; it counts in percentages.
